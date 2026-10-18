"""
Painel interativo do MedRoute (Streamlit).

    streamlit run app/dashboard.py

Abas: mapa e rotas · evolução do GA · comparativo · assistente (LLM) · dados.
O plano padrão (cenário semente 42, GA com a configuração padrão) é o mesmo
do pipeline ``python main.py``, então as respostas da LLM já geradas lá vêm
do cache e aparecem na hora.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from medroute.baselines import nearest_neighbor, ortools_available, run_baseline  # noqa: E402
from medroute.ga import GAConfig, GeneticAlgorithm  # noqa: E402
from medroute.llm import RouteAssistant  # noqa: E402
from medroute.llm.client import OpenRouterClient  # noqa: E402
from medroute.plan import RoutePlan  # noqa: E402
from medroute.problem import FitnessWeights, Problem  # noqa: E402
from medroute.scenario import default_scenario, weekly_scenarios  # noqa: E402
from medroute.viz import plots  # noqa: E402
from medroute.viz.folium_map import build_route_map  # noqa: E402

METODO_GA = "MedRoute (algoritmo genético)"
METODO_ATUAL = "Processo atual (despachante)"

st.set_page_config(page_title="MedRoute — rotas hospitalares", page_icon="💊", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem; padding-bottom: 1rem;}
      div[data-testid="stMetricValue"] {font-size: 1.55rem;}
      .badge {display:inline-block;padding:2px 8px;border-radius:10px;font-size:.78rem;
              background:#eef3f9;color:#1c5cab;margin-right:6px}
      .badge-off {background:#f4f1ea;color:#6b5a2e}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Cenários e otimização (com cache)
# ---------------------------------------------------------------------------
CENARIOS = {"Terça-feira — dia de referência (36 entregas)": None}
for _sc in weekly_scenarios():
    CENARIOS[f"{_sc.name} ({len(_sc.deliveries)} entregas)"] = _sc.date


def carregar_cenario(rotulo: str):
    data = CENARIOS[rotulo]
    if data is None:
        return default_scenario()
    return next(s for s in weekly_scenarios() if s.date == data)


def otimizar(rotulo: str, cfg: GAConfig, pesos: FitnessWeights, barra=None, grafico=None):
    sc = carregar_cenario(rotulo)
    problema = Problem(sc, pesos)
    pontos: list[dict] = []

    def cb(stt, _rotas):
        pontos.append({"geração": stt.generation, "melhor fitness": stt.best,
                       "média da população": stt.mean})
        if barra is not None:
            barra.progress(min(1.0, (stt.generation + 1) / cfg.generations),
                           text=f"geração {stt.generation} · melhor fitness {stt.best:,.1f} · "
                                f"{stt.best_distance_km:.1f} km · viável: "
                                f"{'sim' if stt.best_feasible else 'não'}")
        if grafico is not None and stt.generation % 10 == 0:
            grafico.line_chart(pd.DataFrame(pontos).set_index("geração")[["melhor fitness"]],
                               height=220)

    res = GeneticAlgorithm(problema, cfg, callback=cb).run()
    ga = RoutePlan.from_evaluation(problema, res.evaluation, METODO_GA, res.runtime_s)
    atual = RoutePlan.from_evaluation(problema, problema.evaluate(nearest_neighbor(problema, True)),
                                      METODO_ATUAL)
    return {"ga": ga, "atual": atual, "historico": res.history_dicts, "res": res,
            "problema": problema, "rotulo": rotulo}


@st.cache_resource(show_spinner="Otimizando o dia de referência…")
def otimizacao_inicial():
    return otimizar(next(iter(CENARIOS)), GAConfig(), FitnessWeights())


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
st.sidebar.title("💊 MedRoute")
st.sidebar.caption("Otimização de rotas de medicamentos e insumos — Tech Challenge Fase 2")
rotulo = st.sidebar.selectbox("Dia de operação", list(CENARIOS))
with st.sidebar.expander("Algoritmo genético", expanded=True):
    geracoes = st.slider("Gerações (máx.)", 50, 1000, 500, 50)
    populacao = st.slider("População", 40, 300, 120, 20)
    mutacao = st.slider("Taxa de mutação", 0.0, 1.0, 0.4, 0.05)
    crossover = st.selectbox("Crossover", ["mix", "bcrc", "ox", "pmx", "erx"],
                             help="mix = sorteia OX/PMX/ERX/BCRC a cada filho")
    selecao = st.selectbox("Seleção", ["tournament", "roulette", "rank", "truncation"])
    sementes = st.checkbox("População inicial com heurísticas", True)
    memetico = st.checkbox("Busca local (GA memético)", True)
    seed = st.number_input("Semente", 0, 10_000, 42)
with st.sidebar.expander("Pesos da função fitness"):
    w_prio = st.slider("Prioridade (crítico cedo)", 0.0, 3.0, 1.0, 0.25)
    w_atraso = st.slider("Atraso (SLA e janelas)", 0.0, 3.0, 1.0, 0.25)
modo_llm = st.sidebar.radio("LLM", ["auto", "offline"], horizontal=True,
                            help="auto: usa a OpenRouter (modelos gratuitos) e cai para o modo "
                                 "offline se faltar chave/cota")
cli = OpenRouterClient()
st.sidebar.caption(("🔑 chave OpenRouter configurada" if cli.available else "⚠️ sem chave — LLM em modo offline")
                   + f" · modelo: {cli.models[0].split('/')[-1]}")
rodar = st.sidebar.button("▶ Otimizar rotas", type="primary", use_container_width=True)

cfg = GAConfig(generations=geracoes, population_size=populacao, mutation_rate=mutacao,
               crossover=crossover, selection=selecao, heuristic_seeds=sementes,
               local_search=memetico, final_polish=memetico, seed=int(seed))
pesos = FitnessWeights(priority_time=w_prio, lateness=w_atraso)

if "resultado" not in st.session_state:
    st.session_state.resultado = otimizacao_inicial()
    st.session_state.chat = []
    st.session_state.textos = {}

st.title("Otimização de rotas para distribuição de medicamentos e insumos")

if rodar:
    st.subheader("Evolução ao vivo")
    barra = st.progress(0.0, text="iniciando…")
    grafico = st.empty()
    st.session_state.resultado = otimizar(rotulo, cfg, pesos, barra, grafico)
    st.session_state.chat = []
    st.session_state.textos = {}
    barra.progress(1.0, text=f"concluído em {st.session_state.resultado['res'].runtime_s:.1f} s · "
                             f"{st.session_state.resultado['res'].stop_reason}")

R = st.session_state.resultado
ga: RoutePlan = R["ga"]
atual: RoutePlan = R["atual"]
k, ka = ga.kpis, atual.kpis
eco = ga.compare(atual)

st.caption(f"{ga.scenario.name} · {ga.scenario.description}")
c = st.columns(6)
c[0].metric("Distância total", f"{k.total_km:.1f} km", f"{-eco['km_economizados']:.1f} km vs atual",
            delta_color="inverse")
c[1].metric("Custo do dia", f"R$ {k.cost_total_brl:,.0f}", f"{-eco['reais_economizados']:,.0f} R$",
            delta_color="inverse")
c[2].metric("Entregas no prazo", f"{k.on_time_pct:.0f}%", f"{eco['pontos_sla']:+.0f} p.p.")
c[3].metric("Críticas no prazo", f"{k.on_time_by_priority.get('CRÍTICA', 100):.0f}%",
            f"{k.on_time_by_priority.get('CRÍTICA', 100) - ka.on_time_by_priority.get('CRÍTICA', 100):+.0f} p.p.")
c[4].metric("Horas de rota", f"{k.route_hours:.1f} h", f"{-eco['horas_economizadas']:.1f} h",
            delta_color="inverse")
dv = k.violations - ka.violations
c[5].metric("Violações de restrição", f"{k.violations}", f"{dv:+d}" if dv else None,
            delta_color="inverse")

aba_mapa, aba_ga, aba_comp, aba_llm, aba_dados = st.tabs(
    ["📍 Mapa e rotas", "📈 Evolução do GA", "⚖️ Comparativo", "🤖 Assistente (LLM)", "📄 Dados"])

# ---------------------------------------------------------------------------
with aba_mapa:
    ver = st.radio("Plano exibido", [METODO_GA, METODO_ATUAL], horizontal=True)
    plano = ga if ver == METODO_GA else atual
    components.html(build_route_map(plano).get_root().render(), height=640)
    linhas = []
    for r in plano.routes:
        linhas.append({"veículo": f"{r.vehicle_id} · {r.vehicle_name}", "entregas": len(r.stops),
                       "km": r.distance_km, "autonomia (%)": r.range_pct, "carga (kg)": r.load_kg,
                       "ocupação (%)": r.load_pct, "retorno": r.return_time,
                       "violações": ", ".join(r.violations) or "—",
                       "sequência": " → ".join(s.delivery_id for s in r.stops)})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
with aba_ga:
    h = pd.DataFrame(R["historico"])
    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown("**Convergência** — melhor indivíduo e média da população")
        st.pyplot(plots.plot_convergence(R["historico"]), use_container_width=True)
    with col2:
        res = R["res"]
        st.markdown("**Execução**")
        st.write(f"- gerações executadas: **{res.generations_run}** ({res.stop_reason})")
        st.write(f"- avaliações de fitness: **{res.evaluations:,}**")
        st.write(f"- tempo: **{res.runtime_s:.1f} s**")
        st.write(f"- primeira solução viável: geração **{int(h[h['best_feasible']]['generation'].min())}**"
                 if h["best_feasible"].any() else "- nenhuma solução viável")
        st.write(f"- fitness final: **{res.best_fitness:.1f}**")
        st.caption("Representação: permutação das entregas com separadores de veículo. "
                   "Operadores: OX, PMX, ERX e BCRC; mutações swap, inversão, inserção, "
                   "scramble, prioridade e reparo; seleção por torneio; elitismo; imigrantes; "
                   "2-opt e relocate (memético).")
    st.pyplot(plots.plot_gantt(ga), use_container_width=True)
    st.pyplot(plots.plot_utilization(ga), use_container_width=True)

# ---------------------------------------------------------------------------
with aba_comp:
    st.markdown("Mesmo cenário e mesma função de avaliação para todas as abordagens.")
    metodos = ["tsp_base_split", "vizinho_mais_proximo", "despachante_prioridade", "clarke_wright",
               "sweep", "melhoria_local", "simulated_annealing", "busca_aleatoria"]
    if ortools_available():
        metodos.append("ortools")
    if st.button("Rodar comparativo"):
        problema = R["problema"]
        linhas = []
        barra = st.progress(0.0)
        for i, m in enumerate(metodos):
            r = run_baseline(m, problema, time_limit_s=10)
            kk = RoutePlan.from_evaluation(problema, r.evaluation, r.name, r.runtime_s).kpis
            linhas.append({"metodo": r.name, "km": kk.total_km, "custo_rs": kk.cost_total_brl,
                           "no_prazo_pct": kk.on_time_pct,
                           "criticas_no_prazo_pct": kk.on_time_by_priority.get("CRÍTICA", 100),
                           "violacoes": kk.violations, "fitness": kk.fitness,
                           "tempo_s": round(r.runtime_s, 2)})
            barra.progress((i + 1) / len(metodos), text=r.name)
        linhas.append({"metodo": METODO_GA, "km": k.total_km, "custo_rs": k.cost_total_brl,
                       "no_prazo_pct": k.on_time_pct,
                       "criticas_no_prazo_pct": k.on_time_by_priority.get("CRÍTICA", 100),
                       "violacoes": k.violations, "fitness": k.fitness,
                       "tempo_s": round(R["res"].runtime_s, 2)})
        st.session_state.comparativo = pd.DataFrame(linhas).sort_values("fitness")
    if "comparativo" in st.session_state:
        df = st.session_state.comparativo
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.pyplot(plots.plot_methods_comparison(df, METODO_GA), use_container_width=True)

# ---------------------------------------------------------------------------
with aba_llm:
    assistente = RouteAssistant(ga, atual, mode=modo_llm)

    def selo(resp) -> str:
        cls = "badge" if resp.source != "offline" else "badge badge-off"
        partes = [f"<span class='{cls}'>origem: {resp.source}</span>"]
        if resp.model:
            partes.append(f"<span class='badge'>{resp.model}</span>")
        if resp.validation:
            partes.append(f"<span class='badge'>fidelidade aos dados: {resp.validation['nota']:.0f}/100</span>")
        if resp.latency_s:
            partes.append(f"<span class='badge'>{resp.latency_s:.1f} s</span>")
        return " ".join(partes)

    def mostrar(chave: str) -> None:
        resp = st.session_state.textos.get(chave)
        if resp is None:
            return
        st.markdown(selo(resp), unsafe_allow_html=True)
        if resp.warning:
            st.info(resp.warning)
        st.markdown(resp.text)
        if resp.validation and resp.validation.get("observacoes"):
            st.caption("Guardrails: " + "; ".join(resp.validation["observacoes"]))

    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.subheader("Instruções para motoristas")
        usados = [r.vehicle_id for r in ga.routes if r.used]
        v = st.selectbox("Veículo", usados,
                         format_func=lambda x: f"{x} · {ga.route(x).vehicle_name}")
        if st.button("Gerar instruções", key="b_instr"):
            with st.spinner("Consultando a LLM…"):
                st.session_state.textos[f"instr_{v}"] = assistente.driver_instructions(v)
        mostrar(f"instr_{v}")
    with col_b:
        st.subheader("Relatórios e melhorias")
        b1, b2 = st.columns(2)
        if b1.button("Relatório diário", key="b_rel"):
            with st.spinner("Consultando a LLM…"):
                st.session_state.textos["rel"] = assistente.daily_report()
        if b2.button("Sugestões de melhoria", key="b_sug"):
            with st.spinner("Medindo padrões, simulando cenários 'e se' e consultando a LLM…"):
                st.session_state.textos["sug"] = assistente.improvement_suggestions()
        mostrar("rel")
        mostrar("sug")
        sug = st.session_state.textos.get("sug")
        if sug is not None and sug.extra.get("simulacoes"):
            with st.expander("Simulações 'e se' usadas pela LLM"):
                st.json(sug.extra["simulacoes"])

    st.divider()
    st.subheader("Pergunte sobre as rotas do dia")
    for p, r in st.session_state.chat:
        st.chat_message("user").write(p)
        with st.chat_message("assistant"):
            st.markdown(selo(r), unsafe_allow_html=True)
            st.markdown(r.text)
    pergunta = st.chat_input("Ex.: Qual veículo leva a insulina do paciente PD-05?")
    if pergunta:
        st.chat_message("user").write(pergunta)
        historico = [(p, r.text) for p, r in st.session_state.chat]
        with st.chat_message("assistant"):
            with st.spinner("Consultando a LLM…"):
                resp = assistente.ask(pergunta, historico)
            st.markdown(selo(resp), unsafe_allow_html=True)
            st.markdown(resp.text)
        st.session_state.chat.append((pergunta, resp))

# ---------------------------------------------------------------------------
with aba_dados:
    sc = ga.scenario
    st.markdown(f"**Central:** {sc.depot.name} · turno {sc.shift_start}–{sc.clock(sc.shift_minutes)}")
    st.markdown("**Frota**")
    st.dataframe(pd.DataFrame([{"id": v.id, "veículo": v.name, "capacidade (kg)": v.capacity_kg,
                                "autonomia (km)": v.range_km, "velocidade (km/h)": v.speed_kmh,
                                "R$/km": v.cost_per_km, "recursos": ", ".join(sorted(v.features)) or "—"}
                               for v in sc.vehicles]), hide_index=True, use_container_width=True)
    st.markdown("**Entregas**")
    st.dataframe(pd.DataFrame([{"id": d.id, "destino": d.name, "tipo": d.kind,
                                "prioridade": d.priority.label, "kg": d.demand_kg,
                                "requisitos": ", ".join(sorted(d.requirements)) or "—",
                                "janela": f"{sc.clock(d.window[0])}–{sc.clock(d.window[1])}",
                                "itens": d.items} for d in sc.deliveries]),
                 hide_index=True, use_container_width=True)
    st.download_button("Baixar plano (JSON)", ga.to_json(include_scenario=True),
                       file_name="plano_medroute.json", mime="application/json")
    st.download_button("Baixar cronograma (CSV)",
                       pd.DataFrame(ga.schedule_rows()).to_csv(index=False).encode("utf-8"),
                       file_name="cronograma_rotas.csv", mime="text/csv")
