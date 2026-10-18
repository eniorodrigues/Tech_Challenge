"""
Mapa estático (PNG) das rotas — para o relatório, o README e o vídeo.

Layout 16:9: mapa à esquerda (basemap OpenStreetMap), painel à direita com a
legenda dos veículos (cor + resumo da rota), das formas de prioridade e dos
ícones de requisito. Cada parada leva o número da ordem de visita, então a
rota pode ser seguida mesmo sem distinguir cores.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.lines import Line2D

from ..domain import CONTROLADO, REFRIGERADO
from ..plan import RoutePlan
from . import style
from .tiles import ATTRIBUTION, Basemap, build_basemap

HALO = [patheffects.withStroke(linewidth=3.2, foreground="white")]
HALO_FINO = [patheffects.withStroke(linewidth=2.2, foreground="white")]
FONTE_SIMBOLOS = "DejaVu Sans"   # tem ❄ e ℞


def _coords(plan: RoutePlan) -> tuple[list[float], list[float]]:
    dep = plan.scenario.depot
    lats = [dep.lat] + [d.lat for d in plan.scenario.deliveries]
    lons = [dep.lon] + [d.lon for d in plan.scenario.deliveries]
    return lats, lons


def draw_routes_on_ax(
    ax: plt.Axes,
    plan: RoutePlan,
    basemap: Basemap | None,
    only_vehicle: str | None = None,
    show_numbers: bool = True,
    show_late: bool = True,
    linewidth: float = 2.6,
    marker_scale: float = 1.0,
    routes_override: list[list[str]] | None = None,
) -> None:
    """Desenha central, rotas e paradas num eixo já criado.

    ``routes_override`` permite desenhar uma solução intermediária (lista de
    IDs de entrega por veículo) — usado na animação da evolução do GA.
    """
    sc = plan.scenario
    if basemap is not None:
        proj = basemap.project()
        w, h = basemap.image.size
        ax.imshow(basemap.image, extent=(0, w, h, 0), zorder=0)
        ax.set_xlim(0, w)
        ax.set_ylim(h, 0)
    else:
        def proj(lat: float, lon: float) -> tuple[float, float]:
            return lon * 1000.0, -lat * 1000.0
        lats, lons = _coords(plan)
        xs = [lo * 1000 for lo in lons]
        ys = [-la * 1000 for la in lats]
        mx = (max(xs) - min(xs)) * 0.08
        my = (max(ys) - min(ys)) * 0.08
        ax.set_xlim(min(xs) - mx, max(xs) + mx)
        ax.set_ylim(max(ys) + my, min(ys) - my)
        ax.set_facecolor("#f2f2f0")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)

    dep = sc.depot
    dx, dy = proj(dep.lat, dep.lon)
    entregas = {d.id: d for d in sc.deliveries}

    if routes_override is not None:
        rotas = [(i, sc.vehicles[i].id, ids) for i, ids in enumerate(routes_override)]
        atrasos: dict[str, float] = {}
    else:
        rotas = [(i, r.vehicle_id, [s.delivery_id for s in r.stops])
                 for i, r in enumerate(plan.routes)]
        atrasos = {s.delivery_id: s.lateness_min for r in plan.routes for s in r.stops}

    for i, vid, ids in rotas:
        if not ids or (only_vehicle and vid != only_vehicle):
            continue
        cor = style.vehicle_color(i)
        pts = [(dx, dy)] + [proj(entregas[e].lat, entregas[e].lon) for e in ids] + [(dx, dy)]
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color="white", linewidth=linewidth + 2.6, alpha=0.9, zorder=2,
                solid_capstyle="round")
        ax.plot(xs, ys, color=cor, linewidth=linewidth, alpha=0.95, zorder=3,
                solid_capstyle="round", solid_joinstyle="round")
        # Setas de sentido no meio de alguns trechos.
        for (x0, y0), (x1, y1) in list(zip(pts[:-1], pts[1:]))[::2]:
            if abs(x1 - x0) + abs(y1 - y0) < 25:
                continue
            ax.annotate("", xy=(x0 + 0.56 * (x1 - x0), y0 + 0.56 * (y1 - y0)),
                        xytext=(x0 + 0.44 * (x1 - x0), y0 + 0.44 * (y1 - y0)),
                        arrowprops=dict(arrowstyle="-|>", color=cor, lw=0,
                                        mutation_scale=13 * marker_scale),
                        zorder=4)
        for seq, e in enumerate(ids, start=1):
            d = entregas[e]
            x, y = proj(d.lat, d.lon)
            mk = style.PRIORITY_MARKER[d.priority.label]
            tam = {"D": 95, "^": 95, "o": 70}[mk] * marker_scale
            ax.scatter([x], [y], s=tam, marker=mk, c=cor, edgecolors="white",
                       linewidths=1.6, zorder=6)
            if show_numbers:
                ax.text(x + 7 * marker_scale, y - 7 * marker_scale, str(seq),
                        fontsize=8.2 * marker_scale, color=style.INK, weight="bold",
                        zorder=7, path_effects=HALO_FINO)
            simbolos = ("❄" if REFRIGERADO in d.requirements else "") + \
                       ("℞" if CONTROLADO in d.requirements else "")
            if simbolos:
                ax.text(x - 8 * marker_scale, y - 8 * marker_scale, simbolos, ha="right",
                        fontsize=8.5 * marker_scale, color=style.INK_2, zorder=7,
                        family=FONTE_SIMBOLOS, path_effects=HALO_FINO)
            if show_late and atrasos.get(e, 0) > 0.5:
                ax.scatter([x], [y], s=tam * 2.6, marker="o", facecolors="none",
                           edgecolors=style.STATUS_CRITICAL, linewidths=1.8, zorder=5)
                ax.text(x + 9 * marker_scale, y + 13 * marker_scale,
                        f"⚠ +{atrasos[e]:.0f} min", fontsize=7.8 * marker_scale,
                        color=style.INK, zorder=7, family=FONTE_SIMBOLOS,
                        path_effects=HALO_FINO)

    ax.scatter([dx], [dy], s=260 * marker_scale, marker="s", c=style.INK,
               edgecolors="white", linewidths=2, zorder=8)
    ax.text(dx, dy, "✚", ha="center", va="center", color="white",
            fontsize=10 * marker_scale, zorder=9, family=FONTE_SIMBOLOS)
    ax.text(dx + 12 * marker_scale, dy + 22 * marker_scale, "Central (CAF)",
            fontsize=8.5 * marker_scale, color=style.INK, weight="bold",
            zorder=9, path_effects=HALO)


def plot_route_map(
    plan: RoutePlan,
    path: str | Path | None = None,
    title: str | None = None,
    subtitle: str | None = None,
    basemap: Basemap | None | bool = True,
) -> plt.Figure:
    """Figura 16:9 com mapa + painel de legenda/KPIs."""
    style.apply_style()
    if basemap is True:
        basemap = build_basemap(*_coords(plan))
    elif basemap is False:
        basemap = None

    fig = plt.figure(figsize=(16, 9))
    ax = fig.add_axes((0.01, 0.03, 0.60, 0.86))
    draw_routes_on_ax(ax, plan, basemap)
    if basemap is not None:
        ax.text(0.995, 0.005, ATTRIBUTION, transform=ax.transAxes, ha="right", va="bottom",
                fontsize=7, color=style.MUTED)

    k = plan.kpis
    fig.text(0.012, 0.955, title or f"Rotas otimizadas — {plan.method}",
             fontsize=19, weight="bold", color=style.INK)
    fig.text(0.012, 0.915, subtitle or (
        f"{plan.scenario.name} · {k.deliveries} entregas · {k.vehicles_used} veículos · "
        f"{k.total_km:.1f} km · {k.on_time_pct:.0f}% no prazo · {k.violations} violações"),
        fontsize=11.5, color=style.INK_2)

    painel = fig.add_axes((0.635, 0.03, 0.355, 0.86))
    painel.axis("off")
    y = 0.98
    painel.text(0, y, "Veículos", fontsize=13, weight="bold", color=style.INK,
                transform=painel.transAxes, va="top")
    y -= 0.055
    for i, r in enumerate(plan.routes):
        cor = style.vehicle_color(i)
        painel.add_line(Line2D([0.0, 0.06], [y - 0.012, y - 0.012], color=cor, linewidth=4,
                               transform=painel.transAxes, solid_capstyle="round"))
        painel.text(0.085, y, f"{r.vehicle_id} · {r.vehicle_name}", fontsize=10.5,
                    weight="bold", color=style.INK, transform=painel.transAxes, va="top")
        if r.used:
            linha2 = (f"{len(r.stops)} entregas · {r.distance_km:.1f}/{r.range_km:.0f} km · "
                      f"{r.load_kg:.0f}/{r.capacity_kg:.0f} kg · volta {r.return_time}")
        else:
            linha2 = "não sai neste plano"
        painel.text(0.085, y - 0.033, linha2, fontsize=9.3, color=style.INK_2,
                    transform=painel.transAxes, va="top")
        if r.violations:
            painel.text(0.085, y - 0.062, "⚠ viola: " + ", ".join(r.violations), fontsize=9,
                        color=style.INK, transform=painel.transAxes, va="top",
                        family=FONTE_SIMBOLOS)
            y -= 0.03
        y -= 0.085

    y -= 0.01
    painel.text(0, y, "Prioridade (forma)", fontsize=13, weight="bold",
                color=style.INK, transform=painel.transAxes, va="top")
    y -= 0.06
    for rotulo, mk in style.PRIORITY_MARKER.items():
        painel.scatter([0.03], [y - 0.008], s=80, marker=mk, c=style.INK_2,
                       edgecolors="white", transform=painel.transAxes)
        txt = {"CRÍTICA": "crítica — prazo 2 h", "ALTA": "alta — prazo 4 h",
               "NORMAL": "normal — até o fim da janela"}[rotulo]
        painel.text(0.085, y, txt, fontsize=10, color=style.INK_2,
                    transform=painel.transAxes, va="top")
        y -= 0.045
    y -= 0.01
    for simb, txt in (("❄", "cadeia fria (2–8 °C) — só veículo refrigerado"),
                      ("℞", "controlado (Portaria 344/98) — só veículo com cofre"),
                      ("⚠", "entrega fora do prazo (minutos de atraso)"),
                      ("nº", "ordem de visita dentro da rota")):
        painel.text(0.0, y, simb, fontsize=10.5, color=style.INK, transform=painel.transAxes,
                    va="top", family=FONTE_SIMBOLOS)
        painel.text(0.085, y, txt, fontsize=10, color=style.INK_2, transform=painel.transAxes,
                    va="top")
        y -= 0.045

    if path is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=120, bbox_inches=None)
    return fig


def plot_vehicle_facets(plan: RoutePlan, path: str | Path | None = None,
                        basemap: Basemap | None | bool = True) -> plt.Figure:
    """Um pequeno mapa por veículo (small multiples) — rotas sem sobreposição."""
    style.apply_style()
    if basemap is True:
        basemap = build_basemap(*_coords(plan))
    elif basemap is False:
        basemap = None
    usados = [r for r in plan.routes if r.used]
    n = len(usados)
    cols = 3
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(16, 5.6 * rows))
    axes = list(axes.flat) if hasattr(axes, "flat") else [axes]
    indice = {r.vehicle_id: i for i, r in enumerate(plan.routes)}
    for ax, r in zip(axes, usados):
        draw_routes_on_ax(ax, plan, basemap, only_vehicle=r.vehicle_id, marker_scale=0.9)
        ax.set_title(f"{r.vehicle_id} · {r.vehicle_name}\n{len(r.stops)} entregas · "
                     f"{r.distance_km:.1f} km · {r.load_kg:.0f} kg · volta {r.return_time}",
                     fontsize=11, loc="left", color=style.INK)
        ax.plot([], [], color=style.vehicle_color(indice[r.vehicle_id]), linewidth=4)
    for ax in axes[n:]:
        ax.axis("off")
    fig.suptitle(f"Rota de cada veículo — {plan.method}", x=0.01, ha="left",
                 fontsize=16, weight="bold")
    fig.tight_layout()
    if path is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=110)
    return fig
