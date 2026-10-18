"""
Operadores genéticos: seleção, cruzamento (crossover) e mutação.

Todos recebem um ``random.Random`` explícito (reprodutibilidade) e devolvem
**novos** cromossomos — nunca alteram os pais.

Origem de cada operador
-----------------------
=======================  =====================================================
Do código base           ``order_crossover`` (OX, mesma variante do base, que
                         preenche da esquerda para a direita),
                         ``adjacent_swap_mutation`` (troca de vizinhos) e a
                         seleção por roleta com peso ``1/fitness``.
Clássicos de permutação  PMX, ERX (Edge Recombination), swap, inversão
                         (o TODO do código base), inserção, scramble.
Especializados p/ VRP    ``best_cost_route_crossover`` (BCRC), mutação de
                         prioridade e mutação de reparo de restrições.
=======================  =====================================================
"""

from __future__ import annotations

import math
import random
from typing import Callable, Sequence

from ..problem import Problem

Chromosome = list[int]


# =============================================================================
# SELEÇÃO
# =============================================================================
class Selector:
    """Interface: ``prepare`` uma vez por geração, ``select`` várias vezes."""

    name = "base"

    def prepare(self, population: Sequence[Chromosome], fitness: Sequence[float]) -> None:
        self.population = population
        self.fitness = fitness

    def select(self, rng: random.Random) -> Chromosome:  # pragma: no cover
        raise NotImplementedError


class TournamentSelector(Selector):
    """Torneio: sorteia ``k`` indivíduos e fica com o melhor.

    A pressão seletiva é controlada por ``k`` e não depende da escala da
    fitness — importante aqui, onde penalidades criam saltos de milhares.
    """

    name = "torneio"

    def __init__(self, k: int = 3) -> None:
        self.k = k

    def select(self, rng: random.Random) -> Chromosome:
        n = len(self.population)
        melhor = rng.randrange(n)
        for _ in range(self.k - 1):
            i = rng.randrange(n)
            if self.fitness[i] < self.fitness[melhor]:
                melhor = i
        return self.population[melhor]


class RouletteSelector(Selector):
    """Roleta com probabilidade proporcional a ``1/fitness`` (como no código base)."""

    name = "roleta"

    def prepare(self, population, fitness) -> None:
        super().prepare(population, fitness)
        pesos = [1.0 / max(f, 1e-9) for f in fitness]
        acum = []
        s = 0.0
        for p in pesos:
            s += p
            acum.append(s)
        self._acum = acum

    def select(self, rng: random.Random) -> Chromosome:
        return rng.choices(self.population, cum_weights=self._acum, k=1)[0]


class RankSelector(Selector):
    """Seleção por ranking linear (pressão ``s`` entre 1 e 2).

    Requer a população **ordenada** (melhor primeiro), como o motor entrega.
    """

    name = "ranking"

    def __init__(self, pressure: float = 1.7) -> None:
        self.s = pressure

    def prepare(self, population, fitness) -> None:
        super().prepare(population, fitness)
        n = len(population)
        acum = []
        tot = 0.0
        for i in range(n):  # i = 0 é o melhor
            p = (2 - self.s) / n + 2 * (n - 1 - i) * (self.s - 1) / (n * (n - 1)) if n > 1 else 1.0
            tot += p
            acum.append(tot)
        self._acum = acum

    def select(self, rng: random.Random) -> Chromosome:
        return rng.choices(self.population, cum_weights=self._acum, k=1)[0]


class TruncationSelector(Selector):
    """Sorteio uniforme entre os ``top`` melhores (seleção original do base)."""

    name = "truncamento"

    def __init__(self, top: int = 10) -> None:
        self.top = top

    def select(self, rng: random.Random) -> Chromosome:
        return self.population[rng.randrange(min(self.top, len(self.population)))]


def make_selector(name: str, **kw) -> Selector:
    nome = name.lower()
    if nome in ("tournament", "torneio"):
        return TournamentSelector(kw.get("k", 3))
    if nome in ("roulette", "roleta"):
        return RouletteSelector()
    if nome in ("rank", "ranking"):
        return RankSelector(kw.get("pressure", 1.7))
    if nome in ("truncation", "truncamento", "top"):
        return TruncationSelector(kw.get("top", 10))
    raise ValueError(f"seleção desconhecida: {name}")


