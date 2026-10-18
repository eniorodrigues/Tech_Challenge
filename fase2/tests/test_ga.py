"""Motor do algoritmo genético."""

from __future__ import annotations

import pytest

from medroute.baselines import random_search
from medroute.ga import GAConfig, GeneticAlgorithm
from medroute.ga.representation import is_valid


def _rodar(problema, **kw):
    return GeneticAlgorithm(problema, GAConfig(**kw)).run()


def test_mesma_semente_mesmo_resultado(problema_padrao):
    a = _rodar(problema_padrao, generations=40, seed=3)
    b = _rodar(problema_padrao, generations=40, seed=3)
    assert a.best_chromosome == b.best_chromosome
    assert a.best_fitness == b.best_fitness


def test_ga_evolui_a_partir_de_populacao_aleatoria(problema_padrao):
    res = _rodar(problema_padrao, generations=120, seed=1, heuristic_seeds=False,
                 local_search=False, final_polish=False, patience=None)
    inicial, final = res.history[0].best, res.history[-1].best
    assert final < inicial * 0.2                      # melhora de pelo menos 5x
    melhores = [h.best for h in res.history]
    assert all(b <= a + 1e-9 for a, b in zip(melhores, melhores[1:]))  # elitismo: nunca piora


@pytest.mark.slow
def test_ga_encontra_solucao_viavel_no_cenario_padrao(problema_padrao):
    res = _rodar(problema_padrao, generations=150, seed=2)
    assert res.evaluation.feasible
    assert is_valid(res.best_chromosome, problema_padrao)
    problema_padrao.check_solution(res.best_routes)


@pytest.mark.slow
def test_ga_vence_busca_aleatoria_com_mesmo_orcamento(problema_padrao):
    res = _rodar(problema_padrao, generations=80, seed=4, heuristic_seeds=False,
                 local_search=False, final_polish=False, patience=None)
    aleatoria = random_search(problema_padrao, evaluations=res.evaluations, seed=4)
    assert res.best_fitness < problema_padrao.routes_cost(aleatoria) / 5


def test_callback_pode_interromper(problema_padrao):
    vistos = []

    def cb(stats, rotas):
        vistos.append(stats.generation)
        return stats.generation < 4

    res = GeneticAlgorithm(problema_padrao, GAConfig(generations=100, seed=1), cb).run()
    assert res.stop_reason == "interrompido pelo usuário"
    assert vistos[-1] == 4 and res.generations_run == 5


def test_limite_de_tempo(problema_padrao):
    res = _rodar(problema_padrao, generations=10_000, seed=1, time_limit_s=1.0, patience=None)
    assert "limite de tempo" in res.stop_reason
    assert res.runtime_s < 6


def test_paciencia_encerra_sem_melhora(problema_padrao):
    res = _rodar(problema_padrao, generations=5000, seed=1, patience=15)
    assert "sem melhora" in res.stop_reason
    assert res.generations_run < 5000


def test_snapshots_registram_melhorias(problema_padrao):
    res = _rodar(problema_padrao, generations=60, seed=6)
    fits = [s.fitness for s in res.snapshots]
    assert fits == sorted(fits, reverse=True)
    for s in res.snapshots:
        problema_padrao.check_solution(s.routes)


def test_configuracao_estilo_codigo_base_roda(problema_padrao):
    cfg = GAConfig.base_code_like(generations=30, seed=1)
    assert cfg.crossover == "ox" and cfg.mutation == "adjacent_swap" and cfg.selection == "roulette"
    res = GeneticAlgorithm(problema_padrao, cfg).run()
    assert res.generations_run == 30


@pytest.mark.parametrize("crossover", ["ox", "pmx", "erx", "bcrc"])
@pytest.mark.parametrize("selecao", ["tournament", "roulette", "rank", "truncation"])
def test_todas_as_combinacoes_de_operadores(problema_padrao, crossover, selecao):
    res = _rodar(problema_padrao, generations=8, seed=1, crossover=crossover, selection=selecao,
                 local_search=False, final_polish=False)
    assert is_valid(res.best_chromosome, problema_padrao)


def test_operador_desconhecido_falha_cedo(problema_padrao):
    with pytest.raises(ValueError):
        GeneticAlgorithm(problema_padrao, GAConfig(crossover="xyz"))
    with pytest.raises(ValueError):
        GeneticAlgorithm(problema_padrao, GAConfig(selection="xyz"))


def test_tsp_puro_com_um_veiculo(mini):
    """Com K = 1 o problema vira o TSP do código base (sem separadores)."""
    from dataclasses import replace

    from medroute.problem import Problem

    sc = replace(mini.scenario, vehicles=[mini.scenario.vehicles[0]])
    p = Problem(sc, distance_matrix=mini.dist_np)
    assert p.chromosome_length == 3
    res = GeneticAlgorithm(p, GAConfig(generations=20, seed=1, population_size=20)).run()
    assert sorted(res.best_chromosome) == [1, 2, 3]
