"""
Detecção **determinística** de padrões no plano — a matéria-prima das
sugestões de melhoria.

A LLM não "descobre" problemas olhando para a rota: ela recebe uma lista de
achados já medidos (cada um com a evidência numérica) e os transforma em
recomendações redigidas. Para os achados mais importantes, o sistema roda uma
**simulação "e se"** (re-otimiza o dia com a mudança proposta) e entrega o
efeito medido — a sugestão chega à LLM já validada por dados.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Callable

from ..domain import REFRIGERADO, Scenario
from ..plan import RoutePlan


@dataclass
class Insight:
    codigo: str
    titulo: str
    evidencia: str
    severidade: str                      # alta | media | baixa
    dados: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_plan(plan: RoutePlan, baseline: RoutePlan | None = None) -> list[Insight]:
    achados: list[Insight] = []
    k = plan.kpis
    fim_turno = plan.scenario.clock(plan.scenario.shift_minutes)

    # 1. Atrasos (críticos primeiro)
    for r in plan.routes:
        for s in r.stops:
            if s.lateness_min > 0.5:
                critica = s.priority == "CRÍTICA"
                achados.append(Insight(
                    codigo="ATRASO_CRITICO" if critica else "ATRASO",
                    titulo=f"Entrega {s.priority.lower()} fora do prazo",
                    evidencia=(f"{s.delivery_id} ({s.name}) no {r.vehicle_id}: início previsto "
                               f"{s.start}, prazo {s.deadline} — {s.lateness_min:.0f} min de atraso"),
                    severidade="alta" if critica else "media",
                    dados={"veiculo": r.vehicle_id, "entrega": s.delivery_id,
                           "atraso_min": s.lateness_min, "requisitos": s.requirements},
                ))

    # 2. Gargalo de cadeia fria
    refrig = [r for r in plan.routes if REFRIGERADO in r.features]
    frias = sum(1 for r in plan.routes for s in r.stops if REFRIGERADO in s.requirements)
    criticas_frias = sum(1 for r in plan.routes for s in r.stops
                         if REFRIGERADO in s.requirements and s.priority == "CRÍTICA")
    if refrig:
        achados.append(Insight(
            codigo="CADEIA_FRIA",
            titulo="Concentração de entregas refrigeradas",
            evidencia=(f"{frias} entregas exigem cadeia fria ({criticas_frias} críticas) e só "
                       f"{len(refrig)} veículos podem levá-las: "
                       + ", ".join(f"{r.vehicle_id} ({r.vehicle_name})" for r in refrig)),
            severidade="alta" if criticas_frias > 2 * len(refrig) else "media",
            dados={"entregas_refrigeradas": frias, "criticas_refrigeradas": criticas_frias,
                   "veiculos_refrigerados": [r.vehicle_id for r in refrig]},
        ))

    # 3. Limites da frota (carga e autonomia)
    for r in plan.routes:
        if not r.used:
            achados.append(Insight("VEICULO_OCIOSO", "Veículo sem rota",
                                   f"{r.vehicle_id} ({r.vehicle_name}) não sai neste plano",
                                   "baixa", {"veiculo": r.vehicle_id}))
            continue
        if r.range_pct >= 90:
            achados.append(Insight(
                "AUTONOMIA_NO_LIMITE", "Autonomia quase esgotada",
                f"{r.vehicle_id} roda {r.distance_km:.1f} de {r.range_km:.0f} km "
                f"({r.range_pct:.0f}% da autonomia) — pouca margem para desvios",
                "media", {"veiculo": r.vehicle_id, "uso_autonomia_pct": r.range_pct}))
        if r.load_pct >= 90:
            achados.append(Insight(
                "CARGA_NO_LIMITE", "Capacidade de carga quase esgotada",
                f"{r.vehicle_id} leva {r.load_kg:.0f} de {r.capacity_kg:.0f} kg ({r.load_pct:.0f}%)",
                "media", {"veiculo": r.vehicle_id, "ocupacao_pct": r.load_pct}))
        elif r.load_pct < 35 and r.vehicle_kind != "moto":
            achados.append(Insight(
                "CARGA_OCIOSA", "Veículo grande com pouca carga",
                f"{r.vehicle_id} sai com {r.load_pct:.0f}% da capacidade",
                "baixa", {"veiculo": r.vehicle_id, "ocupacao_pct": r.load_pct}))

    # 4. Esperas por janela de horário
    espera = sum(s.wait_min for r in plan.routes for s in r.stops)
    if espera >= 20:
        piores = sorted(((s.wait_min, r.vehicle_id, s.name) for r in plan.routes for s in r.stops),
                        reverse=True)[:3]
        achados.append(Insight(
            "ESPERA_JANELA", "Tempo parado esperando janela de recebimento",
            f"{espera:.0f} min de espera somados; maiores: "
            + "; ".join(f"{w:.0f} min em {n} ({v})" for w, v, n in piores),
            "media" if espera >= 60 else "baixa", {"espera_total_min": round(espera)}))

    # 5. Folga de turno
    usados = [r for r in plan.routes if r.used]
    if usados:
        folga_h = sum((plan.scenario.shift_minutes - r.duration_min) for r in usados) / 60
        achados.append(Insight(
            "FOLGA_TURNO", "Folga de jornada na frota",
            f"último retorno às {k.makespan} (turno vai até {fim_turno}); "
            f"{folga_h:.1f} h de jornada livre somando os veículos",
            "baixa", {"folga_horas": round(folga_h, 1), "ultimo_retorno": k.makespan}))

    # 6. Emissões por tipo de veículo
    km_eletrico = sum(r.distance_km for r in plan.routes if r.vehicle_kind == "van_eletrica")
    if k.total_km:
        achados.append(Insight(
            "EMISSOES", "Participação do veículo elétrico",
            f"{km_eletrico:.1f} de {k.total_km:.1f} km ({100 * km_eletrico / k.total_km:.0f}%) "
            f"rodados pela van elétrica; emissão total {k.co2_kg:.1f} kg de CO2",
            "baixa", {"km_eletrico": round(km_eletrico, 1), "co2_kg": k.co2_kg}))

    # 7. Ganho sobre o processo atual
    if baseline is not None:
        eco = plan.compare(baseline)
        achados.append(Insight(
            "GANHO_VS_ATUAL", "Ganho sobre o processo atual",
            f"{eco['km_economizados']:.1f} km ({eco['km_economizados_pct']:.0f}%) e "
            f"R$ {eco['reais_economizados']:.2f} a menos; {eco['horas_economizadas']:.1f} h de "
            f"rota a menos; {eco['atrasos_evitados']} atrasos evitados",
            "baixa", eco))
    return achados


# ---------------------------------------------------------------------------
# Simulações "e se"
# ---------------------------------------------------------------------------
@dataclass
class WhatIf:
    nome: str
    descricao: str
    antes: dict[str, Any]
    depois: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bau_termico_moto2(sc: Scenario) -> Scenario:
    frota = [replace(v, features=v.features | {REFRIGERADO},
                     name=v.name + " + baú térmico") if v.id == "V5" else v
             for v in sc.vehicles]
    return replace(sc, vehicles=frota)


def _sem_van_eletrica(sc: Scenario) -> Scenario:
    return replace(sc, vehicles=[v for v in sc.vehicles if v.id != "V3"])


WHAT_IFS: dict[str, tuple[str, Callable[[Scenario], Scenario]]] = {
    "bau_termico_moto02": ("Instalar baú térmico também na Moto 02 (V5)", _bau_termico_moto2),
    "sem_van_eletrica": ("Operar sem a Van Elétrica 03 (V3) — teste de redução de frota",
                         _sem_van_eletrica),
}


def _resumo(plan: RoutePlan) -> dict[str, Any]:
    k = plan.kpis
    return {"km": k.total_km, "custo_rs": k.cost_total_brl, "no_prazo_pct": k.on_time_pct,
            "criticas_no_prazo_pct": k.on_time_by_priority.get("CRÍTICA", 100.0),
            "atrasos": k.late_count, "violacoes": k.violations, "ultimo_retorno": k.makespan}


def run_what_if(plan: RoutePlan, nome: str, generations: int = 250, seed: int = 42) -> WhatIf:
    """Re-otimiza o mesmo dia com a mudança ``nome`` e compara os KPIs."""
    from ..ga import GAConfig
    from ..ga.engine import solve

    descricao, transforma = WHAT_IFS[nome]
    novo = transforma(plan.scenario)
    problema, res = solve(novo, GAConfig(generations=generations, patience=100, seed=seed))
    plano_novo = RoutePlan.from_evaluation(problema, res.evaluation, f"GA — {descricao}",
                                           res.runtime_s)
    return WhatIf(nome=nome, descricao=descricao, antes=_resumo(plan), depois=_resumo(plano_novo))


def suggested_what_ifs(insights: list[Insight]) -> list[str]:
    """Quais simulações valem a pena, dado o que foi achado."""
    nomes = []
    codigos = {i.codigo for i in insights}
    if "ATRASO_CRITICO" in codigos or any(i.codigo == "CADEIA_FRIA" and i.severidade == "alta"
                                          for i in insights):
        nomes.append("bau_termico_moto02")
    if "CARGA_OCIOSA" in codigos or "FOLGA_TURNO" in codigos:
        nomes.append("sem_van_eletrica")
    return nomes
