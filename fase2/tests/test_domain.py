"""Entidades, cenário sintético e geometria."""

from __future__ import annotations

import json

import numpy as np
import pytest

from medroute.domain import CONTROLADO, REFRIGERADO, Priority, Scenario, Vehicle
from medroute.geo import distance_matrix_km, haversine_km
from medroute.scenario import FROTA_PADRAO, generate_scenario, weekly_scenarios


def test_priority_parse_aceita_varias_grafias():
    assert Priority.parse("CRÍTICA") is Priority.CRITICAL
    assert Priority.parse("critica") is Priority.CRITICAL
    assert Priority.parse("HIGH") is Priority.HIGH
    assert Priority.parse(1) is Priority.NORMAL
    assert Priority.CRITICAL.label == "CRÍTICA"


def test_compatibilidade_e_subconjunto_de_recursos():
    from medroute.domain import Delivery

    van_fria = FROTA_PADRAO[0]
    moto = FROTA_PADRAO[4]
    insulina = Delivery("E1", "x", "UBS", 0, 0, Priority.CRITICAL, 1, frozenset({REFRIGERADO}))
    morfina = Delivery("E2", "y", "UPA", 0, 0, Priority.HIGH, 1, frozenset({CONTROLADO}))
    luvas = Delivery("E3", "z", "UBS", 0, 0, Priority.NORMAL, 1)
    assert van_fria.can_carry(insulina) and van_fria.can_carry(morfina)
    assert not moto.can_carry(insulina) and not moto.can_carry(morfina)
    assert moto.can_carry(luvas)


def test_cenario_padrao_e_viavel_e_coerente(cenario_padrao):
    sc = cenario_padrao
    assert sc.validate() == []
    assert len(sc.deliveries) == 36 and len(sc.vehicles) == 5
    assert sc.total_demand_kg < sc.total_capacity_kg
    for d in sc.deliveries:
        assert any(v.can_carry(d) for v in sc.vehicles)
        assert d.window[0] < d.window[1]
        if d.priority is Priority.CRITICAL:
            # críticos podem ser atendidos desde a saída (janela abre no 0)
            assert d.window[0] == 0
        if d.priority is Priority.HIGH:
            # janela abre com folga antes do SLA de 4 h
            assert d.window[0] <= 120


def test_gerador_e_reprodutivel():
    a = generate_scenario(seed=7).to_dict()
    b = generate_scenario(seed=7).to_dict()
    c = generate_scenario(seed=8).to_dict()
    assert a == b
    assert a != c


def test_utilizacao_alvo_calibra_a_carga():
    sc = generate_scenario(seed=3, utilizacao_alvo=0.5)
    assert sc.total_demand_kg == pytest.approx(0.5 * sc.total_capacity_kg, rel=0.03)


def test_json_ida_e_volta_preserva_cenario(cenario_padrao, tmp_path):
    caminho = tmp_path / "cenario.json"
    cenario_padrao.to_json(caminho)
    volta = Scenario.from_json(caminho)
    assert volta.to_dict() == cenario_padrao.to_dict()
    json.loads(caminho.read_text(encoding="utf-8"))  # JSON válido


def test_relogio_converte_minutos_do_turno(cenario_padrao):
    assert cenario_padrao.clock(0) == "07:00"
    assert cenario_padrao.clock(125) == "09:05"
    assert cenario_padrao.clock(480) == "15:00"


def test_semana_tem_cinco_dias_uteis():
    semana = weekly_scenarios()
    assert len(semana) == 5
    assert [s.date for s in semana] == ["2026-10-12", "2026-10-13", "2026-10-14",
                                        "2026-10-15", "2026-10-16"]
    assert len({len(s.deliveries) for s in semana}) > 1  # volumes diferentes


def test_haversine_sao_paulo_rio():
    # Praça da Sé (SP) → Cinelândia (RJ): ~360 km em linha reta.
    d = haversine_km(-23.5503, -46.6340, -22.9110, -43.1759)
    assert 350 < d < 365


def test_matriz_de_distancias_simetrica_e_com_tortuosidade():
    pts = [(-23.55, -46.63), (-23.60, -46.70), (-23.50, -46.60)]
    d1 = distance_matrix_km(pts)
    d2 = distance_matrix_km(pts, circuity=1.35)
    assert np.allclose(d1, d1.T)
    assert np.allclose(np.diag(d1), 0)
    assert np.allclose(d2, 1.35 * d1)
    assert d1[0, 1] == pytest.approx(haversine_km(*pts[0], *pts[1]), rel=1e-9)


def test_cenario_invalido_e_detectado():
    sc = generate_scenario(seed=1)
    sc.vehicles = [v for v in sc.vehicles if REFRIGERADO not in v.features]
    problemas = sc.validate()
    assert any("refrigerado" in p for p in problemas)


def test_veiculo_serializa(cenario_padrao):
    v = cenario_padrao.vehicles[0]
    assert Vehicle.from_dict(v.to_dict()) == v