# =============================================================================
# CRUZAMENTO
# =============================================================================
def _cortes(n: int, rng: random.Random) -> tuple[int, int]:
    """Dois pontos de corte ``a < b`` (mesma regra do código base)."""
    a = rng.randint(0, n - 1)
    b = rng.randint(a + 1, n)
    return a, b


def order_crossover(p1: Sequence[int], p2: Sequence[int], rng: random.Random) -> Chromosome:
    """OX — Order Crossover, na variante do código base.

    Copia o trecho ``p1[a:b]`` para a mesma posição do filho e preenche as
    demais posições, da esquerda para a direita, com os genes de ``p2`` na
    ordem em que aparecem. Preserva a **ordem relativa** — o que importa
    numa rota.

    Correção em relação ao base: o ``tsp.py`` original chamava
    ``order_crossover(parent1, parent1)``, ou seja, cruzava o pai com ele
    mesmo e o filho saía idêntico ao pai — na prática não havia crossover.
    """
    n = len(p1)
    a, b = _cortes(n, rng)
    trecho = p1[a:b]
    no_trecho = set(trecho)
    resto = [g for g in p2 if g not in no_trecho]
    return list(resto[:a]) + list(trecho) + list(resto[a:])


def pmx_crossover(p1: Sequence[int], p2: Sequence[int], rng: random.Random) -> Chromosome:
    """PMX — Partially Mapped Crossover (Goldberg & Lingle, 1985).

    Copia ``p1[a:b]`` e resolve conflitos pelo mapeamento entre os trechos;
    preserva **posições absolutas** de ``p2`` sempre que possível.
    """
    n = len(p1)
    a, b = _cortes(n, rng)
    filho: list[int | None] = [None] * n
    filho[a:b] = p1[a:b]
    pos2 = {g: i for i, g in enumerate(p2)}
    seg = set(p1[a:b])
    for i in range(a, b):
        g = p2[i]
        if g in seg:
            continue
        j = i
        while a <= j < b:
            j = pos2[p1[j]]
        filho[j] = g
    for i in range(n):
        if filho[i] is None:
            filho[i] = p2[i]
    return filho  # type: ignore[return-value]


def edge_recombination(p1: Sequence[int], p2: Sequence[int], rng: random.Random) -> Chromosome:
    """ERX — Edge Recombination (Whitley et al., 1989).

    Monta a tabela de vizinhança dos dois pais e constrói o filho sempre
    seguindo uma aresta herdada, preferindo o vizinho com menos opções. Para
    TSP é o crossover que melhor preserva **adjacências** (quem vem depois de
    quem), que é exatamente o que define o custo de uma rota.
    """
    n = len(p1)
    viz: dict[int, set[int]] = {g: set() for g in p1}
    for pai in (p1, p2):
        for i, g in enumerate(pai):
            viz[g].add(pai[i - 1])
            viz[g].add(pai[(i + 1) % n])

    atual = p1[0] if rng.random() < 0.5 else p2[0]
    filho = [atual]
    restantes = set(p1)
    restantes.discard(atual)
    while restantes:
        # A tabela é simétrica: só os vizinhos de `atual` o têm na lista.
        for vizinho in viz[atual]:
            viz[vizinho].discard(atual)
        candidatos = list(viz[atual])
        if candidatos:
            menor = min(len(viz[c]) for c in candidatos)
            empatados = [c for c in candidatos if len(viz[c]) == menor]
            atual = rng.choice(empatados)
        else:
            atual = rng.choice(tuple(restantes))
        filho.append(atual)
        restantes.discard(atual)
    return filho


