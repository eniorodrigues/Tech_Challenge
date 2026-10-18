"""
Instância compilada do problema e a **função de avaliação (fitness)**.

Representação usada em todo o projeto
-------------------------------------
* Índice ``0`` é a central (depósito); entregas são ``1..N`` (na ordem de
  ``scenario.deliveries``).
* Uma **solução** é uma lista de ``K`` rotas, uma por veículo, na ordem de
  ``scenario.vehicles``: ``[[3, 7, 1], [], [5, 2, 4], ...]``. Rota vazia =
  veículo não sai.
* O **cromossomo** do algoritmo genético (ver :mod:`medroute.ga.representation`)
  é uma permutação de ``1..N`` intercalada com ``K-1`` separadores
  (genes ``N+1..N+K-1``). O segmento *k* é a rota do veículo *k*. Com
  ``K = 1`` não há separador e o cromossomo é exatamente o do TSP do código
  base.

Função fitness (minimização)
----------------------------
Para cada rota do veículo *v*::

    custo_v = w_dist · km_v                         (distância percorrida)
            + w_custo · km_v · R$/km_v              (opcional: custo operacional)
            + w_prio · Σ peso_i · chegada_i / 60     (prioridade: crítico cedo)
            + w_atraso · Σ peso_i · atraso_i         (SLA e janelas de horário)
            + penalidades de restrições duras        (capacidade, autonomia,
                                                      compatibilidade, jornada)

``peso_i`` vem da prioridade (crítica 10, alta 3, normal 1). ``atraso_i`` é
quanto o início do atendimento passou do prazo, onde prazo = mín(fim da
janela, SLA da prioridade). Chegar antes da abertura da janela gera espera.

Restrições duras são tratadas por **penalidade**: cada violação soma um
custo fixo alto (``violation_base``) mais um termo proporcional ao excesso.
Assim uma solução viável quase sempre vence uma inviável, mas o GA ainda
consegue "atravessar" regiões inviáveis — e o termo proporcional diz a ele
em que direção a violação diminui.

Há duas implementações da mesma conta, de propósito:

* :meth:`Problem.route_cost` — enxuta, só devolve o número; é chamada
  dezenas de milhares de vezes por segundo dentro do GA;
* :meth:`Problem.evaluate` — detalhada, devolve horários, cargas e cada
  violação, para relatórios, mapa e LLM.

Um teste automatizado garante que as duas sempre concordam.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .domain import Priority, Scenario
from .geo import distance_matrix_km

INF = math.inf


@dataclass(frozen=True)
class FitnessWeights:
    """Pesos da função fitness (todos em "km equivalentes")."""

    distance: float = 1.0          # por km rodado
    cost: float = 0.0              # por R$ gasto (0 = desligado)
    priority_time: float = 1.0     # por (peso de prioridade × hora de chegada)
    lateness: float = 1.0          # por (peso de prioridade × minuto de atraso)
    capacity: float = 50.0         # por kg acima da capacidade
    range: float = 50.0            # por km acima da autonomia
    compatibility: float = 400.0   # por entrega em veículo incompatível
    shift: float = 5.0             # por minuto além da jornada
    violation_base: float = 1000.0  # custo fixo de cada violação dura

    def to_dict(self) -> dict[str, float]:
        return dict(self.__dict__)


@dataclass
class StopResult:
    """Uma parada já simulada no tempo."""

    index: int               # índice 1..N da entrega
    arrival: float           # chegada (min do turno)
    start: float             # início do atendimento (após eventual espera)
    departure: float         # saída
    wait: float              # minutos esperando a janela abrir
    deadline: float          # prazo (mín. entre fim da janela e SLA)
    lateness: float          # atraso em relação ao prazo (0 se no prazo)
    load_after: float        # carga restante no veículo após descarregar
    leg_km: float            # km do trecho até esta parada
    compatible: bool


@dataclass
class RouteResult:
    """Resultado detalhado da rota de um veículo."""

    vehicle_index: int
    stops: list[int]
    stop_results: list[StopResult]
    distance_km: float
    load_kg: float
    duration_min: float      # instante de retorno à central
    travel_min: float
    service_min: float
    wait_min: float
    priority_cost: float     # Σ peso · chegada (min)
    lateness_cost: float     # Σ peso · atraso (min)
    capacity_excess: float
    range_excess: float
    shift_excess: float
    incompatible: int
    cost: float              # contribuição desta rota para a fitness

    @property
    def used(self) -> bool:
        return bool(self.stops)

    @property
    def violations(self) -> dict[str, float]:
        v: dict[str, float] = {}
        if self.capacity_excess > 1e-9:
            v["capacidade_kg"] = self.capacity_excess
        if self.range_excess > 1e-9:
            v["autonomia_km"] = self.range_excess
        if self.shift_excess > 1e-9:
            v["jornada_min"] = self.shift_excess
        if self.incompatible:
            v["incompatibilidade"] = float(self.incompatible)
        return v


@dataclass
class Evaluation:
    """Avaliação completa de uma solução (lista de rotas)."""

    routes: list[RouteResult]
    fitness: float
    weights: FitnessWeights = field(repr=False, default_factory=FitnessWeights)

    @property
    def distance_km(self) -> float:
        return sum(r.distance_km for r in self.routes)

    @property
    def penalty(self) -> float:
        """Parte da fitness que vem só das restrições duras."""
        w = self.weights
        p = 0.0
        for r in self.routes:
            if r.capacity_excess > 1e-9:
                p += w.violation_base + w.capacity * r.capacity_excess
            if r.range_excess > 1e-9:
                p += w.violation_base + w.range * r.range_excess
            if r.incompatible:
                p += r.incompatible * (w.violation_base + w.compatibility)
            if r.shift_excess > 1e-9:
                p += w.violation_base + w.shift * r.shift_excess
        return p

    @property
    def n_violations(self) -> int:
        n = 0
        for r in self.routes:
            n += (r.capacity_excess > 1e-9) + (r.range_excess > 1e-9) \
                + (r.shift_excess > 1e-9) + r.incompatible
        return int(n)

    @property
    def feasible(self) -> bool:
        """Viável = nenhuma restrição dura violada (atrasos são suaves)."""
        return self.n_violations == 0

    @property
    def late_stops(self) -> list[StopResult]:
        return [s for r in self.routes for s in r.stop_results if s.lateness > 1e-6]

    @property
    def priority_cost(self) -> float:
        return sum(r.priority_cost for r in self.routes)

    @property
    def lateness_cost(self) -> float:
        return sum(r.lateness_cost for r in self.routes)

    def as_routes(self) -> list[list[int]]:
        return [list(r.stops) for r in self.routes]


class Problem:
    """Cenário compilado em listas/arrays para avaliação rápida.

    Parameters
    ----------
    scenario:
        O dia de operação.
    weights:
        Pesos da fitness.
    distance_matrix:
        Matriz (N+1)x(N+1) em km, opcional (ex.: vinda de um roteador real
        como OSRM). Se omitida, usa haversine × fator de tortuosidade.
    """

    def __init__(
        self,
        scenario: Scenario,
        weights: FitnessWeights | None = None,
        distance_matrix: np.ndarray | None = None,
    ) -> None:
        self.scenario = scenario
        self.weights = weights or FitnessWeights()
        dl = scenario.deliveries
        vs = scenario.vehicles
        self.n = len(dl)
        self.k = len(vs)

        coords = [(scenario.depot.lat, scenario.depot.lon)] + [(d.lat, d.lon) for d in dl]
        if distance_matrix is None:
            distance_matrix = distance_matrix_km(coords, scenario.circuity)
        self.dist_np: np.ndarray = np.asarray(distance_matrix, dtype=float)
        self.D: list[list[float]] = self.dist_np.tolist()

        policy = scenario.policy
        self.demand = [0.0] + [d.demand_kg for d in dl]
        self.service = [0.0] + [d.service_min for d in dl]
        self.win_open = [0.0] + [d.window[0] for d in dl]
        self.deadline = [INF]
        for d in dl:
            sla = policy.sla(d.priority)
            self.deadline.append(min(d.window[1], sla if sla is not None else INF))
        self.pweight = [0.0] + [policy.weight(d.priority) for d in dl]
        self.priority = [Priority.NORMAL] + [d.priority for d in dl]

        self.capacity = [v.capacity_kg for v in vs]
        self.range_km = [v.range_km for v in vs]
        self.speed = [v.speed_kmh / 60.0 for v in vs]        # km por minuto
        self.shift = [v.max_shift_min or scenario.shift_minutes for v in vs]
        self.cost_km = [v.cost_per_km for v in vs]
        self.compat = [[True] + [v.can_carry(d) for d in dl] for v in vs]

        # Para cada entrega, quais veículos podem levá-la (usado por operadores).
        self.allowed_vehicles = [list(range(self.k))] + [
            [vi for vi in range(self.k) if self.compat[vi][i]] for i in range(1, self.n + 1)
        ]
        self.chromosome_length = self.n + self.k - 1

    # ------------------------------------------------------------------ codec
    def decode(self, chromosome: Sequence[int]) -> list[list[int]]:
        """Cromossomo (permutação com separadores) → lista de K rotas."""
        n = self.n
        routes: list[list[int]] = [[] for _ in range(self.k)]
        r = 0
        for g in chromosome:
            if g > n:
                r += 1
            else:
                routes[r].append(g)
        return routes

    def encode(self, routes: Sequence[Sequence[int]]) -> list[int]:
        """Lista de K rotas → cromossomo (separadores ``N+1..N+K-1``)."""
        if len(routes) != self.k:
            raise ValueError(f"esperava {self.k} rotas, recebi {len(routes)}")
        chrom: list[int] = []
        for r, stops in enumerate(routes):
            if r:
                chrom.append(self.n + r)
            chrom.extend(stops)
        return chrom

    # ------------------------------------------------- avaliação rápida (GA)
    def route_cost(self, v: int, stops: Sequence[int]) -> float:
        """Custo de uma rota (mesma conta de :meth:`evaluate`, sem detalhes)."""
        if not stops:
            return 0.0
        D = self.D
        speed = self.speed[v]
        compat_v = self.compat[v]
        win_open = self.win_open
        deadline = self.deadline
        pw = self.pweight
        svc = self.service
        dem = self.demand

        prev = 0
        t = 0.0
        dist = 0.0
        load = 0.0
        prio = 0.0
        late = 0.0
        incompat = 0
        for i in stops:
            d = D[prev][i]
            dist += d
            t += d / speed
            if t < win_open[i]:
                t = win_open[i]
            w = pw[i]
            prio += w * t
            if t > deadline[i]:
                late += w * (t - deadline[i])
            t += svc[i]
            load += dem[i]
            if not compat_v[i]:
                incompat += 1
            prev = i
        d = D[prev][0]
        dist += d
        t += d / speed

        W = self.weights
        cost = W.distance * dist + W.priority_time * prio / 60.0 + W.lateness * late
        if W.cost:
            cost += W.cost * dist * self.cost_km[v]
        if load > self.capacity[v] + 1e-9:
            cost += W.violation_base + W.capacity * (load - self.capacity[v])
        if dist > self.range_km[v] + 1e-9:
            cost += W.violation_base + W.range * (dist - self.range_km[v])
        if incompat:
            cost += incompat * (W.violation_base + W.compatibility)
        if t > self.shift[v] + 1e-9:
            cost += W.violation_base + W.shift * (t - self.shift[v])
        return cost

    def routes_cost(self, routes: Sequence[Sequence[int]]) -> float:
        return sum(self.route_cost(v, r) for v, r in enumerate(routes))

    def fitness(self, chromosome: Sequence[int]) -> float:
        """Fitness de um cromossomo (quanto menor, melhor)."""
        return self.routes_cost(self.decode(chromosome))

    # ---------------------------------------------- avaliação detalhada
    def evaluate_route(self, v: int, stops: Sequence[int]) -> RouteResult:
        D = self.D
        speed = self.speed[v]
        prev = 0
        t = 0.0
        dist = 0.0
        load_total = sum(self.demand[i] for i in stops)
        load_left = load_total
        prio = late = 0.0
        travel = service = wait = 0.0
        incompat = 0
        results: list[StopResult] = []
        for i in stops:
            leg = D[prev][i]
            dist += leg
            dt = leg / speed
            travel += dt
            t += dt
            arrival = t
            start = max(arrival, self.win_open[i])
            w_wait = start - arrival
            wait += w_wait
            t = start
            w = self.pweight[i]
            prio += w * t
            lateness = max(0.0, t - self.deadline[i])
            late += w * lateness
            t += self.service[i]
            service += self.service[i]
            load_left -= self.demand[i]
            ok = self.compat[v][i]
            incompat += (not ok)
            results.append(StopResult(
                index=i, arrival=arrival, start=start, departure=t, wait=w_wait,
                deadline=self.deadline[i], lateness=lateness,
                load_after=max(0.0, load_left), leg_km=leg, compatible=ok,
            ))
            prev = i
        if stops:
            leg = D[prev][0]
            dist += leg
            travel += leg / speed
            t += leg / speed

        cost = self.route_cost(v, stops)
        return RouteResult(
            vehicle_index=v,
            stops=list(stops),
            stop_results=results,
            distance_km=dist,
            load_kg=load_total,
            duration_min=t if stops else 0.0,
            travel_min=travel,
            service_min=service,
            wait_min=wait,
            priority_cost=prio,
            lateness_cost=late,
            capacity_excess=max(0.0, load_total - self.capacity[v]),
            range_excess=max(0.0, dist - self.range_km[v]),
            shift_excess=max(0.0, (t if stops else 0.0) - self.shift[v]),
            incompatible=incompat,
            cost=cost,
        )

    def evaluate(self, routes: Sequence[Sequence[int]]) -> Evaluation:
        """Avaliação detalhada de uma solução completa."""
        self.check_solution(routes)
        rr = [self.evaluate_route(v, r) for v, r in enumerate(routes)]
        return Evaluation(routes=rr, fitness=sum(r.cost for r in rr), weights=self.weights)

    def evaluate_chromosome(self, chromosome: Sequence[int]) -> Evaluation:
        return self.evaluate(self.decode(chromosome))

    # ------------------------------------------------------------ validação
    def check_solution(self, routes: Sequence[Sequence[int]]) -> None:
        """Garante que cada entrega aparece exatamente uma vez."""
        if len(routes) != self.k:
            raise ValueError(f"esperava {self.k} rotas, recebi {len(routes)}")
        vistos = [g for r in routes for g in r]
        if sorted(vistos) != list(range(1, self.n + 1)):
            faltando = set(range(1, self.n + 1)) - set(vistos)
            repetidos = {g for g in vistos if vistos.count(g) > 1}
            raise ValueError(
                f"solução inválida: faltando={sorted(faltando)} repetidos={sorted(repetidos)}"
            )
