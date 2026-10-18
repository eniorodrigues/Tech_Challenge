"""
Gráficos de análise (Matplotlib, PNG).

Convenções: marcas finas, grade em linha fina e discreta, um eixo por gráfico,
legenda sempre que houver duas séries ou mais, rótulos diretos só onde
contam a história. Comparações usam **ênfase**: o método em destaque em azul,
os demais em cinza.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from ..plan import RoutePlan
from . import style


def _salvar(fig: plt.Figure, path: str | Path | None) -> plt.Figure:
    if path is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path)
    return fig


# ---------------------------------------------------------------------------
# Convergência
# ---------------------------------------------------------------------------
def plot_convergence(history: Sequence[dict], path: str | Path | None = None,
                     title: str = "Convergência do algoritmo genético") -> plt.Figure:
    style.apply_style()
    h = pd.DataFrame(history)
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.plot(h["generation"], h["mean"], color=style.DEEMPHASIS, linewidth=1.6,
            label="média da população")
    ax.plot(h["generation"], h["best"], color=style.ACCENT, linewidth=2.2,
            label="melhor indivíduo")
    ax.set_yscale("log")
    ax.set_xlabel("geração")
    ax.set_ylabel("fitness (escala log; menor é melhor)")
    ax.set_title(title)
    viavel = h.index[h["best_feasible"]].tolist()
    if viavel:
        g = int(h.loc[viavel[0], "generation"])
        ax.axvline(g, color=style.AXIS, linewidth=1)
        ax.text(g, ax.get_ylim()[1], f"  1ª solução viável (geração {g})", va="top",
                fontsize=9, color=style.INK_2)
    fim = h.iloc[-1]
    ax.annotate(f"{fim['best']:.1f}", (fim["generation"], fim["best"]),
                xytext=(6, 0), textcoords="offset points", va="center", fontsize=9.5,
                color=style.INK)
    ax.legend(loc="upper right")
    fig.tight_layout()
    return _salvar(fig, path)


def plot_convergence_compare(curves: dict[str, list[list[float]]], path: str | Path | None = None,
                             title: str = "Convergência por configuração (média de sementes)",
                             ylabel: str = "melhor fitness (escala log)") -> plt.Figure:
    """``curves[nome]`` = lista de séries "melhor até agora" (uma por semente)."""
    style.apply_style()
    fig, ax = plt.subplots(figsize=(10, 5.4))
    cores = [style.ACCENT, "#eb6834", "#1baf7a", "#4a3aa7"]
    for (nome, series), cor in zip(curves.items(), cores):
        n = max(len(s) for s in series)
        m = np.array([np.pad(s, (0, n - len(s)), mode="edge") for s in series], dtype=float)
        x = np.arange(n)
        med = m.mean(axis=0)
        ax.fill_between(x, m.min(axis=0), m.max(axis=0), color=cor, alpha=0.10, linewidth=0)
        ax.plot(x, med, color=cor, linewidth=2, label=nome)
        ax.annotate(f"{med[-1]:.0f}", (x[-1], med[-1]), xytext=(5, 0),
                    textcoords="offset points", va="center", fontsize=9, color=style.INK)
    ax.set_yscale("log")
    ax.set_xlabel("geração")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(loc="upper right")
    fig.tight_layout()
    return _salvar(fig, path)


# ---------------------------------------------------------------------------
# Comparativo entre abordagens
# ---------------------------------------------------------------------------
def plot_methods_comparison(df: pd.DataFrame, highlight: str, path: str | Path | None = None,
                            title: str = "Comparativo de abordagens — mesmo cenário") -> plt.Figure:
    """Três painéis com o mesmo eixo de métodos: km, % no prazo, violações.

    ``df`` precisa das colunas ``metodo``, ``km``, ``no_prazo_pct`` e
    ``violacoes`` (médias, se houver várias sementes).
    """
    style.apply_style()
    d = df.sort_values("fitness", ascending=False).reset_index(drop=True)
    y = np.arange(len(d))
    cores = [style.ACCENT if m == highlight else style.DEEMPHASIS for m in d["metodo"]]
    fig, axes = plt.subplots(1, 3, figsize=(15, 0.55 * len(d) + 1.9), sharey=True,
                             gridspec_kw={"width_ratios": [1.2, 1, 0.8]})
    inteiro = bool((d["violacoes"] % 1 == 0).all())
    paineis = (("km", "distância total (km)", "{:.0f}"),
               ("no_prazo_pct", "entregas no prazo (%)", "{:.0f}%"),
               ("violacoes", "violações de restrições duras", "{:.0f}" if inteiro else "{:.1f}"))
    for ax, (col, rotulo, fmt) in zip(axes, paineis):
        ax.barh(y, d[col], height=0.5, color=cores)
        ax.set_title(rotulo, fontsize=11)
        ax.grid(axis="y", visible=False)
        lim = max(d[col].max(), 1e-9)
        for yi, v in zip(y, d[col]):
            ax.text(v + lim * 0.015, yi, fmt.format(v), va="center", fontsize=9,
                    color=style.INK_2)
        ax.set_xlim(0, lim * 1.18)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(d["metodo"])
    fig.suptitle(title, x=0.01, ha="left", fontsize=14, weight="bold")
    fig.tight_layout()
    return _salvar(fig, path)


def plot_fitness_distribution(df: pd.DataFrame, path: str | Path | None = None,
                              title: str = "Ablação do GA — fitness final por configuração",
                              order: list[str] | None = None) -> plt.Figure:
    """Pontos (uma semente cada) + mediana, por configuração."""
    style.apply_style()
    grupos = order or list(dict.fromkeys(df["config"]))
    fig, ax = plt.subplots(figsize=(11, 0.5 * len(grupos) + 1.6))
    rng = np.random.default_rng(0)
    for i, g in enumerate(grupos):
        v = df.loc[df["config"] == g, "fitness"].to_numpy()
        ax.scatter(v, i + rng.uniform(-0.12, 0.12, len(v)), s=36, color=style.ACCENT,
                   edgecolors="white", linewidths=1.2, zorder=3, alpha=0.9)
        med = float(np.median(v))
        ax.plot([med, med], [i - 0.3, i + 0.3], color=style.INK, linewidth=2, zorder=4)
        ax.text(v.max(), i, f"   mediana {med:.1f}", va="center", fontsize=9, color=style.INK_2)
    ax.set_yticks(range(len(grupos)))
    ax.set_yticklabels(grupos)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel("fitness final (escala log; menor é melhor) — cada ponto é uma semente")
    ax.set_title(title)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return _salvar(fig, path)


# ---------------------------------------------------------------------------
# Plano: linha do tempo (Gantt) e ocupação
# ---------------------------------------------------------------------------
def _hm(hhmm: str) -> float:
    h, m = hhmm.split(":")
    return int(h) + int(m) / 60


def plot_gantt(plan: RoutePlan, path: str | Path | None = None,
               title: str | None = None) -> plt.Figure:
    """Linha do tempo de cada veículo: deslocamento, espera e atendimento."""
    style.apply_style()
    rotas = [r for r in plan.routes if r.used]
    fig, ax = plt.subplots(figsize=(14, 0.95 * len(rotas) + 1.8))
    inicio = _hm(plan.scenario.shift_start)
    fim_turno = inicio + plan.scenario.shift_minutes / 60
    for yi, r in enumerate(rotas):
        ax.plot([inicio, _hm(r.return_time)], [yi, yi], color=style.AXIS, linewidth=1.5, zorder=1)
        for s in r.stops:
            t0, t1 = _hm(s.start), _hm(s.departure)
            if s.wait_min > 0.5:
                ax.plot([_hm(s.arrival), t0], [yi, yi], color=style.MUTED, linewidth=4,
                        alpha=0.5, zorder=2, solid_capstyle="butt")
            ax.barh(yi, t1 - t0, left=t0, height=0.42, color=style.PRIORITY_RAMP[s.priority],
                    edgecolor=style.SURFACE, linewidth=1, zorder=3)
            if s.priority == "CRÍTICA" and s.deadline:
                ax.plot([_hm(s.deadline)] * 2, [yi - 0.3, yi + 0.3], color=style.INK,
                        linewidth=1, zorder=4)
            if s.lateness_min > 0.5:
                ax.text(t1, yi + 0.33, f"⚠ +{s.lateness_min:.0f} min", fontsize=8.5,
                        color=style.INK, family="DejaVu Sans")
        ax.text(_hm(r.return_time) + 0.05, yi, f" volta {r.return_time}", va="center",
                fontsize=8.8, color=style.INK_2)
    ax.axvline(fim_turno, color=style.STATUS_CRITICAL, linewidth=1)
    ax.text(fim_turno, len(rotas) - 0.45, " fim do turno", fontsize=8.8, color=style.INK_2)
    ax.set_yticks(range(len(rotas)))
    ax.set_yticklabels([f"{r.vehicle_id} · {r.vehicle_name}" for r in rotas])
    ax.invert_yaxis()
    horas = np.arange(int(inicio), int(fim_turno) + 2)
    ax.set_xticks(horas)
    ax.set_xticklabels([f"{h:02d}:00" for h in horas])
    ax.set_xlim(inicio - 0.1, fim_turno + 0.6)
    ax.grid(axis="y", visible=False)
    ax.set_title(title or f"Linha do tempo das rotas — {plan.method}")
    legenda = [Patch(color=c, label=f"atendimento — prioridade {p.lower()}")
               for p, c in style.PRIORITY_RAMP.items()]
    legenda.append(Patch(color=style.MUTED, alpha=0.5, label="espera pela janela de horário"))
    legenda.append(plt.Line2D([], [], color=style.INK, linewidth=1, label="prazo (SLA) das críticas"))
    ax.legend(handles=legenda, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    fig.tight_layout()
    return _salvar(fig, path)


def plot_utilization(plan: RoutePlan, path: str | Path | None = None) -> plt.Figure:
    """Ocupação de carga e de autonomia por veículo (100% = limite)."""
    style.apply_style()
    rotas = plan.routes
    y = np.arange(len(rotas))
    fig, ax = plt.subplots(figsize=(10, 0.7 * len(rotas) + 1.8))
    h = 0.32
    ax.barh(y - h / 2 - 0.02, [r.load_pct for r in rotas], height=h, color=style.ACCENT,
            label="carga usada (% da capacidade)")
    ax.barh(y + h / 2 + 0.02, [r.range_pct for r in rotas], height=h, color="#1baf7a",
            label="km rodados (% da autonomia)")
    for yi, r in zip(y, rotas):
        ax.text(r.load_pct + 1, yi - h / 2 - 0.02, f"{r.load_pct:.0f}%", va="center",
                fontsize=8.8, color=style.INK_2)
        ax.text(r.range_pct + 1, yi + h / 2 + 0.02, f"{r.range_pct:.0f}%", va="center",
                fontsize=8.8, color=style.INK_2)
    ax.axvline(100, color=style.INK, linewidth=1)
    ax.text(100, -0.75, " limite", fontsize=8.8, color=style.INK_2)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r.vehicle_id} · {r.vehicle_name}" for r in rotas])
    ax.invert_yaxis()
    ax.set_xlim(0, 118)
    ax.set_xlabel("% do limite do veículo")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Ocupação da frota — {plan.method}")
    ax.legend(loc="lower right")
    fig.tight_layout()
    return _salvar(fig, path)


# ---------------------------------------------------------------------------
# Escalabilidade e semana
# ---------------------------------------------------------------------------
def plot_scalability(df: pd.DataFrame, highlight: str, path: str | Path | None = None,
                     y: str = "gap_pct",
                     ylabel: str = "distância do melhor resultado conhecido (%)",
                     title: str = "Escalabilidade — qualidade relativa por tamanho do problema",
                     log: bool = False) -> plt.Figure:
    """Uma métrica por tamanho de instância (``df``: ``entregas``, ``metodo``, ``y``)."""
    style.apply_style()
    fig, ax = plt.subplots(figsize=(10, 5.2))
    metodos = list(dict.fromkeys(df["metodo"]))
    cores_extra = ["#eb6834", "#1baf7a", "#4a3aa7", "#e87ba4"]
    j = 0
    for m in metodos:
        sub = df[df["metodo"] == m].sort_values("entregas")
        if m == highlight:
            cor, lw = style.ACCENT, 2.6
        else:
            cor, lw = cores_extra[j % len(cores_extra)], 1.8
            j += 1
        ax.plot(sub["entregas"], sub[y], marker="o", markersize=6, color=cor,
                linewidth=lw, label=m, markeredgecolor="white", markeredgewidth=1.2)
        fim = sub.iloc[-1]
        ax.annotate(f"{fim[y]:.1f}", (fim["entregas"], fim[y]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color=style.INK_2)
    if log:
        ax.set_yscale("log")
    ax.set_xlabel("número de entregas na instância")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(loc="upper left")
    fig.tight_layout()
    return _salvar(fig, path)


def plot_weekly(df: pd.DataFrame, path: str | Path | None = None) -> plt.Figure:
    """km por dia: processo atual × GA (duas séries, legenda + rótulos)."""
    style.apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(df))
    w = 0.34
    ax.bar(x - w / 2 - 0.02, df["km_atual"], width=w, color=style.DEEMPHASIS,
           label="processo atual (despachante)")
    ax.bar(x + w / 2 + 0.02, df["km_ga"], width=w, color=style.ACCENT, label="MedRoute (GA)")
    for xi, a, g in zip(x, df["km_atual"], df["km_ga"]):
        ax.text(xi + w / 2 + 0.02, g + 3, f"−{100 * (a - g) / a:.0f}%", ha="center",
                fontsize=9, color=style.INK)
    ax.set_xticks(x)
    ax.set_xticklabels(df["dia"])
    ax.set_ylabel("km rodados no dia")
    ax.set_title("Semana operacional — distância percorrida por dia")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return _salvar(fig, path)
