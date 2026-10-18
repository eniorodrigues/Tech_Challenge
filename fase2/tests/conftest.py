"""Fixtures compartilhadas.

Regras dos testes:

* **nunca** acessam a rede — a LLM é testada com transporte HTTP simulado
  (``httpx.MockTransport``) e uma fixture automática bloqueia chamadas reais;
* figuras são geradas sem mapa de fundo (sem baixar tiles);
* instâncias pequenas e construídas à mão permitem conferir contas exatas.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from medroute.domain import (  # noqa: E402
    CONTROLADO,
    REFRIGERADO,
    Delivery,
    Depot,
    Priority,
    PriorityPolicy,
    Scenario,
    Vehicle,
)
from medroute.problem import Problem  # noqa: E402
from medroute.scenario import default_scenario  # noqa: E402


@pytest.fixture(autouse=True)
def _sem_rede(monkeypatch):
    """Bloqueia requisições reais da LLM (só transporte simulado passa)."""
    from medroute.llm import client as cli

    original = cli.OpenRouterClient._post

    def _post(self, body):
        if self._transport is None:
            raise RuntimeError("rede bloqueada nos testes")
        return original(self, body)

    monkeypatch.setattr(cli.OpenRouterClient, "_post", _post)
    monkeypatch.delenv("MEDROUTE_LLM_MODELS", raising=False)
    yield


@pytest.fixture(scope="session")
def cenario_padrao() -> Scenario:
    return default_scenario()


@pytest.fixture(scope="session")
def problema_padrao(cenario_padrao) -> Problem:
    return Problem(cenario_padrao)


def _entrega(i: int, **kw) -> Delivery:
    base = dict(id=f"E{i:02d}", name=f"Unidade {i}", kind="UBS", lat=-23.5, lon=-46.6,
                priority=Priority.NORMAL, demand_kg=10.0, service_min=0.0, window=(0.0, 480.0))
    base.update(kw)
    return Delivery(**base)


@pytest.fixture
def mini() -> Problem:
    """3 entregas, 2 veículos e matriz de distâncias escolhida à mão.

    Distâncias (km)::

            0    1    2    3
        0   0   10   20   10
        1  10    0   10   20
        2  20   10    0   10
        3  10   20   10    0

    V1: 60 km/h (1 km/min), 25 kg, autonomia 100 km, refrigerado.
    V2: 60 km/h, 15 kg, autonomia 30 km, sem recursos.
    """
    entregas = [
        _entrega(1, priority=Priority.CRITICAL, requirements=frozenset({REFRIGERADO})),
        _entrega(2),
        _entrega(3, priority=Priority.HIGH),
    ]
    frota = [
        Vehicle(id="V1", name="Van fria", kind="van_refrigerada", capacity_kg=25, range_km=100,
                speed_kmh=60, cost_per_km=2.0, features=frozenset({REFRIGERADO, CONTROLADO})),
        Vehicle(id="V2", name="Moto", kind="moto", capacity_kg=15, range_km=30, speed_kmh=60,
                cost_per_km=0.5),
    ]
    sc = Scenario(name="mini", depot=Depot("Central", -23.5, -46.6), deliveries=entregas,
                  vehicles=frota, shift_minutes=480, circuity=1.0, policy=PriorityPolicy())
    D = np.array([[0, 10, 20, 10], [10, 0, 10, 20], [20, 10, 0, 10], [10, 20, 10, 0]], float)
    return Problem(sc, distance_matrix=D)


@pytest.fixture
def plano_padrao(problema_padrao):
    """Plano do GA (configuração curta) + plano do processo atual."""
    from medroute.baselines import nearest_neighbor
    from medroute.ga import GAConfig, GeneticAlgorithm
    from medroute.plan import RoutePlan

    res = GeneticAlgorithm(problema_padrao, GAConfig(generations=60, seed=5)).run()
    ga = RoutePlan.from_evaluation(problema_padrao, res.evaluation, "GA", res.runtime_s)
    atual = RoutePlan.from_evaluation(
        problema_padrao, problema_padrao.evaluate(nearest_neighbor(problema_padrao, True)), "Atual")
    return ga, atual


@pytest.fixture
def sem_chave(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    os.environ["OPENROUTER_API_KEY"] = ""
    yield
