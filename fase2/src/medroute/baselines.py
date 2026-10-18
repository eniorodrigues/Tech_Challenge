"""
Abordagens de roteamento usadas como **comparação** (e como sementes do GA).

=========================  ===================================================
``nearest_neighbor``       Vizinho mais próximo guloso, veículo a veículo,
                           respeitando capacidade/autonomia/compatibilidade.
``nearest_neighbor`` +     Variante "despachante": atende primeiro as
``priority_first=True``    entregas mais urgentes. Representa o processo
                           manual típico e é a referência do relatório de
                           economia.
``clarke_wright``          Algoritmo de economias (Clarke & Wright, 1964),
                           a heurística clássica de VRP.
``sweep``                  Varredura angular (Gillett & Miller, 1974) com
                           várias rotações + 2-opt.
``random_search``          Melhor de N soluções aleatórias (mesmo orçamento
                           de avaliações do GA) — prova de que o GA não é
                           sorte.
``ortools``                Google OR-Tools (busca local guiada) — solver
                           industrial, referência de qualidade.
``tsp_base_split``         O TSP do código base (uma rota única, sem
                           restrições) fatiado entre os veículos.
=========================  ===================================================
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Callable

from .ga.local_search import improve_solution, two_opt_route
from .ga.operators import cheapest_insertion
from .geo import bearing_deg
from .problem import Evaluation, Problem


@dataclass
class BaselineResult:
    name: str
    routes: list[list[int]]
    evaluation: Evaluation
    runtime_s: float
    extra: dict = field(default_factory=dict)


def _ordem_veiculos(problem: Problem) -> list[int]:
    """Veículos com recursos especiais primeiro, depois os de maior capacidade."""
    vs = problem.scenario.vehicles
    return sorted(range(problem.k), key=lambda v: (-len(vs[v].features), -vs[v].capacity_kg))


def _insere_sobras(problem: Problem, routes: list[list[int]], sobras: list[int]) -> None:
    """Entregas que não couberam em lugar nenhum: inserção mais barata
    (pode gerar violação — e a avaliação vai mostrar isso)."""
    cargas = [sum(problem.demand[i] for i in r) for r in routes]
    for c in sorted(sobras, key=lambda i: -problem.pweight[i]):
        cheapest_insertion(problem, routes, c, cargas)


# =============================================================================
# Vizinho mais próximo
# =============================================================================
def nearest_neighbor(problem: Problem, priority_first: bool = False) -> list[list[int]]:
    D = problem.D
    livres = set(range(1, problem.n + 1))
    routes: list[list[int]] = [[] for _ in range(problem.k)]
    for v in _ordem_veiculos(problem):
        feats = problem.scenario.vehicles[v].features
        atual, t, dist, carga = 0, 0.0, 0.0, 0.0
        while True:
            cands = []
            for i in livres:
                if not problem.compat[v][i]:
                    continue
                if carga + problem.demand[i] > problem.capacity[v] + 1e-9:
                    continue
                d = D[atual][i]
                if dist + d + D[i][0] > problem.range_km[v] + 1e-9:
                    continue
                chegada = max(t + d / problem.speed[v], problem.win_open[i])
                fim = chegada + problem.service[i] + D[i][0] / problem.speed[v]
                if fim > problem.shift[v] + 1e-9:
                    continue
                especial = bool(problem.scenario.deliveries[i - 1].requirements & feats)
                chave = (
                    -int(problem.priority[i]) if priority_first else 0,
                    -int(especial),
                    d,
                )
                cands.append((chave, i, d, chegada))
            if not cands:
                break
            _, i, d, chegada = min(cands)
            routes[v].append(i)
            livres.discard(i)
            dist += d
            carga += problem.demand[i]
            t = chegada + problem.service[i]
            atual = i
    _insere_sobras(problem, routes, sorted(livres))
    return routes


# =============================================================================
# Clarke & Wright (economias)
# =============================================================================
def _viavel_em_algum(problem: Problem, rota: list[int]) -> bool:
    for v in range(problem.k):
        if all(problem.compat[v][i] for i in rota):
            r = problem.evaluate_route(v, rota)
            if not r.violations:
                return True
    return False


def clarke_wright(problem: Problem) -> list[list[int]]:
    D = problem.D
    n = problem.n
    rotas: dict[int, list[int]] = {i: [i] for i in range(1, n + 1)}
    dono = {i: i for i in range(1, n + 1)}
    economias = sorted(
        ((D[0][i] + D[0][j] - D[i][j], i, j)
         for i in range(1, n + 1) for j in range(i + 1, n + 1)),
        reverse=True,
    )
    for s, i, j in economias:
        if s <= 0:
            break
        ri, rj = dono[i], dono[j]
        if ri == rj:
            continue
        Ri, Rj = rotas[ri], rotas[rj]
        if Ri[-1] == i and Rj[0] == j:
            nova = Ri + Rj
        elif Ri[0] == i and Rj[-1] == j:
            nova = Rj + Ri
        elif Ri[-1] == i and Rj[-1] == j:
            nova = Ri + Rj[::-1]
        elif Ri[0] == i and Rj[0] == j:
            nova = Ri[::-1] + Rj
        else:
            continue
        if not _viavel_em_algum(problem, nova):
            continue
        rotas[ri] = nova
        del rotas[rj]
        for c in Rj:
            dono[c] = ri

    # Atribuição rota → veículo: rotas mais "difíceis" primeiro, cada uma no
    # menor veículo livre em que ela é viável.
    solucao: list[list[int]] = [[] for _ in range(problem.k)]
    livres = set(range(problem.k))
    sobras: list[int] = []
    pendentes = sorted(
        rotas.values(),
        key=lambda r: (-max(len(problem.scenario.deliveries[i - 1].requirements) for i in r),
                       -sum(problem.demand[i] for i in r)),
    )
    for rota in pendentes:
        opcoes = []
        for v in livres:
            if all(problem.compat[v][i] for i in rota):
                res = problem.evaluate_route(v, rota)
                if not res.violations:
                    opcoes.append((problem.capacity[v], v))
        if opcoes:
            _, v = min(opcoes)
            solucao[v] = list(rota)
            livres.discard(v)
        else:
            sobras.extend(rota)
    _insere_sobras(problem, solucao, sobras)
    return [two_opt_route(problem, v, r) for v, r in enumerate(solucao)]


# =============================================================================
# Sweep (varredura angular)
# =============================================================================
def sweep(problem: Problem, rotacoes: int = 12) -> list[list[int]]:
    dep = problem.scenario.depot
    angulos = {
        i: bearing_deg(dep.lat, dep.lon, d.lat, d.lon)
        for i, d in enumerate(problem.scenario.deliveries, start=1)
    }
    melhor, melhor_custo = None, math.inf
    for r in range(rotacoes):
        inicio = 360.0 * r / rotacoes
        ordem = sorted(angulos, key=lambda i: (angulos[i] - inicio) % 360.0)
        routes: list[list[int]] = [[] for _ in range(problem.k)]
        pendentes = list(ordem)
        for v in _ordem_veiculos(problem):
            carga = 0.0
            resto = []
            for i in pendentes:
                if problem.compat[v][i] and carga + problem.demand[i] <= problem.capacity[v]:
                    cand = routes[v] + [i]
                    if not problem.evaluate_route(v, cand).violations:
                        routes[v] = cand
                        carga += problem.demand[i]
                        continue
                resto.append(i)
            pendentes = resto
        _insere_sobras(problem, routes, pendentes)
        routes = [two_opt_route(problem, v, rt) for v, rt in enumerate(routes)]
        custo = problem.routes_cost(routes)
        if custo < melhor_custo:
            melhor, melhor_custo = routes, custo
    assert melhor is not None
    return melhor


# =============================================================================
# Busca aleatória
# =============================================================================
def random_search(problem: Problem, evaluations: int = 50_000, seed: int = 42) -> list[list[int]]:
    rng = random.Random(seed)
    genes = list(range(1, problem.n + problem.k))
    melhor, melhor_f = None, math.inf
    for _ in range(evaluations):
        rng.shuffle(genes)
        f = problem.fitness(genes)
        if f < melhor_f:
            melhor, melhor_f = list(genes), f
    return problem.decode(melhor)


# =============================================================================
# TSP do código base + fatiamento guloso
# =============================================================================
def split_tour_greedy(problem: Problem, tour: list[int]) -> list[list[int]]:
    """Fatia uma rota única (TSP) entre os veículos, na ordem do tour.

    Cada veículo recebe entregas consecutivas enquanto a capacidade e a
    autonomia permitirem; o resto vai para o próximo veículo. **Não** olha
    compatibilidade nem prioridade — é o que se obtém "só reaproveitando o
    TSP", e a avaliação mostra o preço disso.
    """
    routes: list[list[int]] = [[] for _ in range(problem.k)]
    ordem = sorted(range(problem.k), key=lambda v: -problem.capacity[v])
    pos = 0
    for j, v in enumerate(ordem):
        ultimo = j == len(ordem) - 1
        while pos < len(tour):
            if ultimo:  # o último veículo leva o que sobrou, caiba ou não
                routes[v].append(tour[pos])
                pos += 1
                continue
            cand = routes[v] + [tour[pos]]
            res = problem.evaluate_route(v, cand)
            if (res.capacity_excess <= 1e-9 and res.range_excess <= 1e-9
                    and res.shift_excess <= 1e-9):
                routes[v] = cand
                pos += 1
            else:
                break
    return routes


def tsp_base_split(problem: Problem, generations: int = 600, seed: int = 42) -> tuple[list[list[int]], dict]:
    from .legacy_tsp import run_base_tsp

    res = run_base_tsp(problem.dist_np, generations=generations, seed=seed)
    tour = [c for c in res.best_tour if c != 0]
    routes = split_tour_greedy(problem, tour)
    return routes, {"tsp_km": res.best_distance, "tsp_tour": res.best_tour}


# =============================================================================
# OR-Tools (opcional)
# =============================================================================
def ortools_available() -> bool:
    """OR-Tools importável *e* carregável.

    Além de não estar instalado, a DLL nativa pode ser barrada pelo sistema
    (no Windows 11, o Smart App Control bloqueia binários sem assinatura
    reconhecida). Nesses casos o comparativo segue sem o OR-Tools.
    """
    try:
        from ortools.constraint_solver import pywrapcp  # noqa: F401
        return True
    except (ImportError, OSError):
        return False


# =============================================================================
# Simulated Annealing (metaheurística de trajetória)
# =============================================================================
def simulated_annealing(
    problem: Problem,
    iterations: int = 150_000,
    seed: int = 42,
    t_inicial: float | None = None,
    t_final: float = 0.05,
    inicial: list[list[int]] | None = None,
) -> list[list[int]]:
    """Simulated Annealing (Kirkpatrick et al., 1983) com vizinhança de VRP.

    Movimentos sorteados a cada iteração: *relocate* (move uma entrega para
    outra posição/veículo compatível), *swap* (troca duas entregas) e *2-opt*
    (inverte um trecho de uma rota). Só as rotas alteradas são reavaliadas.
    Piora é aceita com probabilidade ``exp(-Δ/T)``; ``T`` cai
    geometricamente de ``t_inicial`` até ``t_final``.

    É a comparação "justa" com o GA: outra metaheurística, mesma fitness,
    mesmos movimentos elementares — a diferença é população vs. trajetória.
    """
    rng = random.Random(seed)
    rotas = [list(r) for r in (inicial or nearest_neighbor(problem, priority_first=True))]
    custos = [problem.route_cost(v, r) for v, r in enumerate(rotas)]
    atual = sum(custos)
    melhor, melhor_custo = [list(r) for r in rotas], atual
    clientes = list(range(1, problem.n + 1))

    if t_inicial is None:
        t_inicial = max(1.0, 0.02 * atual)
    alfa = (t_final / t_inicial) ** (1.0 / max(1, iterations))
    T = t_inicial

    def onde_esta(c: int) -> tuple[int, int]:
        for v, r in enumerate(rotas):
            if c in r:
                return v, r.index(c)
        raise KeyError(c)

    for _ in range(iterations):
        mov = rng.random()
        if mov < 0.45:                                  # relocate
            c = rng.choice(clientes)
            a, pa = onde_esta(c)
            b = rng.choice(problem.allowed_vehicles[c])
            nova_a = rotas[a][:pa] + rotas[a][pa + 1:]
            base_b = nova_a if b == a else rotas[b]
            pb = rng.randint(0, len(base_b))
            nova_b = base_b[:pb] + [c] + base_b[pb:]
            if b == a:
                novos = {a: nova_b}
            else:
                novos = {a: nova_a, b: nova_b}
        elif mov < 0.75:                                # swap
            c1, c2 = rng.sample(clientes, 2)
            a, pa = onde_esta(c1)
            b, pb = onde_esta(c2)
            if a == b:
                r = list(rotas[a])
                r[pa], r[pb] = r[pb], r[pa]
                novos = {a: r}
            else:
                ra, rb = list(rotas[a]), list(rotas[b])
                ra[pa], rb[pb] = c2, c1
                novos = {a: ra, b: rb}
        else:                                           # 2-opt intra-rota
            a = rng.randrange(problem.k)
            r = rotas[a]
            if len(r) < 3:
                continue
            i, j = sorted(rng.sample(range(len(r)), 2))
            novos = {a: r[:i] + r[i:j + 1][::-1] + r[j + 1:]}

        novos_custos = {v: problem.route_cost(v, r) for v, r in novos.items()}
        delta = sum(novos_custos[v] - custos[v] for v in novos)
        if delta <= 0 or rng.random() < math.exp(-delta / T):
            for v, r in novos.items():
                rotas[v] = r
                custos[v] = novos_custos[v]
            atual += delta
            if atual < melhor_custo - 1e-9:
                melhor, melhor_custo = [list(r) for r in rotas], atual
        T *= alfa
    return melhor


def ortools_solve(problem: Problem, time_limit_s: int = 20) -> list[list[int]] | None:
    """Resolve o mesmo VRP com o roteador do Google OR-Tools.

    Modelagem equivalente à nossa: capacidade por veículo, autonomia (limite
    de distância por veículo), jornada (limite de tempo), janelas de abertura
    rígidas, prazos (SLA/fim de janela) como **limite superior suave**
    ponderado pela prioridade, e compatibilidade veículo-carga. O objetivo
    nativo é distância + atraso ponderado; o termo "crítico cedo" da nossa
    fitness não tem equivalente direto e fica de fora.
    """
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    n, k = problem.n, problem.k
    manager = pywrapcp.RoutingIndexManager(n + 1, k, 0)
    routing = pywrapcp.RoutingModel(manager)

    dist_m = [[int(round(problem.D[i][j] * 1000)) for j in range(n + 1)] for i in range(n + 1)]

    def dist_cb(fi: int, ti: int) -> int:
        return dist_m[manager.IndexToNode(fi)][manager.IndexToNode(ti)]

    t_dist = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(t_dist)
    routing.AddDimensionWithVehicleCapacity(
        t_dist, 0, [int(r * 1000) for r in problem.range_km], True, "Distancia")

    def dem_cb(fi: int) -> int:
        return int(round(problem.demand[manager.IndexToNode(fi)] * 10))

    t_dem = routing.RegisterUnaryTransitCallback(dem_cb)
    routing.AddDimensionWithVehicleCapacity(
        t_dem, 0, [int(c * 10) for c in problem.capacity], True, "Carga")

    callbacks = []
    for v in range(k):
        vel = problem.speed[v]

        def tempo_cb(fi: int, ti: int, vel: float = vel) -> int:
            i, j = manager.IndexToNode(fi), manager.IndexToNode(ti)
            return int(round((problem.service[i] + problem.D[i][j] / vel) * 60))

        callbacks.append(routing.RegisterTransitCallback(tempo_cb))
    horizonte = int(max(problem.shift) * 60)
    routing.AddDimensionWithVehicleTransitAndCapacity(
        callbacks, horizonte, [int(s * 60) for s in problem.shift], True, "Tempo")
    tempo = routing.GetDimensionOrDie("Tempo")

    W = problem.weights
    for i in range(1, n + 1):
        idx = manager.NodeToIndex(i)
        tempo.CumulVar(idx).SetMin(int(problem.win_open[i] * 60))
        if problem.deadline[i] < math.inf:
            coef = max(1, int(round(1000 * W.lateness * problem.pweight[i] / 60)))
            tempo.SetCumulVarSoftUpperBound(idx, int(problem.deadline[i] * 60), coef)
        permitidos = problem.allowed_vehicles[i]
        if len(permitidos) < k:
            # Equivalente a SetAllowedVehiclesForIndex (cuja assinatura mudou no
            # OR-Tools 9.15): o domínio da variável "veículo" do nó. -1 = não
            # visitado, mantido no domínio por exigência do solver.
            routing.VehicleVar(idx).SetValues([-1] + list(permitidos))

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    params.time_limit.seconds = int(time_limit_s)
    sol = routing.SolveWithParameters(params)
    if sol is None:
        return None
    routes = []
    for v in range(k):
        idx = routing.Start(v)
        rota = []
        while not routing.IsEnd(idx):
            no = manager.IndexToNode(idx)
            if no:
                rota.append(no)
            idx = sol.Value(routing.NextVar(idx))
        routes.append(rota)
    return routes


# =============================================================================
# Registro
# =============================================================================
BASELINES: dict[str, tuple[str, Callable[..., list[list[int]]]]] = {
    "vizinho_mais_proximo": ("Vizinho mais próximo", nearest_neighbor),
    "despachante_prioridade": ("Despachante (prioridade + vizinho)",
                               lambda p: nearest_neighbor(p, priority_first=True)),
    "clarke_wright": ("Clarke & Wright (economias)", clarke_wright),
    "sweep": ("Sweep + 2-opt", sweep),
}


def run_baseline(name: str, problem: Problem, **kwargs) -> BaselineResult:
    """Executa uma abordagem pelo nome e devolve rotas + avaliação + tempo."""
    t0 = time.perf_counter()
    extra: dict = {}
    if name in BASELINES:
        rotulo, fn = BASELINES[name]
        routes = fn(problem)
    elif name == "busca_aleatoria":
        rotulo = "Busca aleatória"
        routes = random_search(problem, kwargs.get("evaluations", 50_000), kwargs.get("seed", 42))
    elif name == "simulated_annealing":
        rotulo = "Simulated Annealing"
        routes = simulated_annealing(problem, kwargs.get("iterations", 150_000),
                                     kwargs.get("seed", 42))
    elif name == "ortools":
        rotulo = "Google OR-Tools (GLS)"
        routes = ortools_solve(problem, kwargs.get("time_limit_s", 20))
        if routes is None:
            raise RuntimeError("OR-Tools não encontrou solução viável no tempo dado")
    elif name == "tsp_base_split":
        rotulo = "TSP do código base + fatiamento"
        routes, extra = tsp_base_split(problem, kwargs.get("generations", 600),
                                       kwargs.get("seed", 42))
    elif name == "melhoria_local":
        # Heurística construtiva + busca local (relocate/2-opt), sem GA.
        rotulo = "Despachante + busca local"
        routes = improve_solution(problem, nearest_neighbor(problem, priority_first=True), rounds=10)
    else:
        raise ValueError(f"abordagem desconhecida: {name}")
    dt = time.perf_counter() - t0
    return BaselineResult(rotulo, routes, problem.evaluate(routes), dt, extra)
