"""Integração com LLM — sem rede: HTTP simulado com ``httpx.MockTransport``."""

from __future__ import annotations

import json

import httpx
import pytest

from medroute.llm import client as cli
from medroute.llm import guardrails, insights, offline, prompts
from medroute.llm.assistant import RouteAssistant
from medroute.llm.client import LLMError, OpenRouterClient, QuotaExceeded

MSGS = [{"role": "user", "content": "Olá"}]


def _ok(texto: str, modelo: str = "m1") -> httpx.Response:
    return httpx.Response(200, json={"model": modelo, "usage": {"total_tokens": 10},
                                     "choices": [{"message": {"content": texto},
                                                  "finish_reason": "stop"}]})


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)


def _cliente(handler, tmp_path, models=("m1", "m2")) -> OpenRouterClient:
    return OpenRouterClient(api_key="sk-teste-SEGREDO", models=list(models), cache_dir=tmp_path,
                            transport=httpx.MockTransport(handler))


# ----------------------------------------------------------------- cliente
def test_sem_chave_nao_chama_api(tmp_path):
    c = OpenRouterClient(api_key="", cache_dir=tmp_path)
    assert not c.available
    with pytest.raises(LLMError):
        c.chat(MSGS)


def test_resposta_cache_e_chave_protegida(tmp_path):
    chamadas = []

    def handler(req: httpx.Request) -> httpx.Response:
        chamadas.append(json.loads(req.content))
        assert req.headers["Authorization"] == "Bearer sk-teste-SEGREDO"
        return _ok("Resposta de teste")

    c = _cliente(handler, tmp_path)
    r1 = c.chat(MSGS, temperature=0.2)
    r2 = c.chat(MSGS, temperature=0.2)
    assert r1.text == "Resposta de teste" and not r1.cached
    assert r2.cached and len(chamadas) == 1                    # 2ª vez veio do cache
    assert chamadas[0]["model"] == "m1" and chamadas[0]["temperature"] == 0.2
    assert chamadas[0]["reasoning"] == {"enabled": False}
    for arq in tmp_path.glob("*.json"):
        assert "SEGREDO" not in arq.read_text(encoding="utf-8")
    assert "SEGREDO" not in repr(c)


def test_fallback_para_o_proximo_modelo(tmp_path):
    def handler(req):
        modelo = json.loads(req.content)["model"]
        if modelo == "m1":
            return httpx.Response(404, json={"error": {"message": "indisponível"}})
        return _ok("do modelo 2", modelo)

    r = _cliente(handler, tmp_path).chat(MSGS)
    assert r.text == "do modelo 2" and r.model == "m2"


def test_resposta_vazia_passa_para_o_proximo_modelo(tmp_path):
    def handler(req):
        modelo = json.loads(req.content)["model"]
        return _ok("" if modelo == "m1" else "ok", modelo)

    assert _cliente(handler, tmp_path).chat(MSGS).model == "m2"


def test_limite_por_minuto_tenta_de_novo(tmp_path):
    estado = {"n": 0}

    def handler(req):
        estado["n"] += 1
        if estado["n"] == 1:
            return httpx.Response(429, json={"error": {"message": "rate limited per minute"}},
                                  headers={"Retry-After": "1"})
        return _ok("depois do 429")

    assert _cliente(handler, tmp_path).chat(MSGS).text == "depois do 429"


def test_cota_diaria_esgotada(tmp_path):
    def handler(req):
        return httpx.Response(429, json={"error": {"message":
                              "Rate limit exceeded: free-models-per-day"}})

    with pytest.raises(QuotaExceeded):
        _cliente(handler, tmp_path).chat(MSGS)


def test_chave_recusada(tmp_path):
    with pytest.raises(LLMError, match="401"):
        _cliente(lambda r: httpx.Response(401, json={}), tmp_path).chat(MSGS)


# --------------------------------------------------------------- assistente
def test_modo_auto_sem_chave_cai_para_offline(plano_padrao, tmp_path):
    ga, atual = plano_padrao
    a = RouteAssistant(ga, atual, client=OpenRouterClient(api_key="", cache_dir=tmp_path))
    r = a.driver_instructions("V1")
    assert r.source == "offline" and r.warning
    assert r.validation["nota"] >= 95


def test_modo_auto_com_cota_esgotada_cai_para_offline(plano_padrao, tmp_path):
    ga, atual = plano_padrao
    cliente = _cliente(lambda r: httpx.Response(429, json={"error": {"message": "free-models-per-day"}}),
                       tmp_path)
    r = RouteAssistant(ga, atual, client=cliente).daily_report()
    assert r.source == "offline" and "Cota" in r.warning


def test_modo_llm_exige_resposta(plano_padrao, tmp_path):
    ga, atual = plano_padrao
    a = RouteAssistant(ga, atual, client=OpenRouterClient(api_key="", cache_dir=tmp_path), mode="llm")
    with pytest.raises(LLMError):
        a.daily_report()


