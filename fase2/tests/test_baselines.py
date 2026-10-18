"""Abordagens de comparação e o algoritmo do código base."""

from __future__ import annotations

import pytest

from medroute.baselines import (
    BASELINES,
    clarke_wright,
    nearest_neighbor,
    ortools_available,
    run_baseline,
    simulated_annealing,
    split_tour_greedy,
    sweep,
)
from medroute.legacy_tsp import run_base_tsp


@pytest.mark.parametrize("nome", [*BASELINES, "busca_aleatoria", "melhoria_local", "tsp_base_split"])
def test_toda_abordagem_entrega_solucao_completa(problema_padrao, nome):
    r = run_baseline(nome, problema_padrao, evaluations=2000, generations=50)
    problema_padrao.check_solution(r.routes)
    assert r.evaluation.fitness > 0
    assert r.runtime_s >= 0


def test_vizinho_mais_proximo_respeita_compatibilidade(problema_padrao):
    rotas = nearest_neighbor(problema_padrao)
    ev = problema_padrao.evaluate(rotas)
    assert sum(r.incompatible for r in ev.routes) == 0


def test_despachante_atende_criticas_primeiro(mini):
    rotas = nearest_neighbor(mini, priority_first=True)
    # V1 (refrigerada) sai primeiro: crítica (1), depois alta (3); a normal (2)
    # não cabe em nenhum veículo sem violar algo e vira "sobra" inserida no fim.
    assert rotas[0][:2] == [1, 3]
    mini.check_solution(rotas)


def test_clarke_wright_e_sweep_completos(problema_padrao):
    for fn in (clarke_wright, sweep):
        problema_padrao.check_solution(fn(problema_padrao))


def test_simulated_annealing_melhora_a_solucao_inicial(problema_padrao):
    inicial = nearest_neighbor(problema_padrao, priority_first=True)
    final = simulated_annealing(problema_padrao, iterations=20_000, seed=1, inicial=inicial)
    problema_padrao.check_solution(final)
    assert problema_padrao.routes_cost(final) < problema_padrao.routes_cost(inicial)


def test_fatiamento_do_tour_cobre_todas_as_entregas(problema_padrao):
    tour = list(range(1, problema_padrao.n + 1))
    problema_padrao.check_solution(split_tour_greedy(problema_padrao, tour))


def test_tsp_do_codigo_base(problema_padrao):
    res = run_base_tsp(problema_padrao.dist_np, generations=60, seed=1)
    assert res.best_tour[0] == 0
    assert sorted(res.best_tour) == list(range(problema_padrao.n + 1))
    assert res.history[-1] <= res.history[0]
    assert res.best_distance == pytest.approx(min(res.history))


def test_bug_do_codigo_base_prejudica_a_busca(problema_padrao):
    """Com o crossover corrigido o GA do base converge melhor (média de sementes)."""
    com_bug = [run_base_tsp(problema_padrao.dist_np, 150, seed=s, fix_crossover_bug=False).best_distance
               for s in range(4)]
    corrigido = [run_base_tsp(problema_padrao.dist_np, 150, seed=s).best_distance for s in range(4)]
    assert sum(corrigido) < sum(com_bug)


def test_abordagem_desconhecida(problema_padrao):
    with pytest.raises(ValueError):
        run_baseline("nao_existe", problema_padrao)


@pytest.mark.skipif(not ortools_available(), reason="OR-Tools indisponível neste ambiente")
def test_ortools_resolve_o_mesmo_modelo(problema_padrao):
    r = run_baseline("ortools", problema_padrao, time_limit_s=3)
    problema_padrao.check_solution(r.routes)
    assert r.evaluation.feasible
