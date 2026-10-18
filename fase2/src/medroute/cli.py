"""
Interface de linha de comando do MedRoute.

    python main.py                         # pipeline completo (padrão)
    python main.py otimizar --geracoes 500 --seed 42
    python main.py comparar                # todas as abordagens no cenário padrão
    python main.py semana                  # simula 5 dias + relatório semanal
    python main.py llm instrucoes --veiculo V1
    python main.py llm perguntar "Qual veículo leva a insulina do PD-05?"
    python main.py visualizar              # janela pygame (herdada do código base)

O pipeline completo gera tudo que o relatório técnico e o vídeo usam:
cenário, plano do GA, plano do processo atual, mapas (HTML e PNG), gráficos,
comparativo do dia, semana simulada e os textos da LLM (com validação).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import config
from .baselines import nearest_neighbor, ortools_available, run_baseline
from .domain import Scenario
from .ga import GAConfig, GeneticAlgorithm
from .plan import RoutePlan
from .problem import Problem
from .scenario import default_scenario

METODO_GA = "MedRoute (algoritmo genético)"
METODO_ATUAL = "Processo atual (despachante)"

PERGUNTAS_DEMO = (
    "Qual veículo leva a insulina do paciente PD-05 e a que horas chega?",
    "Alguma entrega crítica corre risco de atraso? O que fazer?",
    "Quais entregas de medicamentos controlados existem hoje e em quais veículos?",
    "Qual é o telefone do paciente PD-08?",
)


def _titulo(n: int | str, texto: str) -> None:
    print("\n" + "=" * 72)
    print(f"{n}. {texto}" if n != "" else texto)
    print("=" * 72)


def _carregar_cenario(caminho: str | None = None) -> Scenario:
    if caminho:
        return Scenario.from_json(caminho)
    sc = default_scenario()
    sc.to_json(config.DEFAULT_SCENARIO_FILE)
    return sc


# ---------------------------------------------------------------------------
# Etapas
# ---------------------------------------------------------------------------
def etapa_cenario(sc: Scenario) -> Problem:
    _titulo(1, "CENÁRIO DO DIA")
    print(f"{sc.name}")
    print(f"  {sc.description}")
    crit = sum(d.priority.label == "CRÍTICA" for d in sc.deliveries)
    alta = sum(d.priority.label == "ALTA" for d in sc.deliveries)
    frias = sum(d.refrigerated for d in sc.deliveries)
    ctrl = sum(d.controlled for d in sc.deliveries)
    print(f"  Prioridades: {crit} críticas (prazo 2 h), {alta} altas (prazo 4 h), "
          f"{len(sc.deliveries) - crit - alta} normais")
    print(f"  Requisitos: {frias} com cadeia fria, {ctrl} com medicamento controlado")
    print(f"  Carga total: {sc.total_demand_kg:.0f} kg  |  capacidade da frota: "
          f"{sc.total_capacity_kg:.0f} kg ({100 * sc.total_demand_kg / sc.total_capacity_kg:.0f}%)")
    print("  Frota:")
    for v in sc.vehicles:
        recursos = ", ".join(sorted(v.features)) or "—"
        print(f"    {v.id} {v.name:24s} {v.capacity_kg:5.0f} kg  autonomia {v.range_km:4.0f} km  "
              f"{v.speed_kmh:.0f} km/h  R$ {v.cost_per_km:.2f}/km  recursos: {recursos}")
    problemas = sc.validate()
    print(f"  Validação da instância: {'OK' if not problemas else problemas}")
    return Problem(sc)


def etapa_ga(problema: Problem, cfg: GAConfig) -> tuple[RoutePlan, object]:
    _titulo(2, "OTIMIZAÇÃO COM ALGORITMO GENÉTICO")
    print(f"  População {cfg.population_size} · até {cfg.generations} gerações · crossover "
          f"{cfg.crossover} · mutação {cfg.mutation} ({cfg.mutation_rate:.0%}) · seleção "
          f"{cfg.selection} · elitismo {cfg.elitism} · semente {cfg.seed}")
    marcos = {0, 1, 5, 10, 25, 50, 100, 200, 300, 400, 500, 750, 1000}

    def progresso(st, _rotas):
        if st.generation in marcos:
            print(f"  geração {st.generation:4d} | melhor fitness {st.best:10.1f} | "
                  f"{st.best_distance_km:6.1f} km | viável: {'sim' if st.best_feasible else 'não'} "
                  f"| diversidade {st.diversity:.2f} | {st.elapsed_s:5.1f}s")

    res = GeneticAlgorithm(problema, cfg, callback=progresso).run()
    print(f"  Parada: {res.stop_reason} ({res.generations_run} gerações, "
          f"{res.evaluations} avaliações, {res.runtime_s:.1f} s)")
    plano = RoutePlan.from_evaluation(problema, res.evaluation, METODO_GA, res.runtime_s,
                                      meta={"config": cfg.to_dict(),
                                            "generations_run": res.generations_run,
                                            "evaluations": res.evaluations})
    print()
    print(plano.summary_text())
    return plano, res


def etapa_comparativo(problema: Problem, plano_ga: RoutePlan, ortools: bool) -> tuple[RoutePlan, list[dict]]:
    _titulo(3, "COMPARATIVO COM OUTRAS ABORDAGENS (mesmo cenário)")
    linhas = []
    planos: dict[str, RoutePlan] = {}
    nomes = ["tsp_base_split", "vizinho_mais_proximo", "despachante_prioridade",
             "clarke_wright", "sweep", "busca_aleatoria", "melhoria_local", "simulated_annealing"]
    if ortools and ortools_available():
        nomes.append("ortools")
    for nome in nomes:
        r = run_baseline(nome, problema)
        p = RoutePlan.from_evaluation(problema, r.evaluation, r.name, r.runtime_s)
        planos[nome] = p
        linhas.append(_linha(p))
    linhas.append(_linha(plano_ga))
    print(f"  {'Abordagem':40s} {'km':>7s} {'R$':>9s} {'no prazo':>9s} {'críticas':>9s} "
          f"{'violações':>9s} {'fitness':>10s} {'tempo':>7s}")
    for l in sorted(linhas, key=lambda x: x["fitness"]):
        print(f"  {l['metodo']:40s} {l['km']:7.1f} {l['custo_rs']:9.2f} {l['no_prazo_pct']:8.1f}% "
              f"{l['criticas_no_prazo_pct']:8.1f}% {l['violacoes']:9d} {l['fitness']:10.1f} "
              f"{l['tempo_s']:6.2f}s")
    if not (ortools and ortools_available()):
        print("  (OR-Tools indisponível neste ambiente — ver docs/RELATORIO_TECNICO.md)")
    atual = planos["despachante_prioridade"]
    atual.method = METODO_ATUAL
    eco = plano_ga.compare(atual)
    print(f"\n  -> MedRoute vs processo atual: {eco['km_economizados']:.1f} km "
          f"({eco['km_economizados_pct']:.0f}%) e R$ {eco['reais_economizados']:.2f} a menos; "
          f"{eco['horas_economizadas']:.1f} h de rota a menos; no prazo {eco['pontos_sla']:+.1f} p.p.; "
          f"{eco['co2_evitado_kg']:.1f} kg de CO2 evitados")
    return atual, linhas


def _linha(p: RoutePlan) -> dict:
    k = p.kpis
    return {"metodo": p.method, "km": k.total_km, "custo_rs": k.cost_total_brl,
            "horas": k.route_hours, "co2_kg": k.co2_kg, "no_prazo_pct": k.on_time_pct,
            "criticas_no_prazo_pct": k.on_time_by_priority.get("CRÍTICA", 100.0),
            "atrasos": k.late_count, "violacoes": k.violations, "fitness": k.fitness,
            "tempo_s": round(p.runtime_s, 3)}


def etapa_visualizacoes(plano_ga: RoutePlan, atual: RoutePlan, res, linhas: list[dict]) -> None:
    _titulo(4, "VISUALIZAÇÕES")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    from .viz import folium_map, plots, static_map
    from .viz.tiles import build_basemap

    fig_dir, map_dir = config.FIGURES_DIR, config.MAPS_DIR
    dep = plano_ga.scenario.depot
    lats = [dep.lat] + [d.lat for d in plano_ga.scenario.deliveries]
    lons = [dep.lon] + [d.lon for d in plano_ga.scenario.deliveries]
    base = build_basemap(lats, lons)
    print(f"  Mapa de fundo: {'OpenStreetMap (cache local)' if base else 'indisponível (sem rede) — fundo liso'}")

    saidas = []
    saidas.append(folium_map.save_route_map(plano_ga, map_dir / "mapa_rotas_ga.html"))
    saidas.append(folium_map.save_route_map(atual, map_dir / "mapa_rotas_processo_atual.html"))
    static_map.plot_route_map(plano_ga, fig_dir / "01_mapa_rotas_ga.png", basemap=base)
    static_map.plot_route_map(atual, fig_dir / "02_mapa_rotas_processo_atual.png",
                              title=f"Rotas do processo atual — {atual.method}", basemap=base)
    static_map.plot_vehicle_facets(plano_ga, fig_dir / "03_mapa_por_veiculo.png", basemap=base)
    plots.plot_convergence(res.history_dicts, fig_dir / "04_convergencia_ga.png")
    plots.plot_gantt(plano_ga, fig_dir / "05_linha_do_tempo_ga.png")
    plots.plot_gantt(atual, fig_dir / "06_linha_do_tempo_processo_atual.png")
    plots.plot_utilization(plano_ga, fig_dir / "07_ocupacao_frota.png")
    df = pd.DataFrame(linhas)
    plots.plot_methods_comparison(df, highlight=METODO_GA, path=fig_dir / "08_comparativo_dia.png")
    plt.close("all")
    for f in sorted(fig_dir.glob("0[1-8]_*.png")):
        saidas.append(f)
    for s in saidas:
        print(f"  {Path(s).relative_to(config.PROJECT_ROOT)}")


def etapa_semana(cfg: GAConfig | None = None):
    from .operations import simulate_week

    _titulo(5, "SEMANA OPERACIONAL SIMULADA (relatório semanal)")
    semana = simulate_week(cfg, progress=lambda i, d: print(f"  roteirizando {d}-feira...", flush=True))
    df = semana.table
    df.to_csv(config.REPORTS_DIR / "operacao_semanal.csv", index=False)
    t = semana.summary["totais"]
    print(df[["dia", "entregas", "km_atual", "km_ga", "km_economia_pct", "sla_atual", "sla_ga",
              "violacoes_atual", "violacoes_ga"]].to_string(index=False))
    print(f"\n  Semana: {t['km_economia']:.0f} km ({t['km_economia_pct']:.0f}%), "
          f"R$ {t['custo_economia']:.2f}, {t['horas_economia']:.1f} h e {t['co2_economia']:.1f} kg de "
          f"CO2 economizados; no prazo {t['sla_atual']:.1f}% -> {t['sla_ga']:.1f}%")
    import matplotlib

    matplotlib.use("Agg")
    from .viz import plots

    plots.plot_weekly(df, config.FIGURES_DIR / "09_semana_km.png")
    return semana


def etapa_llm(plano_ga: RoutePlan, atual: RoutePlan, semana, modo: str,
              perguntas: tuple[str, ...] = PERGUNTAS_DEMO) -> None:
    from .llm import RouteAssistant

    _titulo(6, "LLM — INSTRUÇÕES, RELATÓRIOS, SUGESTÕES E PERGUNTAS")
    assistente = RouteAssistant(plano_ga, atual, mode=modo)
    if assistente.client is not None:
        print(f"  Cliente: {assistente.client!r}")
    pasta = config.LLM_OUTPUT_DIR
    pasta.mkdir(parents=True, exist_ok=True)
    registro = []

    def salvar(nome: str, resp) -> None:
        cabecalho = (f"<!-- gerado por: {resp.source}"
                     f"{' · modelo ' + resp.model if resp.model else ''}"
                     f" · fidelidade {resp.validation['nota'] if resp.validation else '—'}/100 -->\n\n")
        (pasta / f"{nome}.md").write_text(cabecalho + resp.text + "\n", encoding="utf-8")
        registro.append({"arquivo": f"{nome}.md", "tarefa": resp.task, "origem": resp.source,
                         "modelo": resp.model, "latencia_s": resp.latency_s,
                         "validacao": resp.validation, "aviso": resp.warning})
        nota = resp.validation["nota"] if resp.validation else "—"
        print(f"  {nome + '.md':34s} origem={resp.source:8s} fidelidade={nota:>5}/100 "
              f"{('modelo=' + resp.model) if resp.model else ''}"
              f"{('  AVISO: ' + resp.warning) if resp.warning else ''}", flush=True)

    for r in plano_ga.routes:
        if r.used:
            salvar(f"instrucoes_{r.vehicle_id}", assistente.driver_instructions(r.vehicle_id))
    salvar("relatorio_diario", assistente.daily_report())
    if semana is not None:
        salvar("relatorio_semanal", assistente.weekly_report(semana.summary))
    sug = assistente.improvement_suggestions()
    salvar("sugestoes_melhoria", sug)
    (pasta / "simulacoes_e_se.json").write_text(
        json.dumps({"achados": sug.extra.get("achados"), "simulacoes": sug.extra.get("simulacoes")},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    conversa = []
    historico: list[tuple[str, str]] = []
    for q in perguntas:
        resp = assistente.ask(q, historico)
        historico.append((q, resp.text))
        conversa.append(f"**Pergunta:** {q}\n\n**Resposta** ({resp.source}"
                        f"{', ' + resp.model if resp.model else ''}; fidelidade "
                        f"{resp.validation['nota']}/100):\n\n{resp.text}\n")
        registro.append({"arquivo": "perguntas_e_respostas.md", "tarefa": "pergunta",
                         "pergunta": q, "origem": resp.source, "modelo": resp.model,
                         "latencia_s": resp.latency_s, "validacao": resp.validation})
        print(f"  P: {q}\n     R ({resp.source}): {resp.text.splitlines()[0][:150]}", flush=True)
    (pasta / "perguntas_e_respostas.md").write_text(
        "# Perguntas em linguagem natural sobre o plano do dia\n\n" + "\n---\n\n".join(conversa),
        encoding="utf-8")
    (pasta / "registro_llm.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2),
                                             encoding="utf-8")


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
def cmd_pipeline(a: argparse.Namespace) -> int:
    t0 = time.perf_counter()
    config.ensure_dirs()
    print("=" * 72)
    print("MEDROUTE — Otimização de rotas de medicamentos e insumos (Tech Challenge Fase 2)")
    print("=" * 72)
    sc = _carregar_cenario(a.cenario)
    problema = etapa_cenario(sc)
    cfg = GAConfig(generations=a.geracoes, population_size=a.populacao, seed=a.seed)
    plano_ga, res = etapa_ga(problema, cfg)
    atual, linhas = etapa_comparativo(problema, plano_ga, ortools=not a.sem_ortools)

    (config.REPORTS_DIR / "plano_ga.json").write_text(plano_ga.to_json(), encoding="utf-8")
    (config.REPORTS_DIR / "plano_processo_atual.json").write_text(atual.to_json(), encoding="utf-8")
    import pandas as pd

    pd.DataFrame(plano_ga.schedule_rows()).to_csv(config.REPORTS_DIR / "rotas_ga.csv", index=False)
    pd.DataFrame(linhas).sort_values("fitness").to_csv(config.REPORTS_DIR / "comparativo_dia.csv",
                                                       index=False)
    pd.DataFrame(res.history_dicts).to_csv(config.REPORTS_DIR / "historico_ga.csv", index=False)

    etapa_visualizacoes(plano_ga, atual, res, linhas)
    semana = None if a.sem_semana else etapa_semana()
    if not a.sem_llm:
        etapa_llm(plano_ga, atual, semana, modo=a.modo_llm)

    _titulo("", f"PIPELINE CONCLUÍDO em {time.perf_counter() - t0:.0f} s")
    print("  Saídas em fase2/reports/ (figuras, mapas, CSVs, planos JSON e textos da LLM).")
    print("  Painel interativo:  streamlit run app/dashboard.py")
    print("  API REST:           uvicorn medroute.api.app:app --reload  (docs em /docs)")
    return 0


def cmd_otimizar(a: argparse.Namespace) -> int:
    config.ensure_dirs()
    sc = _carregar_cenario(a.cenario)
    problema = etapa_cenario(sc)
    cfg = GAConfig(generations=a.geracoes, population_size=a.populacao, seed=a.seed,
                   crossover=a.crossover, selection=a.selecao, mutation_rate=a.mutacao)
    plano, _ = etapa_ga(problema, cfg)
    destino = Path(a.saida) if a.saida else config.REPORTS_DIR / "plano_ga.json"
    destino.write_text(plano.to_json(), encoding="utf-8")
    from .viz.folium_map import save_route_map

    mapa = save_route_map(plano, config.MAPS_DIR / "mapa_rotas_ga.html")
    print(f"\n  Plano: {destino}\n  Mapa:  {mapa}")
    return 0


def cmd_comparar(a: argparse.Namespace) -> int:
    config.ensure_dirs()
    problema = etapa_cenario(_carregar_cenario(a.cenario))
    plano, _ = etapa_ga(problema, GAConfig(seed=a.seed))
    etapa_comparativo(problema, plano, ortools=True)
    return 0


def cmd_semana(a: argparse.Namespace) -> int:
    config.ensure_dirs()
    semana = etapa_semana()
    if not a.sem_llm:
        from .llm import RouteAssistant

        plano = semana.plans_ga[0]
        resp = RouteAssistant(plano, semana.plans_atual[0], mode=a.modo_llm).weekly_report(semana.summary)
        print("\n" + resp.text)
    return 0


def _plano_salvo() -> tuple[RoutePlan, RoutePlan]:
    """Recria os planos do pipeline (mesma semente → mesmo resultado)."""
    problema = Problem(_carregar_cenario(None))
    res = GeneticAlgorithm(problema, GAConfig()).run()
    ga = RoutePlan.from_evaluation(problema, res.evaluation, METODO_GA, res.runtime_s)
    atual = RoutePlan.from_evaluation(problema, problema.evaluate(nearest_neighbor(problema, True)),
                                      METODO_ATUAL)
    return ga, atual


def cmd_llm(a: argparse.Namespace) -> int:
    from .llm import RouteAssistant

    print("Recriando o plano do dia (GA, semente 42)...", flush=True)
    ga, atual = _plano_salvo()
    assistente = RouteAssistant(ga, atual, mode=a.modo_llm)
    if a.tarefa == "instrucoes":
        resp = assistente.driver_instructions(a.veiculo)
    elif a.tarefa == "relatorio":
        resp = assistente.daily_report()
    elif a.tarefa == "sugestoes":
        resp = assistente.improvement_suggestions()
    elif a.tarefa == "perguntar":
        if not a.texto:
            print("Informe a pergunta: python main.py llm perguntar \"...\"")
            return 2
        resp = assistente.ask(" ".join(a.texto))
    else:  # pragma: no cover - argparse restringe
        return 2
    print(f"\n[{resp.source}{' · ' + resp.model if resp.model else ''} · "
          f"fidelidade {resp.validation['nota'] if resp.validation else '—'}/100]\n")
    print(resp.text)
    if resp.warning:
        print(f"\nAVISO: {resp.warning}")
    return 0


def cmd_textos(a: argparse.Namespace) -> int:
    """Regenera só os textos da LLM (reaproveita a semana já simulada)."""
    import pandas as pd

    from .operations import WeekResult, summarize_week

    config.ensure_dirs()
    print("Recriando o plano do dia (GA, semente 42)...", flush=True)
    ga, atual = _plano_salvo()
    semana = None
    csv = config.REPORTS_DIR / "operacao_semanal.csv"
    if csv.exists():
        df = pd.read_csv(csv)
        semana = WeekResult(table=df, summary=summarize_week(df))
    etapa_llm(ga, atual, semana, modo=a.modo_llm)
    return 0


def cmd_visualizar(a: argparse.Namespace) -> int:
    from .viz.pygame_viewer import run_viewer

    return run_viewer(generations=a.geracoes, seed=a.seed)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="medroute", description="MedRoute — VRP hospitalar com GA + LLM")
    sub = p.add_subparsers(dest="cmd")

    def comuns(sp, geracoes=500):
        sp.add_argument("--cenario", help="JSON de cenário (padrão: cenário sintético semente 42)")
        sp.add_argument("--geracoes", type=int, default=geracoes)
        sp.add_argument("--populacao", type=int, default=120)
        sp.add_argument("--seed", type=int, default=config.RANDOM_SEED)

    pp = sub.add_parser("pipeline", help="pipeline completo (padrão)")
    comuns(pp)
    pp.add_argument("--sem-llm", action="store_true", help="não chama a LLM")
    pp.add_argument("--sem-semana", action="store_true", help="não simula a semana")
    pp.add_argument("--sem-ortools", action="store_true")
    pp.add_argument("--modo-llm", choices=("auto", "llm", "offline"), default="auto")
    pp.set_defaults(func=cmd_pipeline)

    po = sub.add_parser("otimizar", help="só roda o GA e salva plano + mapa")
    comuns(po)
    po.add_argument("--crossover", default="mix", choices=("mix", "ox", "pmx", "erx", "bcrc"))
    po.add_argument("--selecao", default="tournament",
                    choices=("tournament", "roulette", "rank", "truncation"))
    po.add_argument("--mutacao", type=float, default=0.4)
    po.add_argument("--saida")
    po.set_defaults(func=cmd_otimizar)

    pc = sub.add_parser("comparar", help="GA x heurísticas x metaheurística")
    pc.add_argument("--cenario")
    pc.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    pc.set_defaults(func=cmd_comparar)

    ps = sub.add_parser("semana", help="simula a semana e gera o relatório semanal")
    ps.add_argument("--sem-llm", action="store_true")
    ps.add_argument("--modo-llm", choices=("auto", "llm", "offline"), default="auto")
    ps.set_defaults(func=cmd_semana)

    pl = sub.add_parser("llm", help="um produto da LLM sobre o plano do dia")
    pl.add_argument("tarefa", choices=("instrucoes", "relatorio", "sugestoes", "perguntar"))
    pl.add_argument("texto", nargs="*", help="pergunta (para 'perguntar')")
    pl.add_argument("--veiculo", default="V1")
    pl.add_argument("--modo-llm", choices=("auto", "llm", "offline"), default="auto")
    pl.set_defaults(func=cmd_llm)

    pt = sub.add_parser("textos", help="regenera só os textos da LLM do plano do dia")
    pt.add_argument("--modo-llm", choices=("auto", "llm", "offline"), default="auto")
    pt.set_defaults(func=cmd_textos)

    pv = sub.add_parser("visualizar", help="janela pygame com a evolução ao vivo (código base)")
    pv.add_argument("--geracoes", type=int, default=300)
    pv.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    pv.set_defaults(func=cmd_visualizar)
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # console do Windows (cp1252)
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv = ["pipeline", *argv]
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