def test_prompt_de_instrucoes_leva_todos_os_dados_da_rota(plano_padrao, tmp_path):
    ga, atual = plano_padrao
    enviados = []

    def handler(req):
        enviados.append(json.loads(req.content)["messages"])
        return _ok("## Rota\nTexto")

    a = RouteAssistant(ga, atual, client=_cliente(handler, tmp_path), mode="llm")
    rota = ga.route("V1")
    resp = a.driver_instructions("V1")
    sistema, usuario = enviados[0][0]["content"], enviados[0][1]["content"]
    assert "Use SOMENTE as informações dentro de <dados>" in sistema
    assert usuario.startswith("<dados>") and "</dados>" in usuario
    for s in rota.stops:
        assert s.delivery_id in usuario and s.arrival in usuario
    assert resp.source == "llm"
    assert resp.validation["cobertura_paradas"] == 0.0     # texto falso não cita as paradas
    assert resp.extra["prompt_version"] == prompts.PROMPT_VERSION


def test_chat_mantem_historico(plano_padrao, tmp_path):
    ga, atual = plano_padrao
    enviados = []

    def handler(req):
        enviados.append(json.loads(req.content)["messages"])
        return _ok("resposta")

    a = RouteAssistant(ga, atual, client=_cliente(handler, tmp_path), mode="llm")
    a.ask("primeira?")
    a.ask("segunda?", [("primeira?", "resposta")])
    msgs = enviados[-1]
    assert msgs[0]["role"] == "system" and "<dados>" in msgs[1]["content"]
    assert "primeira?" in msgs[-3]["content"] and "segunda?" in msgs[-1]["content"]


# --------------------------------------------------------------- guardrails
def test_guardrails_aprovam_texto_fiel(plano_padrao):
    ga, _ = plano_padrao
    rota = ga.route("V1")
    rep = guardrails.validate_route_text(offline.driver_instructions(ga, rota), rota, ga)
    assert rep.nota == 100.0
    assert rep.cobertura_paradas == 1.0 and rep.ordem_correta and rep.horarios_citados == 1.0


def test_guardrails_detectam_parada_omitida_e_dados_inventados(plano_padrao):
    ga, _ = plano_padrao
    rota = ga.route("V1")
    texto = offline.driver_instructions(ga, rota)
    primeira = rota.stops[0]
    sem_primeira = "\n".join(l for l in texto.splitlines() if primeira.name not in l)
    sem_primeira += "\nPassar também na E99 às 03:33."
    rep = guardrails.validate_route_text(sem_primeira, rota, ga)
    assert rep.cobertura_paradas < 1.0
    assert "E99" in rep.ids_inexistentes and "03:33" in rep.horarios_inventados
    assert rep.nota < 80


def test_guardrails_detectam_ordem_trocada(plano_padrao):
    ga, _ = plano_padrao
    rota = next(r for r in ga.routes if len(r.stops) >= 3)
    nomes = [s.name for s in rota.stops]
    texto = "\n".join(reversed(nomes))
    rep = guardrails.validate_route_text(texto, rota, ga)
    assert rep.cobertura_paradas == 1.0 and rep.ordem_correta is False


def test_guardrails_numeros_rastreaveis(plano_padrao):
    ga, _ = plano_padrao
    k = ga.kpis
    ok = guardrails.validate_free_text(f"Foram {k.total_km} km e R$ {k.cost_total_brl}.", ga)
    ruim = guardrails.validate_free_text("Foram 9999 km e R$ 12345,67.", ga)
    assert ok.numeros_nao_rastreaveis == []
    assert len(ruim.numeros_nao_rastreaveis) == 2


# ------------------------------------------------------------------ offline
def test_respostas_offline(plano_padrao):
    ga, _ = plano_padrao
    r, s = ga.find_stop("E25")
    resp = offline.answer(ga, "Qual veículo leva a insulina do paciente PD-05?")
    assert r.vehicle_id in resp and s.arrival in resp
    assert "km" in offline.answer(ga, "Quantos km no total?")
    assert "não sai" in offline.answer(ga, "rota do V5") or "V5" in offline.answer(ga, "rota do V5")
    assert "offline" in offline.answer(ga, "Qual a capital da França?")


def test_relatorios_offline_tem_as_secoes(plano_padrao):
    ga, atual = plano_padrao
    rel = offline.daily_report(ga, atual)
    for secao in ("Resumo executivo", "Indicadores", "Pontos de atenção", "Uso da frota"):
        assert secao in rel


# ------------------------------------------------------------------ padrões
def test_insights_e_simulacoes_sugeridas(plano_padrao):
    ga, atual = plano_padrao
    achados = insights.analyze_plan(ga, atual)
    codigos = {a.codigo for a in achados}
    assert {"CADEIA_FRIA", "FOLGA_TURNO", "GANHO_VS_ATUAL", "EMISSOES"} <= codigos
    if ga.kpis.critical_late:
        assert "ATRASO_CRITICO" in codigos
        assert "bau_termico_moto02" in insights.suggested_what_ifs(achados)


