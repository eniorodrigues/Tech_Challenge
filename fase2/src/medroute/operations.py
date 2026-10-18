"""
Simulação de uma semana de operação: alimenta o relatório semanal.

Para cada dia útil gera um cenário (volumes diferentes), roteiriza com o
**processo atual** (despachante: urgentes primeiro + vizinho mais próximo) e
com o **MedRoute (GA)**, e registra os KPIs dos dois. O resultado é a tabela
``reports/operacao_semanal.csv`` e o dicionário que vai para a LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from .baselines import nearest_neighbor
from .ga import GAConfig, GeneticAlgorithm
from .plan import RoutePlan
from .problem import Problem
from .scenario import DIAS_SEMANA, weekly_scenarios

METODO_ATUAL = "Processo atual (despachante)"
METODO_GA = "MedRoute (algoritmo genético)"


@dataclass
class WeekResult:
    table: pd.DataFrame
    summary: dict[str, Any]
    plans_ga: list[RoutePlan] = field(default_factory=list)
    plans_atual: list[RoutePlan] = field(default_factory=list)


def plan_pair(problem: Problem, config: GAConfig) -> tuple[RoutePlan, RoutePlan]:
    atual = RoutePlan.from_evaluation(problem, problem.evaluate(nearest_neighbor(problem, True)),
                                      METODO_ATUAL)
    res = GeneticAlgorithm(problem, config).run()
    ga = RoutePlan.from_evaluation(problem, res.evaluation, METODO_GA, res.runtime_s)
    return ga, atual


def simulate_week(config: GAConfig | None = None, seed: int = 100,
                  progress: Callable[[int, str], None] | None = None) -> WeekResult:
    cfg = config or GAConfig(generations=300, patience=120)
    linhas = []
    planos_ga, planos_atual = [], []
    for i, (dia, sc) in enumerate(zip(DIAS_SEMANA, weekly_scenarios(seed))):
        if progress:
            progress(i, dia)
        ga, atual = plan_pair(Problem(sc), cfg)
        planos_ga.append(ga)
        planos_atual.append(atual)
        a, g = atual.kpis, ga.kpis
        linhas.append({
            "dia": dia, "data": sc.date, "entregas": g.deliveries,
            "criticas": sum(1 for d in sc.deliveries if d.priority.label == "CRÍTICA"),
            "km_atual": a.total_km, "km_ga": g.total_km,
            "custo_atual": a.cost_total_brl, "custo_ga": g.cost_total_brl,
            "horas_atual": a.route_hours, "horas_ga": g.route_hours,
            "co2_atual": a.co2_kg, "co2_ga": g.co2_kg,
            "sla_atual": a.on_time_pct, "sla_ga": g.on_time_pct,
            "criticas_prazo_atual": a.on_time_by_priority.get("CRÍTICA", 100.0),
            "criticas_prazo_ga": g.on_time_by_priority.get("CRÍTICA", 100.0),
            "violacoes_atual": a.violations, "violacoes_ga": g.violations,
            "veiculos_ga": g.vehicles_used, "tempo_ga_s": round(ga.runtime_s, 1),
        })
    df = pd.DataFrame(linhas)
    df["km_economia_pct"] = (100 * (df["km_atual"] - df["km_ga"]) / df["km_atual"]).round(1)
    return WeekResult(table=df, summary=summarize_week(df), plans_ga=planos_ga,
                      plans_atual=planos_atual)


def summarize_week(df: pd.DataFrame) -> dict[str, Any]:
    """Totais e médias da semana no formato que a LLM recebe."""
    tot = {
        "entregas": int(df["entregas"].sum()),
        "criticas": int(df["criticas"].sum()),
        "km_atual": round(float(df["km_atual"].sum()), 1),
        "km_ga": round(float(df["km_ga"].sum()), 1),
        "custo_atual": round(float(df["custo_atual"].sum()), 2),
        "custo_ga": round(float(df["custo_ga"].sum()), 2),
        "horas_atual": round(float(df["horas_atual"].sum()), 1),
        "horas_ga": round(float(df["horas_ga"].sum()), 1),
        "co2_atual": round(float(df["co2_atual"].sum()), 1),
        "co2_ga": round(float(df["co2_ga"].sum()), 1),
        "sla_atual": round(float((df["sla_atual"] * df["entregas"]).sum() / df["entregas"].sum()), 1),
        "sla_ga": round(float((df["sla_ga"] * df["entregas"]).sum() / df["entregas"].sum()), 1),
        "violacoes_atual": int(df["violacoes_atual"].sum()),
        "violacoes_ga": int(df["violacoes_ga"].sum()),
    }
    tot["km_economia"] = round(tot["km_atual"] - tot["km_ga"], 1)
    tot["km_economia_pct"] = round(100 * tot["km_economia"] / tot["km_atual"], 1)
    tot["custo_economia"] = round(tot["custo_atual"] - tot["custo_ga"], 2)
    tot["horas_economia"] = round(tot["horas_atual"] - tot["horas_ga"], 1)
    tot["co2_economia"] = round(tot["co2_atual"] - tot["co2_ga"], 1)
    dias = df.to_dict(orient="records")
    return {
        "periodo": f"{df['data'].iloc[0]} a {df['data'].iloc[-1]}",
        "totais": tot,
        "dias": [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in d.items()} for d in dias],
        "dia_mais_carregado": str(df.loc[df["entregas"].idxmax(), "dia"]),
        "maior_economia_dia": str(df.loc[df["km_economia_pct"].idxmax(), "dia"]),
    }
