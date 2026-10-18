"""
Busca local para o GA **memético** (GA + refinamento local).

O GA é bom em achar a "região" certa do espaço de soluções (quem vai em qual
veículo), mas lento para acertar detalhes finos de ordem. Duas buscas locais
clássicas resolvem isso, sempre avaliadas com a **fitness exata da rota**
(enxergam prioridade, janelas e autonomia — não só distância):

* **2-opt intra-rota**: inverte um trecho da rota se isso reduzir o custo
  (desfaz cruzamentos de caminho).
* **Relocate inter-rotas**: move uma entrega para outra posição, inclusive em
  outro veículo, se reduzir o custo total.

São aplicadas ao melhor indivíduo periodicamente e ao final da evolução.
"""

from __future__ import annotations

from ..problem import Problem


def two_opt_route(problem: Problem, v: int, route: list[int], max_passes: int = 50) -> list[int]:
    """2-opt de primeira melhora numa rota (devolve uma nova lista)."""
    melhor = list(route)
    if len(melhor) < 3:
        return melhor
    custo = problem.route_cost(v, melhor)
    for _ in range(max_passes):
        melhorou = False
        n = len(melhor)
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = melhor[:i] + melhor[i:j + 1][::-1] + melhor[j + 1:]
                c = problem.route_cost(v, cand)
                if c < custo - 1e-9:
                    melhor, custo = cand, c
                    melhorou = True
                    break
            if melhorou:
                break
        if not melhorou:
            break
    return melhor


def relocate(problem: Problem, routes: list[list[int]], max_passes: int = 20) -> list[list[int]]:
    """Move entregas entre/dentro de rotas enquanto houver melhora (first improvement)."""
    rotas = [list(r) for r in routes]
    custos = [problem.route_cost(v, r) for v, r in enumerate(rotas)]
    for _ in range(max_passes):
        melhorou = False
        for a in range(problem.k):
            for pos in range(len(rotas[a])):
                cliente = rotas[a][pos]
                origem = rotas[a][:pos] + rotas[a][pos + 1:]
                custo_origem = problem.route_cost(a, origem)
                ganho_remocao = custos[a] - custo_origem
                for b in problem.allowed_vehicles[cliente]:
                    base = origem if b == a else rotas[b]
                    custo_b = custo_origem if b == a else custos[b]
                    for p in range(len(base) + 1):
                        if b == a and p == pos:
                            continue
                        nova = base[:p] + [cliente] + base[p:]
                        c = problem.route_cost(b, nova)
                        if c - custo_b < ganho_remocao - 1e-9:
                            if b == a:
                                rotas[a] = nova
                                custos[a] = c
                            else:
                                rotas[a] = origem
                                custos[a] = custo_origem
                                rotas[b] = nova
                                custos[b] = c
                            melhorou = True
                            break
                    if melhorou:
                        break
                if melhorou:
                    break
            if melhorou:
                break
        if not melhorou:
            break
    return rotas


def swap_between(problem: Problem, routes: list[list[int]], max_passes: int = 10) -> list[list[int]]:
    """Troca duas entregas de veículos diferentes, mantendo as posições (exchange)."""
    rotas = [list(r) for r in routes]
    custos = [problem.route_cost(v, r) for v, r in enumerate(rotas)]
    for _ in range(max_passes):
        melhorou = False
        for a in range(problem.k):
            for b in range(a + 1, problem.k):
                for i, ca in enumerate(rotas[a]):
                    if not problem.compat[b][ca]:
                        continue
                    for j, cb in enumerate(rotas[b]):
                        if not problem.compat[a][cb]:
                            continue
                        na = rotas[a][:i] + [cb] + rotas[a][i + 1:]
                        nb = rotas[b][:j] + [ca] + rotas[b][j + 1:]
                        c_a, c_b = problem.route_cost(a, na), problem.route_cost(b, nb)
                        if c_a + c_b < custos[a] + custos[b] - 1e-9:
                            rotas[a], rotas[b] = na, nb
                            custos[a], custos[b] = c_a, c_b
                            melhorou = True
                            break
                    if melhorou:
                        break
                if melhorou:
                    break
            if melhorou:
                break
        if not melhorou:
            break
    return rotas


def improve_solution(problem: Problem, routes: list[list[int]], rounds: int = 3) -> list[list[int]]:
    """Alterna relocate, troca entre rotas e 2-opt até estabilizar."""
    atual = [list(r) for r in routes]
    custo = problem.routes_cost(atual)
    for _ in range(rounds):
        atual = relocate(problem, atual)
        atual = swap_between(problem, atual)
        atual = [two_opt_route(problem, v, r) for v, r in enumerate(atual)]
        novo = problem.routes_cost(atual)
        if novo >= custo - 1e-9:
            break
        custo = novo
    return atual