def cheapest_insertion(
    problem: Problem,
    routes: list[list[int]],
    customer: int,
    loads: list[float] | None = None,
    exact_candidates: int = 3,
    route_costs: list[float] | None = None,
) -> None:
    """Insere ``customer`` na posição de menor custo (in place).

    Duas etapas, para ser rápida o bastante para rodar dentro do GA:

    1. triagem barata pelo acréscimo de distância ``d(a,c) + d(c,b) - d(a,b)``
       em todas as posições de todos os veículos **compatíveis** (veículos
       onde a carga cabe têm preferência);
    2. as ``exact_candidates`` melhores posições — mais o início de cada rota
       quando a entrega tem prazo apertado — são reavaliadas com a fitness
       exata da rota (que enxerga prioridade, janelas e autonomia).
    """
    D = problem.D
    if loads is None:
        loads = [sum(problem.demand[i] for i in r) for r in routes]
    dem = problem.demand[customer]
    permitidos = problem.allowed_vehicles[customer] or list(range(problem.k))
    cabem = [v for v in permitidos if loads[v] + dem <= problem.capacity[v] + 1e-9]
    veiculos = cabem or permitidos

    candidatos: list[tuple[float, int, int]] = []
    for v in veiculos:
        r = routes[v]
        anterior = 0
        for p in range(len(r) + 1):
            proximo = r[p] if p < len(r) else 0
            delta = D[anterior][customer] + D[customer][proximo] - D[anterior][proximo]
            candidatos.append((delta, v, p))
            anterior = proximo
    candidatos.sort()
    finalistas = {(v, p) for _, v, p in candidatos[:exact_candidates]}
    if problem.pweight[customer] >= 3.0:  # prioridade alta/crítica: testa o início
        for v in veiculos:
            finalistas.add((v, 0))

    if route_costs is None:
        custo_atual = {v: problem.route_cost(v, routes[v]) for v in {v for v, _ in finalistas}}
    else:
        custo_atual = route_costs
    melhor = (math.inf, veiculos[0], 0, 0.0)
    for v, p in finalistas:
        r = routes[v]
        novo_custo = problem.route_cost(v, r[:p] + [customer] + r[p:])
        delta = novo_custo - custo_atual[v]
        if delta < melhor[0]:
            melhor = (delta, v, p, novo_custo)
    _, v, p, novo_custo = melhor
    routes[v].insert(p, customer)
    loads[v] += dem
    if route_costs is not None:
        route_costs[v] = novo_custo


def best_cost_route_crossover(
    p1: Sequence[int], p2: Sequence[int], rng: random.Random, problem: Problem,
) -> Chromosome:
    """BCRC — Best Cost Route Crossover (Ombuki, Ross & Hanshar, 2006).

    Operador **específico de VRP**: herda as rotas de ``p1``, retira delas os
    clientes de uma rota sorteada de ``p2`` e os reinsere um a um na posição
    de menor custo (:func:`cheapest_insertion`). Transmite ao filho um
    "agrupamento" bom de ``p2`` sem destruir a estrutura de ``p1``.
    """
    r1 = problem.decode(p1)
    r2 = [r for r in problem.decode(p2) if r]
    if not r2:
        return list(p1)
    doadora = rng.choice(r2)
    removidos = set(doadora)
    filho = [[g for g in r if g not in removidos] for r in r1]
    ordem = list(doadora)
    rng.shuffle(ordem)
    cargas = [sum(problem.demand[i] for i in r) for r in filho]
    custos = [problem.route_cost(v, r) for v, r in enumerate(filho)]
    for c in ordem:
        cheapest_insertion(problem, filho, c, cargas, route_costs=custos)
    return problem.encode(filho)


CROSSOVERS: dict[str, Callable[..., Chromosome]] = {
    "ox": order_crossover,
    "pmx": pmx_crossover,
    "erx": edge_recombination,
    "bcrc": best_cost_route_crossover,
}
PRECISA_PROBLEMA = {"bcrc"}


# =============================================================================
# MUTAÇÃO
# =============================================================================
def adjacent_swap_mutation(ch: Sequence[int], rng: random.Random) -> Chromosome:
    """Troca dois genes vizinhos — a mutação original do código base."""
    out = list(ch)
    if len(out) >= 2:
        i = rng.randrange(len(out) - 1)
        out[i], out[i + 1] = out[i + 1], out[i]
    return out


def swap_mutation(ch: Sequence[int], rng: random.Random) -> Chromosome:
    """Troca duas posições quaisquer (pode trocar entregas entre veículos)."""
    out = list(ch)
    if len(out) >= 2:
        i, j = rng.sample(range(len(out)), 2)
        out[i], out[j] = out[j], out[i]
    return out


