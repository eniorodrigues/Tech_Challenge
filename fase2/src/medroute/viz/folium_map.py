"""
Mapa interativo (HTML) com folium/Leaflet.

* uma camada por veículo (liga/desliga no controle de camadas);
* marcador de cada parada com a **ordem de visita** dentro da forma da
  prioridade (◆ crítica, ▲ alta, ● normal) na cor do veículo;
* *tooltip* com o resumo e *popup* com todos os dados da entrega (itens,
  janela, prazo, chegada prevista, carga, requisitos, atraso);
* setas de sentido ao longo da rota, legenda e painel de KPIs fixos.
"""

from __future__ import annotations

import html
from pathlib import Path

import folium
from branca.element import MacroElement, Template
from folium.plugins import PolyLineTextPath

from ..plan import RoutePlan, RouteView, StopView
from . import style

_TEXTO_ESCURO = {"#eda100", "#1baf7a"}   # fundos claros pedem texto escuro


def _forma_svg(prioridade: str, cor: str, numero: str, atrasada: bool, tam: int = 28) -> str:
    texto = style.INK if cor in _TEXTO_ESCURO else "#ffffff"
    anel = (f'<circle cx="{tam/2}" cy="{tam/2}" r="{tam/2-1}" fill="none" '
            f'stroke="{style.STATUS_CRITICAL}" stroke-width="2.5"/>') if atrasada else ""
    m = tam / 2
    if prioridade == "CRÍTICA":
        forma = (f'<polygon points="{m},2 {tam-2},{m} {m},{tam-2} 2,{m}" fill="{cor}" '
                 f'stroke="#fff" stroke-width="2"/>')
    elif prioridade == "ALTA":
        forma = (f'<polygon points="{m},2 {tam-2},{tam-4} 2,{tam-4}" fill="{cor}" '
                 f'stroke="#fff" stroke-width="2"/>')
    else:
        forma = f'<circle cx="{m}" cy="{m}" r="{m-4}" fill="{cor}" stroke="#fff" stroke-width="2"/>'
    dy = 3 if prioridade == "ALTA" else 0
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{tam}" height="{tam}">{anel}{forma}'
            f'<text x="{m}" y="{m+4+dy}" text-anchor="middle" font-size="11" font-weight="700" '
            f'font-family="Segoe UI,Arial,sans-serif" fill="{texto}">{numero}</text></svg>')


def _popup(r: RouteView, s: StopView) -> str:
    req = ", ".join(s.requirements) or "nenhum"
    atraso = (f"<b style='color:{style.STATUS_CRITICAL}'>⚠ {s.lateness_min:.0f} min de atraso</b>"
              if s.lateness_min > 0.5 else "✔ no prazo")
    linhas = [
        ("Entrega", f"{s.delivery_id} — {html.escape(s.name)}"),
        ("Veículo", f"{r.vehicle_id} · {html.escape(r.vehicle_name)} (parada {s.seq})"),
        ("Prioridade", s.priority),
        ("Itens", html.escape(s.items)),
        ("Carga", f"{s.demand_kg:.1f} kg"),
        ("Requisitos", req),
        ("Janela", s.window),
        ("Prazo (SLA)", s.deadline or "—"),
        ("Chegada prevista", f"{s.arrival} (início {s.start})"),
        ("Situação", atraso),
    ]
    corpo = "".join(f"<tr><td style='color:#52514e;padding:2px 8px 2px 0'>{a}</td>"
                    f"<td style='padding:2px 0'>{b}</td></tr>" for a, b in linhas)
    return (f"<div style='font-family:Segoe UI,Arial,sans-serif;font-size:12.5px;min-width:280px'>"
            f"<table>{corpo}</table></div>")