@pytest.mark.slow
def test_simulacao_e_se_reotimiza_o_dia(plano_padrao):
    ga, _ = plano_padrao
    w = insights.run_what_if(ga, "bau_termico_moto02", generations=40)
    assert set(w.antes) == set(w.depois)
    assert w.depois["violacoes"] == 0


def test_guardrails_detectam_requisito_inventado(plano_padrao):
    """Erro real da v1 do prompt: ceftriaxona tratada como controlado."""
    ga, _ = plano_padrao
    alvo = next((r, s) for r in ga.routes for s in r.stops if "Ceftriaxona" in s.items)
    rota, parada = alvo
    errado = (f"### Antes de sair\n- Verificar lacre dos itens controlados (Ceftriaxona – Portaria 344/98)\n"
              f"### Paradas\n**1. {parada.arrival} — {parada.name}**\n"
              f"  - Entrega controlada: exigir assinatura (Portaria 344/98)\n")
    rep = guardrails.validate_route_text(errado, rota, ga)
    assert rep.requisitos_inventados == [f"{parada.delivery_id} tratado como controlado"]
    # Frase de resumo que só cita a parada ao lado da palavra não é acusada.
    ambigua = f"- Priorizar a crítica ({parada.name}) e os controlados.\n"
    assert guardrails.validate_route_text(ambigua, rota, ga).requisitos_inventados == []


def test_prompt_v3_proibe_deduzir_requisito_e_usa_indices():
    assert prompts.PROMPT_VERSION.endswith("v3")
    assert "Nunca deduza um requisito pelo nome" in prompts.SYSTEM
    assert "pelo tipo da unidade" in prompts.SYSTEM and '"indices"' in prompts.SYSTEM


def test_contexto_traz_indices_por_requisito(plano_padrao):
    from medroute.llm import context as ctx

    ga, _ = plano_padrao
    idx = ctx.plan_context(ga)["indices"]
    reais = [d.id for d in ga.scenario.deliveries if "controlado" in d.requirements]
    assert idx["entregas_controladas"]["total"] == len(reais)
    assert sorted(i["id"] for i in idx["entregas_controladas"]["lista"]) == sorted(reais)


def test_guardrails_pegam_item_de_lista_e_contagem_errada(plano_padrao):
    """Erro real da v2 no chat: um CAPS sem controlados listado como controlado."""
    ga, _ = plano_padrao
    ctrl = [(r, s) for r in ga.routes for s in r.stops if "controlado" in s.requirements]
    intruso = next((r, s) for r in ga.routes for s in r.stops if not s.requirements)
    linhas = [f"Há {len(ctrl) + 1} entregas com requisito \"controlado\" (Portaria 344/98):", ""]
    for r, s in ctrl + [intruso]:
        linhas.append(f"- Ordem {s.seq} – {s.delivery_id} – {s.name} – chegada {s.arrival}")
    rep = guardrails.validate_free_text("\n".join(linhas), ga)
    assert f"{intruso[1].delivery_id} listado como controlado" in rep.requisitos_inventados
    assert any(a.startswith("contagem:") for a in rep.requisitos_inventados)
    certo = linhas[0].replace(f"Há {len(ctrl) + 1}", f"Há {len(ctrl)}")
    certo += "\n\n" + "\n".join(linhas[2:-1])
    assert guardrails.validate_free_text(certo, ga).requisitos_inventados == []


def test_geracao_interrompida_pelo_provedor_nao_e_aceita(tmp_path):
    """Caso real: finish_reason "error" com texto parcial (cortado no meio)."""
    estado = {"n": 0}

    def handler(req):
        estado["n"] += 1
        if estado["n"] == 1:
            return httpx.Response(200, json={"model": "m1", "choices": [
                {"message": {"content": "texto cortado no mei"}, "finish_reason": "error"}]})
        return _ok("texto completo")

    c = _cliente(handler, tmp_path)
    assert c.chat(MSGS).text == "texto completo"
    assert c.chat(MSGS).cached                      # só o texto completo foi para o cache
    assert estado["n"] == 2


def test_contagem_por_veiculo_nao_e_acusada(plano_padrao):
    """Falso positivo corrigido: '2 paradas controladas na V1 e 4 na V2' está certo."""
    ga, _ = plano_padrao
    partes = []
    for r in ga.routes:
        n = sum("controlado" in s.requirements for s in r.stops)
        if n:
            partes.append(f"- {r.vehicle_id}: {n} paradas controladas")
    rep = guardrails.validate_free_text("\n".join(partes), ga)
    assert rep.requisitos_inventados == []


def test_total_de_paradas_perto_de_controlado_nao_e_contagem(plano_padrao):
    """Falso positivo corrigido: '(13 paradas) e validar lacres para controlados'."""
    ga, _ = plano_padrao
    texto = "- Conferir carga na ordem de entrega (13 paradas) e validar lacres para itens controlados."
    assert guardrails.validate_free_text(texto, ga).requisitos_inventados == []
