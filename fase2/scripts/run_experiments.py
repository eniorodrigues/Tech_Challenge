"""
Experimentos do relatório técnico (comparativo, ablação, escalabilidade).

    python scripts/run_experiments.py              # tudo (~5–10 min, usa todos os núcleos)
    python scripts/run_experiments.py --rapido     # 3 sementes por configuração
    python scripts/run_experiments.py --so comparativo,ablacao

Saídas em ``reports/experimentos/`` (CSV) e ``reports/figures/1x_*.png``.

Experimentos
------------
E1  Comparativo de abordagens no cenário padrão (10 sementes p/ métodos
    estocásticos): GA, Simulated Annealing, busca aleatória com o mesmo
    orçamento, GA na configuração do código base, TSP do código base +
    fatiamento, heurísticas construtivas e OR-Tools.
E2  Ablação do GA: sementes heurísticas, busca local, crossover, seleção,
    taxa de mutação e tamanho de população.
E3  Escalabilidade: 20, 36, 60 e 90 entregas.
E4  Efeito do bug do código base (crossover do pai com ele mesmo).
E5  Objetivo do OR-Tools (só distância + atraso): GA x SA x OR-Tools.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import pandas as pd  # noqa: E402

from medroute import config  # noqa: E402
from medroute.baselines import ortools_available, run_baseline  # noqa: E402
from medroute.ga import GAConfig, GeneticAlgorithm  # noqa: E402
from medroute.legacy_tsp import run_base_tsp  # noqa: E402
from medroute.plan import RoutePlan  # noqa: E402
from medroute.problem import FitnessWeights, Problem  # noqa: E402
from medroute.scenario import default_scenario, scaled_scenario  # noqa: E402

SAIDA = config.REPORTS_DIR / "experimentos"
GA_NOME = "MedRoute (GA memético)"


# ---------------------------------------------------------------------------
# Execução de um trabalho (roda em processo separado)
# ---------------------------------------------------------------------------
def _linha(problema: Problem, rotas, metodo: str, seed, tempo: float, **extra) -> dict:
    ev = problema.evaluate(rotas)
    k = RoutePlan.from_evaluation(problema, ev, metodo, tempo).kpis
    return {"metodo": metodo, "seed": seed, "fitness": round(ev.fitness, 3), "km": k.total_km,
            "custo_rs": k.cost_total_brl, "horas": k.route_hours, "co2_kg": k.co2_kg,
            "no_prazo_pct": k.on_time_pct,
            "criticas_no_prazo_pct": k.on_time_by_priority.get("CRÍTICA", 100.0),
            "atrasos": k.late_count, "violacoes": k.violations, "viavel": ev.feasible,
            "tempo_s": round(tempo, 3), **extra}


def _cenario(spec: dict):
    if spec.get("n"):
        return scaled_scenario(spec["n"], seed=spec.get("cenario_seed", 42))
    return default_scenario()


def job(spec: dict) -> dict:
    tipo = spec["tipo"]
    pesos = FitnessWeights(**spec.get("pesos", {}))
    problema = Problem(_cenario(spec), pesos)
    seed = spec.get("seed", 42)
    extra = {k: spec[k] for k in ("experimento", "config", "n") if k in spec}
    t0 = time.perf_counter()
    if tipo == "ga":
        cfg = GAConfig(seed=seed, **spec.get("ga", {}))
        res = GeneticAlgorithm(problema, cfg).run()
        linha = _linha(problema, res.best_routes, spec["metodo"], seed, res.runtime_s, **extra,
                       geracoes=res.generations_run, avaliacoes=res.evaluations)
        if spec.get("curva"):
            linha["curva"] = json.dumps([round(h.best, 2) for h in res.history])
        return linha
    if tipo == "baseline":
        kw = dict(spec.get("kw", {}))
        kw.setdefault("seed", seed)
        r = run_baseline(spec["nome"], problema, **kw)
        return _linha(problema, r.routes, spec["metodo"], seed, r.runtime_s, **extra)
    if tipo == "tsp_bug":
        res = run_base_tsp(problema.dist_np, generations=spec["geracoes"], seed=seed,
                           fix_crossover_bug=spec["corrigido"])
        return {"metodo": spec["metodo"], "seed": seed, "km_tsp": round(res.best_distance, 2),
                "tempo_s": round(time.perf_counter() - t0, 2), **extra}
    raise ValueError(tipo)


def rodar(specs: list[dict], workers: int) -> pd.DataFrame:
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        linhas = list(ex.map(job, specs, chunksize=1))
    print(f"    {len(specs)} execuções em {time.perf_counter() - t0:.0f} s", flush=True)
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Experimentos
# ---------------------------------------------------------------------------
def e1_comparativo(sementes: list[int], workers: int) -> pd.DataFrame:
    print("\n[E1] Comparativo de abordagens (cenário padrão)", flush=True)
    specs = []
    for s in sementes:
        specs += [
            {"tipo": "ga", "metodo": GA_NOME, "seed": s},
            {"tipo": "ga", "metodo": "GA na configuração do código base", "seed": s,
             "ga": {k: v for k, v in GAConfig.base_code_like(generations=500).to_dict().items()
                    if k not in ("seed",)}},
            {"tipo": "baseline", "nome": "simulated_annealing", "metodo": "Simulated Annealing", "seed": s},
            {"tipo": "baseline", "nome": "busca_aleatoria", "metodo": "Busca aleatória (mesmo orçamento)",
             "seed": s, "kw": {"evaluations": 36_000}},
            {"tipo": "baseline", "nome": "tsp_base_split", "metodo": "TSP do código base + fatiamento",
             "seed": s},
        ]
    for nome, rotulo in (("vizinho_mais_proximo", "Vizinho mais próximo"),
                         ("despachante_prioridade", "Despachante (processo atual)"),
                         ("clarke_wright", "Clarke & Wright"), ("sweep", "Sweep + 2-opt"),
                         ("melhoria_local", "Despachante + busca local")):
        specs.append({"tipo": "baseline", "nome": nome, "metodo": rotulo, "seed": 0})
    df = rodar(specs, workers)
    if ortools_available():
        for tl in (5, 30):
            problema = Problem(default_scenario())
            r = run_baseline("ortools", problema, time_limit_s=tl)
            df = pd.concat([df, pd.DataFrame([_linha(problema, r.routes, f"Google OR-Tools ({tl} s)",
                                                     0, r.runtime_s)])], ignore_index=True)
    return df


def _ga(cfg_extra: dict) -> dict:
    return {"generations": 300, "patience": None, **cfg_extra}


PURO = {"heuristic_seeds": False, "local_search": False, "final_polish": False}

ABLACAO: dict[str, tuple[str, dict]] = {
    # nome: (grupo, parâmetros)
    "Completo (padrão)": ("Componentes", {}),
    "Sem sementes heurísticas": ("Componentes", {"heuristic_seeds": False}),
    "Sem busca local": ("Componentes", {"local_search": False, "final_polish": False}),
    "GA puro (sem ambos)": ("Componentes", PURO),
    "Configuração do código base": ("Componentes", {
        k: v for k, v in GAConfig.base_code_like().to_dict().items()
        if k not in ("seed", "generations", "patience")}),
    "Crossover OX": ("Crossover (GA puro)", {**PURO, "crossover": "ox"}),
    "Crossover PMX": ("Crossover (GA puro)", {**PURO, "crossover": "pmx"}),
    "Crossover ERX": ("Crossover (GA puro)", {**PURO, "crossover": "erx"}),
    "Crossover BCRC": ("Crossover (GA puro)", {**PURO, "crossover": "bcrc"}),
    "Crossover mix": ("Crossover (GA puro)", PURO),
    "Seleção torneio": ("Seleção (GA puro)", {**PURO, "selection": "tournament"}),
    "Seleção roleta (1/f)": ("Seleção (GA puro)", {**PURO, "selection": "roulette"}),
    "Seleção ranking": ("Seleção (GA puro)", {**PURO, "selection": "rank"}),
    "Seleção truncamento (top 10)": ("Seleção (GA puro)", {**PURO, "selection": "truncation"}),
    "Mutação 10%": ("Mutação (GA puro)", {**PURO, "mutation_rate": 0.1}),
    "Mutação 40%": ("Mutação (GA puro)", {**PURO, "mutation_rate": 0.4}),
    "Mutação 80%": ("Mutação (GA puro)", {**PURO, "mutation_rate": 0.8}),
    "Só mutações do código base (troca vizinha)": ("Mutação (GA puro)",
                                                   {**PURO, "mutation": "adjacent_swap"}),
    "População 50": ("População (GA puro)", {**PURO, "population_size": 50}),
    "População 120": ("População (GA puro)", {**PURO, "population_size": 120}),
    "População 250": ("População (GA puro)", {**PURO, "population_size": 250}),
}


def e2_ablacao(sementes: list[int], workers: int) -> pd.DataFrame:
    print("\n[E2] Ablação do GA (300 gerações, sem parada antecipada)", flush=True)
    specs = []
    for nome, (grupo, params) in ABLACAO.items():
        for s in sementes:
            specs.append({"tipo": "ga", "metodo": nome, "config": grupo, "seed": s,
                          "ga": _ga(params), "experimento": "ablacao", "curva": True})
    return rodar(specs, workers)


def e3_escalabilidade(sementes: list[int], workers: int, tamanhos=(20, 36, 60, 90)) -> pd.DataFrame:
    print("\n[E3] Escalabilidade", flush=True)
    specs = []
    for n in tamanhos:
        for s in sementes:
            specs.append({"tipo": "ga", "metodo": GA_NOME, "seed": s, "n": n,
                          "ga": {"generations": 600, "patience": 250}})
            specs.append({"tipo": "baseline", "nome": "simulated_annealing",
                          "metodo": "Simulated Annealing", "seed": s, "n": n,
                          "kw": {"iterations": 150_000 * max(1, n // 36)}})
        for nome, rotulo in (("despachante_prioridade", "Despachante (processo atual)"),
                             ("clarke_wright", "Clarke & Wright"), ("sweep", "Sweep + 2-opt")):
            specs.append({"tipo": "baseline", "nome": nome, "metodo": rotulo, "seed": 0, "n": n})
    df = rodar(specs, workers)
    if ortools_available():
        for n in tamanhos:
            problema = Problem(scaled_scenario(n))
            r = run_baseline("ortools", problema, time_limit_s=30)
            df = pd.concat([df, pd.DataFrame([_linha(problema, r.routes, "Google OR-Tools (30 s)", 0,
                                                     r.runtime_s, n=n)])], ignore_index=True)
    return df


def e4_bug(sementes: list[int], workers: int) -> pd.DataFrame:
    print("\n[E4] Bug do crossover do código base", flush=True)
    specs = []
    for s in sementes:
        specs.append({"tipo": "tsp_bug", "metodo": "TSP base como fornecido (pai × pai)", "seed": s,
                      "geracoes": 600, "corrigido": False})
        specs.append({"tipo": "tsp_bug", "metodo": "TSP base com crossover corrigido", "seed": s,
                      "geracoes": 600, "corrigido": True})
    return rodar(specs, workers)


def e5_objetivo_distancia(sementes: list[int], workers: int) -> pd.DataFrame:
    print("\n[E5] Objetivo só distância + atraso (o do OR-Tools)", flush=True)
    pesos = {"priority_time": 0.0}
    specs = []
    for s in sementes:
        specs.append({"tipo": "ga", "metodo": GA_NOME, "seed": s, "pesos": pesos})
        specs.append({"tipo": "baseline", "nome": "simulated_annealing", "metodo": "Simulated Annealing",
                      "seed": s, "pesos": pesos})
    df = rodar(specs, workers)
    if ortools_available():
        problema = Problem(default_scenario(), FitnessWeights(**pesos))
        r = run_baseline("ortools", problema, time_limit_s=30)
        df = pd.concat([df, pd.DataFrame([_linha(problema, r.routes, "Google OR-Tools (30 s)", 0,
                                                 r.runtime_s)])], ignore_index=True)
    return df


# ---------------------------------------------------------------------------
# Resumos e figuras
# ---------------------------------------------------------------------------
def resumo(df: pd.DataFrame, chave: list[str]) -> pd.DataFrame:
    agg = df.groupby(chave, sort=False).agg(
        execucoes=("fitness", "size"), fitness_media=("fitness", "mean"),
        fitness_dp=("fitness", "std"), fitness_min=("fitness", "min"),
        fitness_max=("fitness", "max"), km=("km", "mean"), custo_rs=("custo_rs", "mean"),
        no_prazo_pct=("no_prazo_pct", "mean"), criticas_no_prazo_pct=("criticas_no_prazo_pct", "mean"),
        violacoes=("violacoes", "mean"), viavel_pct=("viavel", "mean"), tempo_s=("tempo_s", "mean"),
    ).reset_index()
    agg["viavel_pct"] *= 100
    return agg.round(3)


def figuras(dfs: dict[str, pd.DataFrame]) -> None:
    import numpy as np

    from medroute.viz import plots

    fig_dir = config.FIGURES_DIR
    if "comparativo" in dfs:
        r = resumo(dfs["comparativo"], ["metodo"])
        r2 = r.rename(columns={"fitness_media": "fitness"})
        plots.plot_methods_comparison(
            r2.assign(violacoes=r2["violacoes"]), GA_NOME, fig_dir / "10_comparativo_metodos.png",
            title="Comparativo de abordagens — médias de 10 execuções (cenário padrão)")
        d = dfs["comparativo"].rename(columns={"metodo": "config"})
        ordem = r.sort_values("fitness_media")["metodo"].tolist()
        plots.plot_fitness_distribution(d, fig_dir / "11_dispersao_metodos.png",
                                        title="Fitness final por abordagem (cada ponto = uma execução)",
                                        order=ordem)
    if "ablacao" in dfs:
        d = dfs["ablacao"].rename(columns={"metodo": "config_nome"})
        d = d.assign(config=d["config_nome"])
        plots.plot_fitness_distribution(d, fig_dir / "12_ablacao_ga.png",
                                        title="Ablação do GA — fitness final após 300 gerações",
                                        order=list(ABLACAO))
        curvas = {}
        for nome in ("Completo (padrão)", "GA puro (sem ambos)", "Configuração do código base"):
            sub = dfs["ablacao"][dfs["ablacao"]["metodo"] == nome]
            curvas[nome] = [json.loads(c) for c in sub["curva"]]
        plots.plot_convergence_compare(curvas, fig_dir / "13_convergencia_configs.png",
                                       title="Convergência média (faixa = mín–máx entre sementes)")
    if "escalabilidade" in dfs:
        d = dfs["escalabilidade"]
        melhor = d.groupby("n")["fitness"].min()
        d = d.assign(gap_pct=100 * (d["fitness"] - d["n"].map(melhor)) / d["n"].map(melhor))
        g = d.groupby(["n", "metodo"], sort=False)[["gap_pct", "tempo_s"]].mean().reset_index()
        g = g.rename(columns={"n": "entregas"})
        # Heurísticas construtivas ficam 100%–9000% acima (atrasos e violações):
        # aparecem só na tabela; o gráfico compara as abordagens competitivas.
        g = g[g["metodo"].isin([GA_NOME, "Simulated Annealing", "Google OR-Tools (30 s)"])]
        plots.plot_scalability(g, GA_NOME, fig_dir / "14_escalabilidade.png")
        plots.plot_scalability(g, GA_NOME, fig_dir / "15_escalabilidade_tempo.png", y="tempo_s",
                               ylabel="tempo médio de execução (s)",
                               title="Escalabilidade — tempo de execução por tamanho do problema")
    _ = np  # (import mantido para extensões)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rapido", action="store_true", help="3 sementes em vez de 10")
    ap.add_argument("--so", default="comparativo,ablacao,escalabilidade,bug,objetivo")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--so-figuras", action="store_true",
                    help="refaz só as figuras a partir dos CSVs já gravados")
    a = ap.parse_args()
    if a.so_figuras:
        arquivos = {"comparativo": "e1_comparativo_execucoes.csv", "ablacao": "e2_ablacao_execucoes.csv",
                    "escalabilidade": "e3_escalabilidade_execucoes.csv"}
        figuras({k: pd.read_csv(SAIDA / v) for k, v in arquivos.items() if (SAIDA / v).exists()})
        print("figuras refeitas")
        return 0
    sementes = list(range(1, 4 if a.rapido else 11))
    SAIDA.mkdir(parents=True, exist_ok=True)
    config.ensure_dirs()
    quais = set(a.so.split(","))
    dfs: dict[str, pd.DataFrame] = {}
    t0 = time.perf_counter()
    if "comparativo" in quais:
        dfs["comparativo"] = e1_comparativo(sementes, a.workers)
        dfs["comparativo"].to_csv(SAIDA / "e1_comparativo_execucoes.csv", index=False)
        r = resumo(dfs["comparativo"], ["metodo"]).sort_values("fitness_media")
        r.to_csv(SAIDA / "e1_comparativo_resumo.csv", index=False)
        print(r[["metodo", "execucoes", "fitness_media", "fitness_dp", "fitness_min", "km",
                 "no_prazo_pct", "criticas_no_prazo_pct", "violacoes", "tempo_s"]].to_string(index=False))
        try:
            from scipy.stats import mannwhitneyu

            ga = dfs["comparativo"].query("metodo == @GA_NOME")["fitness"]
            sa = dfs["comparativo"].query("metodo == 'Simulated Annealing'")["fitness"]
            u = mannwhitneyu(ga, sa, alternative="two-sided")
            teste = {"teste": "Mann-Whitney U (bicaudal)", "ga_mediana": float(ga.median()),
                     "sa_mediana": float(sa.median()), "U": float(u.statistic), "p_valor": float(u.pvalue)}
            (SAIDA / "e1_teste_estatistico.json").write_text(json.dumps(teste, indent=2), encoding="utf-8")
            print(f"    GA x SA: {teste}")
        except Exception as exc:  # pragma: no cover
            print("    (teste estatístico indisponível)", exc)
    if "ablacao" in quais:
        dfs["ablacao"] = e2_ablacao(sementes, a.workers)
        dfs["ablacao"].to_csv(SAIDA / "e2_ablacao_execucoes.csv", index=False)
        r = resumo(dfs["ablacao"], ["config", "metodo"])
        r.to_csv(SAIDA / "e2_ablacao_resumo.csv", index=False)
        print(r[["config", "metodo", "fitness_media", "fitness_dp", "fitness_min", "km", "viavel_pct",
                 "tempo_s"]].to_string(index=False))
    if "escalabilidade" in quais:
        dfs["escalabilidade"] = e3_escalabilidade(sementes[:5], a.workers)
        dfs["escalabilidade"].to_csv(SAIDA / "e3_escalabilidade_execucoes.csv", index=False)
        r = resumo(dfs["escalabilidade"], ["n", "metodo"])
        r.to_csv(SAIDA / "e3_escalabilidade_resumo.csv", index=False)
        print(r[["n", "metodo", "fitness_media", "fitness_min", "km", "no_prazo_pct", "violacoes",
                 "tempo_s"]].to_string(index=False))
    if "bug" in quais:
        d = e4_bug(sementes, a.workers)
        d.to_csv(SAIDA / "e4_bug_codigo_base.csv", index=False)
        print(d.groupby("metodo")["km_tsp"].agg(["mean", "std", "min", "max"]).round(2).to_string())
    if "objetivo" in quais:
        d = e5_objetivo_distancia(sementes[:5], a.workers)
        d.to_csv(SAIDA / "e5_objetivo_distancia.csv", index=False)
        print(resumo(d, ["metodo"])[["metodo", "fitness_media", "fitness_min", "km"]].to_string(index=False))
    figuras(dfs)
    print(f"\nExperimentos concluídos em {time.perf_counter() - t0:.0f} s -> {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