def _legenda(plan: RoutePlan) -> str:
    itens = []
    for i, r in enumerate(plan.routes):
        cor = style.vehicle_color(i)
        resumo = (f"{len(r.stops)} entregas · {r.distance_km:.0f}/{r.range_km:.0f} km · "
                  f"{r.load_kg:.0f}/{r.capacity_kg:.0f} kg · volta {r.return_time}"
                  if r.used else "não sai")
        itens.append(
            f"<div style='margin:3px 0'><span style='display:inline-block;width:22px;height:4px;"
            f"background:{cor};border-radius:2px;vertical-align:middle;margin-right:6px'></span>"
            f"<b>{r.vehicle_id}</b> {html.escape(r.vehicle_name)}<br>"
            f"<span style='color:#52514e;margin-left:28px'>{resumo}</span></div>")
    formas = "".join(
        f"<span style='margin-right:10px'>{_forma_svg(p, '#52514e', '', False, 16)} {t}</span>"
        for p, t in (("CRÍTICA", "crítica"), ("ALTA", "alta"), ("NORMAL", "normal")))
    k = plan.kpis
    return f"""
{{% macro html(this, kwargs) %}}
<div style="position:fixed;bottom:18px;left:12px;z-index:9999;background:rgba(252,252,251,.96);
 border:1px solid rgba(11,11,11,.12);border-radius:10px;padding:10px 12px;max-width:380px;
 font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#0b0b0b;box-shadow:0 2px 8px rgba(0,0,0,.08)">
 <div style="font-weight:600;font-size:13px;margin-bottom:4px">Veículos</div>
 {''.join(itens)}
 <div style="font-weight:600;font-size:13px;margin:8px 0 2px">Prioridade (forma) · número = ordem</div>
 <div>{formas}</div>
 <div style="margin-top:4px;color:#52514e">❄ cadeia fria · ℞ controlado · anel vermelho + ⚠ = atraso</div>
</div>
<div style="position:fixed;top:12px;left:60px;z-index:9999;background:rgba(252,252,251,.96);
 border:1px solid rgba(11,11,11,.12);border-radius:10px;padding:8px 12px;
 font-family:Segoe UI,Arial,sans-serif;font-size:12.5px;color:#0b0b0b;box-shadow:0 2px 8px rgba(0,0,0,.08)">
 <div style="font-weight:600;font-size:14px">{html.escape(plan.method)} — {html.escape(plan.scenario.name)}</div>
 <div style="color:#52514e">{k.deliveries} entregas · {k.vehicles_used} veículos · {k.total_km:.1f} km ·
 R$ {k.cost_total_brl:,.2f} · {k.on_time_pct:.0f}% no prazo (críticas: {k.on_time_by_priority.get('CRÍTICA', 100):.0f}%)
 · {k.violations} violações</div>
</div>
{{% endmacro %}}
"""


def build_route_map(plan: RoutePlan, arrows: bool = True) -> folium.Map:
    sc = plan.scenario
    dep = sc.depot
    mapa = folium.Map(location=(dep.lat, dep.lon), zoom_start=12, tiles=None,
                      control_scale=True)
    folium.TileLayer("openstreetmap", name="OpenStreetMap").add_to(mapa)

    folium.Marker(
        (dep.lat, dep.lon),
        tooltip=f"Central: {dep.name}",
        popup=folium.Popup(f"<b>{html.escape(dep.name)}</b><br>{html.escape(dep.address)}<br>"
                           f"Saída de todos os veículos às {sc.shift_start}", max_width=320),
        icon=folium.DivIcon(
            html=("<div style='width:30px;height:30px;background:#0b0b0b;border:2px solid #fff;"
                  "border-radius:6px;color:#fff;font:700 18px/26px Segoe UI,Arial;text-align:center;"
                  "box-shadow:0 1px 4px rgba(0,0,0,.4)'>✚</div>"),
            icon_size=(30, 30), icon_anchor=(15, 15)),
    ).add_to(mapa)

    for i, r in enumerate(plan.routes):
        if not r.used:
            continue
        cor = style.vehicle_color(i)
        camada = folium.FeatureGroup(name=f"{r.vehicle_id} · {r.vehicle_name}", show=True)
        pontos = [(dep.lat, dep.lon)] + [(s.lat, s.lon) for s in r.stops] + [(dep.lat, dep.lon)]
        folium.PolyLine(pontos, color="#ffffff", weight=8, opacity=0.85).add_to(camada)
        linha = folium.PolyLine(pontos, color=cor, weight=4.5, opacity=0.95,
                                tooltip=f"{r.vehicle_id} — {r.distance_km:.1f} km, {len(r.stops)} entregas")
        linha.add_to(camada)
        if arrows:
            PolyLineTextPath(linha, "      ►      ", repeat=True, offset=5,
                             attributes={"fill": cor, "font-size": "13"}).add_to(camada)
        for s in r.stops:
            atrasada = s.lateness_min > 0.5
            simbolos = ("❄" if "refrigerado" in s.requirements else "") + \
                       ("℞" if "controlado" in s.requirements else "")
            dica = (f"{r.vehicle_id} · parada {s.seq} · {s.name} ({s.priority}) "
                    f"{simbolos} — chega {s.arrival}" + (f" ⚠ +{s.lateness_min:.0f} min" if atrasada else ""))
            folium.Marker(
                (s.lat, s.lon),
                tooltip=dica,
                popup=folium.Popup(_popup(r, s), max_width=360),
                icon=folium.DivIcon(html=_forma_svg(s.priority, cor, str(s.seq), atrasada),
                                    icon_size=(28, 28), icon_anchor=(14, 14)),
            ).add_to(camada)
        camada.add_to(mapa)

    legenda = MacroElement()
    legenda._template = Template(_legenda(plan))
    mapa.get_root().add_child(legenda)
    folium.LayerControl(collapsed=False).add_to(mapa)

    lats = [dep.lat] + [d.lat for d in sc.deliveries]
    lons = [dep.lon] + [d.lon for d in sc.deliveries]
    mapa.fit_bounds([(min(lats), min(lons)), (max(lats), max(lons))], padding=(20, 20))
    return mapa


def save_route_map(plan: RoutePlan, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    build_route_map(plan).save(str(path))
    return path
