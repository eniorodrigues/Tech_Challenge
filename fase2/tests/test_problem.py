"""Função fitness: contas exatas numa instância construída à mão.

Instância ``mini`` (ver conftest): 3 entregas, 2 veículos, 1 km/min.
Entrega 1 = crítica e refrigerada; 2 = normal; 3 = alta. Todas com 10 kg.
"""

from __future__ import annotations

import random
from dataclasses import replace

import numpy as np
import pytest

from medroute.ga.representation import random_chromosome
from medroute.problem import Problem


def test_decode_encode_ida_e_volta(mini):
    assert mini.decode([1, 2, 4, 3]) == [[1, 2], [3]]
    assert mini.decode([4, 1, 2, 3]) == [[], [1, 2, 3]]
    assert mini.encode([[1, 2], [3]]) == [1, 2, 4, 3]
    assert mini.chromosome_length == 4


def test_custo_de_solucao_viavel_conferido_a_mao(mini):
    # V1 [1,2]: 40 km; prioridade 10*10 + 1*20 = 120 peso·min -> 2,0
    assert mini.route_cost(0, [1, 2]) == pytest.approx(42.0)
    # V2 [3]: 20 km; prioridade 3*10 = 30 -> 0,5
    assert mini.route_cost(1, [3]) == pytest.approx(20.5)
    assert mini.fitness([1, 2, 4, 3]) == pytest.approx(62.5)
    ev = mini.evaluate([[1, 2], [3]])
    assert ev.feasible and ev.n_violations == 0
    assert ev.distance_km == pytest.approx(60.0)


def test_penalidade_de_capacidade(mini):
    # 30 kg num veículo de 25 kg: 1000 + 50 * 5 de penalidade
    assert mini.route_cost(0, [1, 2, 3]) == pytest.approx(40 + 210 / 60 + 1000 + 250)
    rr = mini.evaluate_route(0, [1, 2, 3])
    assert rr.capacity_excess == pytest.approx(5.0)
    assert rr.violations == {"capacidade_kg": 5.0}


def test_penalidade_de_compatibilidade_cadeia_fria(mini):
    # Insulina (refrigerada) na moto sem refrigeração
    assert mini.route_cost(1, [1]) == pytest.approx(20 + 100 / 60 + 1000 + 400)
    assert mini.evaluate_route(1, [1]).incompatible == 1


def test_penalidade_de_autonomia(mini):
    # Moto vai até a entrega 2 (20 km) e volta: 40 km > autonomia de 30 km
    rr = mini.evaluate_route(1, [2])
    assert rr.range_excess == pytest.approx(10.0)
    assert mini.route_cost(1, [2]) == pytest.approx(40 + 20 / 60 + 1000 + 500)


def test_prioridade_critica_cedo_custa_menos(mini):
    critico_primeiro = mini.route_cost(0, [1, 3])
    critico_por_ultimo = mini.route_cost(0, [3, 1])
    assert critico_primeiro == pytest.approx(40 + 190 / 60)
    assert critico_por_ultimo == pytest.approx(40 + 330 / 60)
    assert critico_primeiro < critico_por_ultimo


def test_atraso_ponderado_pela_prioridade(mini):
    sc = mini.scenario
    entregas = list(sc.deliveries)
    entregas[1] = replace(entregas[1], window=(0.0, 15.0))   # entrega 2 até t=15
    p = Problem(replace(sc, deliveries=entregas), distance_matrix=mini.dist_np)
    rr = p.evaluate_route(0, [1, 2])
    assert rr.stop_results[1].lateness == pytest.approx(5.0)
    assert rr.lateness_cost == pytest.approx(5.0)            # peso normal = 1
    assert p.route_cost(0, [1, 2]) == pytest.approx(42.0 + 5.0)


def test_espera_pela_abertura_da_janela(mini):
    sc = mini.scenario
    entregas = list(sc.deliveries)
    entregas[2] = replace(entregas[2], window=(30.0, 480.0))
    p = Problem(replace(sc, deliveries=entregas), distance_matrix=mini.dist_np)
    rr = p.evaluate_route(1, [3])
    s = rr.stop_results[0]
    assert s.arrival == pytest.approx(10.0)
    assert s.wait == pytest.approx(20.0) and s.start == pytest.approx(30.0)
    assert rr.duration_min == pytest.approx(40.0)
    assert p.route_cost(1, [3]) == pytest.approx(20 + 90 / 60)


def test_penalidade_de_jornada(mini):
    p = Problem(replace(mini.scenario, shift_minutes=30.0), distance_matrix=mini.dist_np)
    rr = p.evaluate_route(0, [1, 2])
    assert rr.shift_excess == pytest.approx(10.0)
    assert p.route_cost(0, [1, 2]) == pytest.approx(42.0 + 1000 + 5 * 10)


def test_check_solution_rejeita_entrega_faltando_ou_repetida(mini):
    with pytest.raises(ValueError):
        mini.evaluate([[1, 2], [2]])
    with pytest.raises(ValueError):
        mini.evaluate([[1], [3]])


def test_avaliacao_rapida_e_detalhada_sempre_concordam(problema_padrao):
    """As duas implementações da fitness precisam dar o mesmo número."""
    rng = random.Random(0)
    for _ in range(300):
        ch = random_chromosome(problema_padrao, rng)
        rapida = problema_padrao.fitness(ch)
        detalhada = problema_padrao.evaluate_chromosome(ch).fitness
        assert rapida == pytest.approx(detalhada, rel=1e-12, abs=1e-9)


def test_penalty_soma_somente_restricoes_duras(problema_padrao):
    rng = random.Random(1)
    ev = problema_padrao.evaluate_chromosome(random_chromosome(problema_padrao, rng))
    w = problema_padrao.weights
    sem_penalidade = sum(
        w.distance * r.distance_km + w.priority_time * r.priority_cost / 60 + w.lateness * r.lateness_cost
        for r in ev.routes)
    assert ev.fitness == pytest.approx(sem_penalidade + ev.penalty)


def test_matriz_customizada_e_usada(mini):
    assert np.allclose(mini.dist_np[0], [0, 10, 20, 10])
