"""
Montagem do **contexto estruturado** que vai para a LLM.

Princípio: a LLM não calcula nada. Todo número (km, horário, kg, R$, %) é
produzido pelo otimizador e entregue pronto, em JSON compacto com chaves em
português. A LLM só organiza e redige. Isso reduz alucinação e mantém o
texto conferível contra os dados (ver :mod:`medroute.llm.guardrails`).
"""

from __future__ import annotations

import json
from typing import Any

from ..plan import RoutePlan, RouteView


def _parada(s) -> dict[str, Any]:
    d = {
        "ordem": s.seq,
        "id": s.delivery_id,
        "destino": s.name,
        "bairro": s.neighborhood,
        "tipo": s.kind,
        "prioridade": s.priority,
        "chegada": s.arrival,
        "inicio_atendimento": s.start,
        "janela": s.window,
        "prazo": s.deadline or "fim do turno",
        "carga_kg": s.demand_kg,
        "itens": s.items,
    }
    if s.requirements:
        d["requisitos"] = s.requirements
    if s.wait_min > 0.5:
        d["espera_min"] = round(s.wait_min)
    if s.lateness_min > 0.5:
        d["atraso_previsto_min"] = round(s.lateness_min)
    return d


def route_context(r: RouteView) -> dict[str, Any]:
    return {
        "veiculo": r.vehicle_id,
        "nome": r.vehicle_name,
        "tipo": r.vehicle_kind,
        "recursos": r.features or ["nenhum especial"],
        "capacidade_kg": r.capacity_kg,
        "autonomia_km": r.range_km,
        "carga_total_kg": r.load_kg,
        "km_rota": r.distance_km,
        "saida": r.departure,
        "retorno_previsto": r.return_time,
        "ocupacao_carga_pct": r.load_pct,
        "uso_autonomia_pct": r.range_pct,
        "n_entregas": len(r.stops),
        "indices": {
            "paradas_refrigeradas": [s.delivery_id for s in r.stops if "refrigerado" in s.requirements],
            "paradas_controladas": [s.delivery_id for s in r.stops if "controlado" in s.requirements],
            "paradas_criticas": [s.delivery_id for s in r.stops if s.priority == "CRÍTICA"],
        },
        "paradas": [_parada(s) for s in r.stops],
    }


def kpi_context(plan: RoutePlan) -> dict[str, Any]:
    k = plan.kpis
    return {
        "entregas": k.deliveries,
        "veiculos_usados": f"{k.vehicles_used} de {k.vehicles_total}",
        "km_total": k.total_km,
        "custo_total_rs": k.cost_total_brl,
        "custo_km_rs": k.cost_km_brl,
        "custo_motoristas_rs": k.cost_driver_brl,
        "horas_de_rota": k.route_hours,
        "co2_kg": k.co2_kg,
        "ultimo_retorno": k.makespan,
        "no_prazo_pct": k.on_time_pct,
        "no_prazo_por_prioridade_pct": k.on_time_by_priority,
        "entregas_atrasadas": k.late_count,
        "criticas_atrasadas": k.critical_late,
        "maior_atraso_min": k.max_lateness_min,
        "horario_medio_entrega_critica": k.avg_critical_arrival,
        "ocupacao_media_frota_pct": k.fleet_load_pct,
        "violacoes_restricoes": k.violations,
    }


def indices(plan: RoutePlan) -> dict[str, Any]:
    """Listas prontas por requisito/prioridade (pré-cálculo contra erro de contagem).

    Introduzido na v3 do prompt: sem elas a LLM chegou a "deduzir" que um CAPS
    recebia controlados e contou 7 entregas controladas quando eram 6.
    """
    def item(r: RouteView, s) -> dict[str, Any]:
        return {"id": s.delivery_id, "destino": s.name, "veiculo": r.vehicle_id,
                "ordem": s.seq, "chegada": s.arrival}

    paradas = [(r, s) for r in plan.routes for s in r.stops]
    controladas = [item(r, s) for r, s in paradas if "controlado" in s.requirements]
    refrigeradas = [item(r, s) for r, s in paradas if "refrigerado" in s.requirements]
    criticas = [item(r, s) for r, s in paradas if s.priority == "CRÍTICA"]
    atrasadas = [{**item(r, s), "atraso_min": round(s.lateness_min)}
                 for r, s in paradas if s.lateness_min > 0.5]
    return {
        "entregas_controladas": {"total": len(controladas), "lista": controladas},
        "entregas_refrigeradas": {"total": len(refrigeradas), "lista": refrigeradas},
        "entregas_criticas": {"total": len(criticas), "lista": criticas},
        "entregas_com_atraso_previsto": {"total": len(atrasadas), "lista": atrasadas},
    }


def plan_context(plan: RoutePlan, include_stops: bool = True) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "data": plan.scenario.date,
        "turno": f"{plan.scenario.shift_start}–{plan.scenario.clock(plan.scenario.shift_minutes)}",
        "central": plan.scenario.depot.name,
        "metodo": plan.method,
        "indicadores": kpi_context(plan),
        "indices": indices(plan),
    }
    if include_stops:
        ctx["veiculos"] = [route_context(r) for r in plan.routes]
    else:
        ctx["veiculos"] = [
            {k: v for k, v in route_context(r).items() if k != "paradas"} for r in plan.routes
        ]
    return ctx


def comparison_context(plan: RoutePlan, baseline: RoutePlan) -> dict[str, Any]:
    eco = plan.compare(baseline)
    return {
        "medroute": kpi_context(plan),
        "processo_atual": kpi_context(baseline),
        "processo_atual_descricao": baseline.method,
        "economia_medroute_vs_atual": eco,
    }


def to_json(obj: Any) -> str:
    """JSON compacto (sem indentação) — economiza tokens."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
