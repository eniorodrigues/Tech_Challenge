"""Plano de rotas e KPIs de negócio."""

from __future__ import annotations

import json

import pytest

from medroute.plan import CUSTO_HORA_MOTORISTA, RoutePlan


def test_kpis_batem_com_as_rotas(plano_padrao):
    ga, _ = plano_padrao
    k = ga.kpis
    assert k.total_km == pytest.approx(sum(r.distance_km for r in ga.routes), abs=0.06)
    assert k.deliveries == len(ga.scenario.deliveries)
    assert 0 <= k.on_time_pct <= 100
    assert k.late_count == sum(not s.on_time for r in ga.routes for s in r.stops)
    custo_km = sum(r.distance_km * ga.scenario.vehicle_by_id(r.vehicle_id).cost_per_km
                   for r in ga.routes)
    custo_mot = sum(r.duration_min / 60 * CUSTO_HORA_MOTORISTA for r in ga.routes if r.used)
    assert k.cost_total_brl == pytest.approx(custo_km + custo_mot, abs=0.05)


def test_horarios_das_paradas_sao_consistentes(plano_padrao):
    ga, _ = plano_padrao
    for r in ga.routes:
        anteriores = "07:00"
        for s in r.stops:
            assert s.arrival <= s.start <= s.departure
            assert s.start >= anteriores
            anteriores = s.departure
            if s.lateness_min > 0:
                assert not s.on_time


def test_comparacao_com_processo_atual(plano_padrao):
    ga, atual = plano_padrao
    eco = ga.compare(atual)
    assert eco["km_economizados"] == pytest.approx(atual.kpis.total_km - ga.kpis.total_km, abs=0.11)
    assert eco["pontos_sla"] == pytest.approx(ga.kpis.on_time_pct - atual.kpis.on_time_pct, abs=0.11)
    assert ga.kpis.fitness < atual.kpis.fitness          # o GA vence o despachante


def test_exportacao_json_e_tabela(plano_padrao):
    ga, _ = plano_padrao
    d = json.loads(ga.to_json(include_scenario=True))
    assert d["kpis"]["deliveries"] == 36
    assert len(d["routes"]) == 5 and "scenario" in d
    linhas = ga.schedule_rows()
    assert len(linhas) == 36
    assert {"veiculo", "entrega", "chegada", "prioridade"} <= set(linhas[0])
    assert "km" in ga.summary_text()


def test_busca_de_parada_por_id_e_por_nome(plano_padrao):
    ga, _ = plano_padrao
    r, s = ga.find_stop("E25")
    assert s.delivery_id == "E25"
    nome = s.name.split(" (")[0]
    r2, s2 = ga.find_stop(nome)
    assert s2.delivery_id == "E25"
    assert ga.find_stop("inexistente") is None
    with pytest.raises(KeyError):
        ga.route("V99")


def test_plano_de_rotas_reconstroi_a_partir_da_avaliacao(problema_padrao, plano_padrao):
    ga, _ = plano_padrao
    rotas = [[int(s.delivery_id[1:]) for s in r.stops] for r in ga.routes]
    ev = problema_padrao.evaluate(rotas)
    novo = RoutePlan.from_evaluation(problema_padrao, ev, "x")
    assert novo.kpis.total_km == ga.kpis.total_km
    assert novo.kpis.fitness == ga.kpis.fitness
