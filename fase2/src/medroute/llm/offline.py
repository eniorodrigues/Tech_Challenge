"""
Modo offline: os mesmos produtos da LLM gerados por *templates*.

Serve para três coisas:

1. o sistema funciona sem chave, sem internet ou com a cota gratuita
   esgotada (degradação graciosa — o painel avisa que o texto é offline);
2. linha de base para avaliar a LLM: o que ela acrescenta em relação a um
   template determinístico (fluidez, priorização, linguagem);
3. testes automatizados reprodutíveis.

O formato espelha o esqueleto pedido nos prompts.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..domain import CONTROLADO, REFRIGERADO
from ..plan import RoutePlan, RouteView

AVISO = "> _Gerado em modo offline (template determinístico, sem LLM)._"


def _cuidados(req: list[str]) -> str:
    partes = []
    if REFRIGERADO in req:
        partes.append("manter 2–8 °C na caixa térmica e registrar a temperatura na entrega")
    if CONTROLADO in req:
        partes.append("medicamento controlado: conferir lacre e colher assinatura")
    return "; ".join(partes) or "conferir itens com o recebedor"


def driver_instructions(plan: RoutePlan, route: RouteView) -> str:
    r = route
    if not r.used:
        return f"## Rota {r.vehicle_id} — {r.vehicle_name}\n\nVeículo sem entregas neste plano.\n\n{AVISO}"
    reqs = {q for s in r.stops for q in s.requirements}
    linhas = [
        f"## Rota {r.vehicle_id} — {r.vehicle_name}",
        f"**Resumo:** saída às {r.departure} da Central, {len(r.stops)} entregas, "
        f"{r.distance_km:.1f} km, retorno previsto às {r.return_time}, carga total {r.load_kg:.1f} kg.",
        "",
        "### Antes de sair",
        "- Conferir a carga separada por parada, na ordem de entrega abaixo.",
        "- Conferir documentação de cada pedido e o celular carregado.",
    ]
    if REFRIGERADO in reqs:
        linhas.append("- Cadeia fria: caixa térmica fechada, termômetro funcionando e faixa 2–8 °C registrada na saída.")
    if CONTROLADO in reqs:
        linhas.append("- Controlados: conferir lacres e guias; entregar somente mediante assinatura.")
    linhas += ["", "### Paradas (na ordem)"]
    for s in r.stops:
        linhas.append(f"**{s.seq}. {s.arrival} — {s.name}** ({s.neighborhood}) · prioridade "
                      f"{s.priority} · {s.demand_kg:.1f} kg")
        linhas.append(f"  - Itens: {s.items}")
        extra = f" · aguardar abertura até {s.start}" if s.wait_min > 0.5 else ""
        linhas.append(f"  - Janela {s.window} · prazo {s.deadline or 'fim do turno'} · "
                      f"{_cuidados(s.requirements)}{extra}")
    alertas = []
    for s in r.stops:
        if s.priority == "CRÍTICA":
            alertas.append(f"- {s.name}: entrega CRÍTICA, prazo {s.deadline} (chegada prevista {s.arrival}).")
        if s.lateness_min > 0.5:
            alertas.append(f"- {s.name}: atraso previsto de {s.lateness_min:.0f} min — avisar a Central ao sair da parada anterior.")
    if r.range_pct >= 90:
        alertas.append(f"- Autonomia: {r.distance_km:.1f} de {r.range_km:.0f} km — não fazer desvios.")
    linhas += ["", "### Atenção"] + (alertas or ["- Sem alertas especiais para esta rota."])
    linhas += [
        "", "### Em caso de imprevisto",
        "- Avisar a Central imediatamente informando a parada e o novo horário estimado.",
        "- Entregas críticas têm preferência sobre as demais.",
        "- Nunca deixar itens de cadeia fria fora da refrigeração.",
        "", AVISO,
    ]
    return "\n".join(linhas)


def daily_report(plan: RoutePlan, baseline: RoutePlan | None) -> str:
    k = plan.kpis
    linhas = [f"# Relatório diário de rotas — {plan.scenario.date}", "", "## Resumo executivo"]
    if baseline is not None:
        e = plan.compare(baseline)
        b = baseline.kpis
        linhas.append(
            f"O plano do MedRoute atende {k.deliveries} entregas com {k.total_km:.1f} km, "
            f"{e['km_economizados']:.1f} km ({e['km_economizados_pct']:.0f}%) a menos que o processo atual. "
            f"O custo cai R$ {e['reais_economizados']:.2f} e {k.on_time_pct:.1f}% das entregas ficam no prazo "
            f"(processo atual: {b.on_time_pct:.1f}%). "
            f"Ponto de atenção: {k.critical_late} entrega(s) crítica(s) com atraso previsto.")
        linhas += ["", "## Indicadores", "| Indicador | MedRoute | Processo atual | Diferença |",
                   "|---|---|---|---|",
                   f"| km total | {k.total_km:.1f} | {b.total_km:.1f} | −{e['km_economizados']:.1f} km |",
                   f"| custo total (R$) | {k.cost_total_brl:.2f} | {b.cost_total_brl:.2f} | −{e['reais_economizados']:.2f} |",
                   f"| horas de rota | {k.route_hours:.2f} | {b.route_hours:.2f} | −{e['horas_economizadas']:.2f} h |",
                   f"| CO2 (kg) | {k.co2_kg:.1f} | {b.co2_kg:.1f} | −{e['co2_evitado_kg']:.1f} |",
                   f"| entregas no prazo | {k.on_time_pct:.1f}% | {b.on_time_pct:.1f}% | {e['pontos_sla']:+.1f} p.p. |",
                   f"| críticas no prazo | {k.on_time_by_priority.get('CRÍTICA', 100):.1f}% | "
                   f"{b.on_time_by_priority.get('CRÍTICA', 100):.1f}% | — |",
                   f"| violações de restrição | {k.violations} | {b.violations} | {k.violations - b.violations:+d} |"]
    else:
        linhas.append(f"{k.deliveries} entregas, {k.total_km:.1f} km, R$ {k.cost_total_brl:.2f}, "
                      f"{k.on_time_pct:.1f}% no prazo.")
    linhas += ["", "## Pontos de atenção"]
    atrasos = [(r, s) for r in plan.routes for s in r.stops if s.lateness_min > 0.5]
    for r, s in atrasos:
        linhas.append(f"- {s.name} ({r.vehicle_id}): {s.lateness_min:.0f} min além do prazo {s.deadline}.")
    for r in plan.routes:
        if r.range_pct >= 90:
            linhas.append(f"- {r.vehicle_id} usa {r.range_pct:.0f}% da autonomia.")
    if len(linhas) and linhas[-1] == "## Pontos de atenção":
        linhas.append("- Nenhum ponto crítico.")
    linhas += ["", "## Uso da frota"]
    for r in plan.routes:
        if r.used:
            linhas.append(f"- {r.vehicle_id} {r.vehicle_name}: {r.distance_km:.1f} km, carga {r.load_pct:.0f}%, "
                          f"autonomia {r.range_pct:.0f}%, retorno {r.return_time}.")
        else:
            linhas.append(f"- {r.vehicle_id} {r.vehicle_name}: não saiu.")
    linhas += ["", AVISO]
    return "\n".join(linhas)


def weekly_report(semana: dict[str, Any]) -> str:
    t = semana["totais"]
    linhas = [f"# Relatório semanal de distribuição — {semana['periodo']}", "", "## Resumo da semana",
              f"Na semana foram {t['entregas']} entregas. O MedRoute rodou {t['km_ga']:.0f} km contra "
              f"{t['km_atual']:.0f} km do processo atual ({t['km_economia_pct']:.0f}% a menos), economizando "
              f"R$ {t['custo_economia']:.2f} e {t['horas_economia']:.1f} h de rota. "
              f"Entregas no prazo: {t['sla_ga']:.1f}% (atual: {t['sla_atual']:.1f}%).",
              "", "## Economia acumulada", "| Indicador | Processo atual | MedRoute | Economia |",
              "|---|---|---|---|",
              f"| km | {t['km_atual']:.0f} | {t['km_ga']:.0f} | {t['km_atual'] - t['km_ga']:.0f} |",
              f"| custo (R$) | {t['custo_atual']:.2f} | {t['custo_ga']:.2f} | {t['custo_economia']:.2f} |",
              f"| horas de rota | {t['horas_atual']:.1f} | {t['horas_ga']:.1f} | {t['horas_economia']:.1f} |",
              f"| CO2 (kg) | {t['co2_atual']:.1f} | {t['co2_ga']:.1f} | {t['co2_atual'] - t['co2_ga']:.1f} |",
              "", "## Dia a dia"]
    for d in semana["dias"]:
        linhas.append(f"- {d['dia']}: {d['entregas']} entregas, {d['km_ga']:.0f} km "
                      f"(−{d['km_economia_pct']:.0f}%), {d['sla_ga']:.0f}% no prazo.")
    linhas += ["", AVISO]
    return "\n".join(linhas)


def suggestions(dados: dict[str, Any]) -> str:
    linhas = ["## Sugestões de melhoria", ""]
    n = 0
    for sim in dados.get("simulacoes", []):
        n += 1
        a, d = sim["antes"], sim["depois"]
        linhas += [f"### {n}. {sim['descricao']}",
                   f"- **Impacto simulado:** críticas no prazo {a['criticas_no_prazo_pct']:.0f}% → "
                   f"{d['criticas_no_prazo_pct']:.0f}%; km {a['km']:.1f} → {d['km']:.1f}; "
                   f"custo R$ {a['custo_rs']:.2f} → R$ {d['custo_rs']:.2f}.", ""]
    for ach in dados.get("achados", []):
        if ach["severidade"] in ("alta", "media") and n < 5:
            n += 1
            linhas += [f"### {n}. {ach['titulo']}", f"- **Problema observado:** {ach['evidencia']}",
                       "- **Impacto esperado:** a medir.", ""]
    linhas.append(AVISO)
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Perguntas em linguagem natural (regras simples)
# ---------------------------------------------------------------------------
def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def answer(plan: RoutePlan, pergunta: str) -> str:
    q = _norm(pergunta)
    k = plan.kpis

    # Uma entrega específica (por ID ou parte do nome).
    m = re.search(r"\be\d{2}\b", q)
    alvo = plan.find_stop(m.group(0).upper()) if m else None
    if alvo is None:
        for r in plan.routes:
            for s in r.stops:
                nome = _norm(re.sub(r"\s*\(.*?\)", "", s.name))
                if nome and nome in q:
                    alvo = (r, s)
                    break
            if alvo:
                break
    if alvo is not None:
        r, s = alvo
        txt = (f"{s.name} ({s.delivery_id}) é a parada {s.seq} do {r.vehicle_id} ({r.vehicle_name}), "
               f"com chegada prevista às {s.arrival}, prioridade {s.priority}, {s.demand_kg:.1f} kg: {s.items}.")
        if s.lateness_min > 0.5:
            txt += f" Há atraso previsto de {s.lateness_min:.0f} min em relação ao prazo {s.deadline}."
        return txt + f"\n\n{AVISO}"

    m = re.search(r"\bv(\d)\b", q)
    if m:
        try:
            r = plan.route(f"V{m.group(1)}")
        except KeyError:
            return f"Não existe o veículo V{m.group(1)} na frota deste plano.\n\n{AVISO}"
        if not r.used:
            return f"O {r.vehicle_id} não sai neste plano.\n\n{AVISO}"
        seq = ", ".join(f"{s.seq}) {s.name} {s.arrival}" for s in r.stops)
        return (f"O {r.vehicle_id} ({r.vehicle_name}) faz {len(r.stops)} entregas, {r.distance_km:.1f} km, "
                f"carga {r.load_kg:.1f} kg ({r.load_pct:.0f}%), retorno às {r.return_time}. Ordem: {seq}.\n\n{AVISO}")
    if "atras" in q:
        atrasos = [(r, s) for r in plan.routes for s in r.stops if s.lateness_min > 0.5]
        if not atrasos:
            return f"Nenhuma entrega com atraso previsto.\n\n{AVISO}"
        return "Entregas com atraso previsto: " + "; ".join(
            f"{s.name} ({r.vehicle_id}, {s.lateness_min:.0f} min)" for r, s in atrasos) + f".\n\n{AVISO}"
    if "critic" in q:
        crit = [(r, s) for r in plan.routes for s in r.stops if s.priority == "CRÍTICA"]
        return "Entregas críticas: " + "; ".join(
            f"{s.name} — {r.vehicle_id} às {s.start} (prazo {s.deadline})" for r, s in crit) + f".\n\n{AVISO}"
    if "km" in q or "distancia" in q or "quilomet" in q:
        return f"O plano soma {k.total_km:.1f} km com {k.vehicles_used} veículos.\n\n{AVISO}"
    if "custo" in q or "r$" in q or "gasto" in q:
        return (f"Custo estimado do dia: R$ {k.cost_total_brl:.2f} (R$ {k.cost_km_brl:.2f} de veículo + "
                f"R$ {k.cost_driver_brl:.2f} de motoristas).\n\n{AVISO}")
    if "frio" in q or "refriger" in q or "insulina" in q or "vacina" in q:
        frias = [(r, s) for r in plan.routes for s in r.stops if REFRIGERADO in s.requirements]
        return "Entregas de cadeia fria: " + "; ".join(
            f"{s.name} ({r.vehicle_id}, {s.arrival})" for r, s in frias) + f".\n\n{AVISO}"
    if "volta" in q or "retorno" in q or "termina" in q:
        return f"O último veículo retorna às {k.makespan}.\n\n{AVISO}"
    return ("No modo offline eu respondo sobre: uma entrega (ID ou nome), um veículo (V1–V5), atrasos, "
            f"entregas críticas, cadeia fria, km, custo e horário de retorno.\n\n{AVISO}")
