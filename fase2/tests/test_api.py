"""API REST (FastAPI) — LLM sempre em modo offline nos testes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from medroute.api.app import app


@pytest.fixture(scope="module")
def cliente():
    return TestClient(app)


@pytest.fixture(scope="module")
def plano_id(cliente):
    r = cliente.post("/otimizar", json={"config": {"geracoes": 40, "seed": 1},
                                        "incluir_historico": True})
    assert r.status_code == 200
    d = r.json()
    assert len(d["historico"]) == d["geracoes"]
    assert d["plano"]["kpis"]["deliveries"] == 36
    return d["plano_id"]


def test_health(cliente):
    d = cliente.get("/health").json()
    assert d["status"] == "ok" and "modelos" in d["llm"]


def test_cenarios(cliente):
    padrao = cliente.get("/cenarios/padrao").json()
    assert len(padrao["deliveries"]) == 36
    novo = cliente.post("/cenarios/gerar", json={"seed": 3, "composicao": {"UBS": 4, "Domiciliar": 5}})
    assert novo.status_code == 200 and len(novo.json()["deliveries"]) == 9


def test_plano_mapa_e_produtos_da_llm(cliente, plano_id):
    assert cliente.get(f"/planos/{plano_id}").status_code == 200
    mapa = cliente.get(f"/planos/{plano_id}/mapa")
    assert mapa.status_code == 200 and "leaflet" in mapa.text.lower()
    for rota in (f"/planos/{plano_id}/instrucoes/V1", f"/planos/{plano_id}/relatorio"):
        r = cliente.post(rota, params={"modo": "offline"})
        assert r.status_code == 200 and r.json()["source"] == "offline"
    r = cliente.post(f"/planos/{plano_id}/perguntar", params={"modo": "offline"},
                     json={"pergunta": "Tem alguma entrega atrasada?"})
    assert r.status_code == 200 and r.json()["text"]
    r = cliente.post(f"/planos/{plano_id}/sugestoes", params={"modo": "offline", "simular": False})
    assert r.status_code == 200 and r.json()["extra"]["achados"]


def test_erros_tratados(cliente, plano_id):
    assert cliente.get("/planos/naoexiste").status_code == 404
    assert cliente.post(f"/planos/{plano_id}/instrucoes/V9", params={"modo": "offline"}).status_code == 404
    assert cliente.post("/otimizar", json={"cenario": {"name": "incompleto"}}).status_code == 422
    assert cliente.post("/otimizar", json={"config": {"geracoes": 0}}).status_code == 422


def test_comparar(cliente):
    r = cliente.post("/comparar", json={"metodos": ["vizinho_mais_proximo", "sweep"],
                                        "incluir_ga": False})
    res = r.json()["resultados"]
    assert r.status_code == 200 and len(res) == 2
    assert res[0]["fitness"] <= res[1]["fitness"]


def test_openapi_documenta_todas_as_rotas(cliente):
    caminhos = cliente.get("/openapi.json").json()["paths"]
    for p in ("/otimizar", "/comparar", "/planos/{plano_id}/perguntar", "/planos/{plano_id}/mapa"):
        assert p in caminhos
