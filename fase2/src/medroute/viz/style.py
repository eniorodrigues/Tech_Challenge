"""
Identidade visual dos gráficos e mapas.

Paleta validada com o checador de daltonismo (OKLab, ΔE): as cinco cores dos
veículos passam no teste **todos-os-pares** (num mapa qualquer rota pode
cruzar qualquer outra), com pior par CVD ΔE 6,9 — por isso cada parada leva
também um **rótulo** com o veículo e a ordem (codificação secundária), e o
mapa interativo permite ligar/desligar cada veículo.

A cor carrega **identidade do veículo**. Prioridade é codificada por
**forma** (◆ crítica, ▲ alta, ● normal) e requisitos por **ícone** (❄ cadeia
fria, 🔒 controlado) — nunca só por cor. Atraso é estado (status), sempre
com ícone ⚠ e texto.
"""

from __future__ import annotations

import matplotlib as mpl

# Superfície e tinta (modo claro — os PNGs vão para relatório e vídeo).
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# Cores por veículo, na ordem da frota padrão (V1..V5).
VEHICLE_COLORS = ["#2a78d6", "#4a3aa7", "#1baf7a", "#eda100", "#e34948"]
# Frotas maiores (cenários de escalabilidade) reaproveitam com rótulo obrigatório.
EXTRA_COLORS = ["#eb6834", "#e87ba4", "#008300"]

# Ênfase: o método em destaque em azul, o resto em cinza.
ACCENT = "#2a78d6"
DEEMPHASIS = "#b9b8b1"

# Rampa ordinal de prioridade (azul claro → escuro) para o Gantt.
PRIORITY_RAMP = {"NORMAL": "#86b6ef", "ALTA": "#3987e5", "CRÍTICA": "#104281"}
PRIORITY_MARKER = {"CRÍTICA": "D", "ALTA": "^", "NORMAL": "o"}
PRIORITY_SYMBOL = {"CRÍTICA": "◆", "ALTA": "▲", "NORMAL": "●"}

# Status (reservado: só para estado bom/ruim, sempre com ícone + texto).
STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_CRITICAL = "#d03b3b"


def vehicle_color(index: int) -> str:
    cores = VEHICLE_COLORS + EXTRA_COLORS
    return cores[index % len(cores)]


def apply_style() -> None:
    """rcParams do Matplotlib: marcas finas, grade discreta, fonte do sistema."""
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK_2,
        "axes.titlecolor": INK,
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "axes.titlelocation": "left",
        "axes.labelsize": 10.5,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.frameon": False,
        "legend.fontsize": 9.5,
        "legend.labelcolor": INK_2,
        "lines.linewidth": 2.0,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
        "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
        "text.color": INK,
        "figure.dpi": 110,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
    })