def inversion_mutation(ch: Sequence[int], rng: random.Random) -> Chromosome:
    """Inverte um trecho — o movimento 2-opt (o TODO do código base).

    Dentro de uma rota desfaz cruzamentos; se o trecho contém separador,
    troca as caudas de duas rotas (2-opt*).
    """
    out = list(ch)
    if len(out) >= 2:
        i, j = sorted(rng.sample(range(len(out)), 2))
        out[i:j + 1] = out[i:j + 1][::-1]
    return out


def insertion_mutation(ch: Sequence[int], rng: random.Random) -> Chromosome:
    """Retira um gene e o reinsere noutra posição (relocate / or-opt de 1)."""
    out = list(ch)
    if len(out) >= 2:
        i, j = rng.sample(range(len(out)), 2)
        g = out.pop(i)
        out.insert(j, g)
    return out


def scramble_mutation(ch: Sequence[int], rng: random.Random) -> Chromosome:
    """Embaralha um trecho curto (até 5 genes) — perturbação para diversidade."""
    out = list(ch)
    if len(out) >= 3:
        tam = rng.randint(3, min(5, len(out)))
        i = rng.randrange(len(out) - tam + 1)
        trecho = out[i:i + tam]
        rng.shuffle(trecho)
        out[i:i + tam] = trecho
    return out


def priority_mutation(ch: Sequence[int], rng: random.Random, problem: Problem) -> Chromosome:
    """Antecipa uma entrega crítica/alta dentro da própria rota.

    Escolhe uma entrega prioritária que não seja a primeira da rota e a move
    para uma posição anterior (com viés para o começo). É o operador que
    "entende" o termo de prioridade da fitness.
    """
    out = list(ch)
    n = problem.n
    candidatos = []
    inicio_rota = 0
    for idx, g in enumerate(out):
        if g > n:
            inicio_rota = idx + 1
            continue
        if problem.pweight[g] >= 3.0 and idx > inicio_rota:
            candidatos.append((idx, inicio_rota))
    if not candidatos:
        return out
    idx, ini = rng.choice(candidatos)
    destino = ini + int((idx - ini) * rng.random() ** 2)  # viés para o início
    g = out.pop(idx)
    out.insert(destino, g)
    return out


def repair_mutation(ch: Sequence[int], rng: random.Random, problem: Problem) -> Chromosome:
    """Reparo dirigido: tira uma entrega de uma rota que viola restrição dura
    e a reinsere onde for mais barato (compatível e com folga de carga).

    * incompatibilidade (ex.: insulina na van sem refrigeração) → move a
      entrega incompatível;
    * capacidade / autonomia / jornada estourada → move uma entrega
      sorteada com peso proporcional à carga (capacidade) ou ao desvio que
      ela causa na rota (autonomia/jornada).
    """
    routes = problem.decode(ch)
    ruins = []
    for v, r in enumerate(routes):
        if not r:
            continue
        incompat = [i for i in r if not problem.compat[v][i]]
        if incompat:
            ruins.append((v, incompat))
            continue
        res = problem.evaluate_route(v, r)
        if res.capacity_excess > 1e-9:
            ruins.append((v, r))
        elif res.range_excess > 1e-9 or res.shift_excess > 1e-9:
            ruins.append((v, r))
    if not ruins:
        return list(ch)

    v, alvo = rng.choice(ruins)
    r = routes[v]
    if alvo is r:
        D = problem.D
        pesos = []
        for p, i in enumerate(r):
            a = r[p - 1] if p > 0 else 0
            b = r[p + 1] if p + 1 < len(r) else 0
            desvio = D[a][i] + D[i][b] - D[a][b]
            pesos.append(desvio + problem.demand[i] / 10.0 + 1e-6)
        escolhido = rng.choices(r, weights=pesos, k=1)[0]
    else:
        escolhido = rng.choice(alvo)
    r.remove(escolhido)
    cheapest_insertion(problem, routes, escolhido)
    return problem.encode(routes)


MUTATIONS: dict[str, Callable[..., Chromosome]] = {
    "adjacent_swap": adjacent_swap_mutation,
    "swap": swap_mutation,
    "inversion": inversion_mutation,
    "insertion": insertion_mutation,
    "scramble": scramble_mutation,
    "priority": priority_mutation,
    "repair": repair_mutation,
}
MUTACAO_PRECISA_PROBLEMA = {"priority", "repair"}
