"""
Plano de rotas pronto para consumo: o que o mapa, a API, o painel e a LLM usam.

:class:`RoutePlan` junta o cenário, a avaliação detalhada e os **KPIs de
negócio** (km, custo em R$, horas de motorista, CO₂, cumprimento de SLA,
ocupação da frota) num objeto serializável em JSON. Toda conta é feita aqui,
em Python — a LLM recebe os números prontos e só os redige (evita
"alucinação aritmética").
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .domain import Priority, Scenario
from .problem import Evaluation, Problem

# Custo da hora de motorista (salário + encargos ≈ R$ 6.400/mês ÷ 160 h).
CUSTO_HORA_MOTORISTA = 40.0


@dataclass
class StopView:
    seq: int
    delivery_id: str
    name: str
    kind: str
    neighborhood: str
    lat: float
    lon: float
    priority: str
    demand_kg: float
    requirements: list[str]
    items: str
    window: str
    arrival: str
    start: str
    departure: str
    wait_min: float
    deadline: str | None
    lateness_min: float
    leg_km: float
    load_after_kg: float
    on_time: bool


@dataclass
class RouteView:
    vehicle_id: str
    vehicle_name: str
    vehicle_kind: str
    features: list[str]
    capacity_kg: float
    range_km: float
    load_kg: float
    distance_km: float
    duration_min: float
    departure: str
    return_time: str
    drive_min: float
    service_min: float
    wait_min: float
    cost_brl: float
    co2_kg: float
    load_pct: float
    range_pct: float
    violations: dict[str, float]
    stops: list[StopView] = field(default_factory=list)

    @property
    def used(self) -> bool:
        return bool(self.stops)


@dataclass
class KPIs:
    deliveries: int
    vehicles_used: int
    vehicles_total: int
    total_km: float
    cost_km_brl: float
    cost_driver_brl: float
    cost_total_brl: float
    co2_kg: float
    drive_hours: float
    route_hours: float
    makespan: str
    on_time_pct: float
    on_time_by_priority: dict[str, float]
    late_count: int
    critical_late: int
    max_lateness_min: float
    avg_critical_arrival: str
    fleet_load_pct: float
    violations: int
    feasible: bool
    fitness: float


@dataclass
class RoutePlan:
    """Plano completo de um dia (uma solução avaliada)."""

    scenario: Scenario
    method: str
    routes: list[RouteView]
    kpis: KPIs
    runtime_s: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    # -------------------------------------------------------------- construção
    @classmethod
    def from_evaluation(cls, problem: Problem, evaluation: Evaluation, method: str,
                        runtime_s: float = 0.0, meta: dict | None = None) -> "RoutePlan":
        sc = problem.scenario
        relogio = sc.clock
        rotas: list[RouteView] = []
        for rr in evaluation.routes:
            v = sc.vehicles[rr.vehicle_index]
            paradas = []
            for seq, s in enumerate(rr.stop_results, start=1):
                d = sc.deliveries[s.index - 1]
                prazo = None if s.deadline == float("inf") else relogio(s.deadline)
                paradas.append(StopView(
                    seq=seq, delivery_id=d.id, name=d.name, kind=d.kind,
                    neighborhood=d.neighborhood, lat=d.lat, lon=d.lon,
                    priority=d.priority.label, demand_kg=round(d.demand_kg, 1),
                    requirements=sorted(d.requirements), items=d.items,
                    window=f"{relogio(d.window[0])}–{relogio(d.window[1])}",
                    arrival=relogio(s.arrival), start=relogio(s.start),
                    departure=relogio(s.departure), wait_min=round(s.wait, 1),
                    deadline=prazo, lateness_min=round(s.lateness, 1),
                    leg_km=round(s.leg_km, 2), load_after_kg=round(s.load_after, 1),
                    on_time=s.lateness <= 1e-6,
                ))
            horas = rr.duration_min / 60.0
            custo = rr.distance_km * v.cost_per_km + (horas * CUSTO_HORA_MOTORISTA if rr.stops else 0)
            rotas.append(RouteView(
                vehicle_id=v.id, vehicle_name=v.name, vehicle_kind=v.kind,
                features=sorted(v.features), capacity_kg=v.capacity_kg, range_km=v.range_km,
                load_kg=round(rr.load_kg, 1), distance_km=round(rr.distance_km, 2),
                duration_min=round(rr.duration_min, 1),
                departure=relogio(0), return_time=relogio(rr.duration_min) if rr.stops else "—",
                drive_min=round(rr.travel_min, 1), service_min=round(rr.service_min, 1),
                wait_min=round(rr.wait_min, 1), cost_brl=round(custo, 2),
                co2_kg=round(rr.distance_km * v.co2_kg_per_km, 2),
                load_pct=round(100 * rr.load_kg / v.capacity_kg, 1) if v.capacity_kg else 0.0,
                range_pct=round(100 * rr.distance_km / v.range_km, 1) if v.range_km else 0.0,
                violations={k: round(x, 2) for k, x in rr.violations.items()},
                stops=paradas,
            ))
        return cls(scenario=sc, method=method, routes=rotas,
                   kpis=cls._kpis(sc, evaluation, rotas), runtime_s=runtime_s,
                   meta=dict(meta or {}))

    @staticmethod
    def _kpis(sc: Scenario, ev: Evaluation, rotas: list[RouteView]) -> KPIs:
        paradas = [s for r in rotas for s in r.stops]
        usados = [r for r in rotas if r.used]
        por_prioridade: dict[str, float] = {}
        for p in (Priority.CRITICAL, Priority.HIGH, Priority.NORMAL):
            grupo = [s for s in paradas if s.priority == p.label]
            if grupo:
                por_prioridade[p.label] = round(100 * sum(s.on_time for s in grupo) / len(grupo), 1)
        criticas = [r_s for r in rotas for r_s in r.stops if r_s.priority == Priority.CRITICAL.label]

        def _min(hhmm: str) -> int:
            h, m = hhmm.split(":")
            return int(h) * 60 + int(m)

        media_critica = "—"
        if criticas:
            m = sum(_min(s.start) for s in criticas) / len(criticas)
            media_critica = f"{int(m // 60):02d}:{int(m % 60):02d}"
        fim = max((r.duration_min for r in usados), default=0.0)
        custo_km = sum(r.distance_km * sc.vehicle_by_id(r.vehicle_id).cost_per_km for r in rotas)
        custo_mot = sum(r.duration_min / 60 * CUSTO_HORA_MOTORISTA for r in usados)
        cap_usada = sum(r.capacity_kg for r in usados) or 1.0
        return KPIs(
            deliveries=len(paradas),
            vehicles_used=len(usados),
            vehicles_total=len(rotas),
            total_km=round(sum(r.distance_km for r in rotas), 1),
            cost_km_brl=round(custo_km, 2),
            cost_driver_brl=round(custo_mot, 2),
            cost_total_brl=round(custo_km + custo_mot, 2),
            co2_kg=round(sum(r.co2_kg for r in rotas), 1),
            drive_hours=round(sum(r.drive_min for r in rotas) / 60, 2),
            route_hours=round(sum(r.duration_min for r in usados) / 60, 2),
            makespan=sc.clock(fim),
            on_time_pct=round(100 * sum(s.on_time for s in paradas) / max(1, len(paradas)), 1),
            on_time_by_priority=por_prioridade,
            late_count=sum(not s.on_time for s in paradas),
            critical_late=sum(not s.on_time for s in criticas),
            max_lateness_min=round(max((s.lateness_min for s in paradas), default=0.0), 1),
            avg_critical_arrival=media_critica,
            fleet_load_pct=round(100 * sum(r.load_kg for r in usados) / cap_usada, 1),
            violations=ev.n_violations,
            feasible=ev.feasible,
            fitness=round(ev.fitness, 2),
        )

    # ----------------------------------------------------------------- consulta
    def route(self, vehicle_id: str) -> RouteView:
        for r in self.routes:
            if r.vehicle_id == vehicle_id:
                return r
        raise KeyError(vehicle_id)

    def find_stop(self, termo: str) -> tuple[RouteView, StopView] | None:
        """Procura uma parada pelo ID (``E07``) ou por parte do nome."""
        t = termo.strip().lower()
        for r in self.routes:
            for s in r.stops:
                if s.delivery_id.lower() == t or t in s.name.lower():
                    return r, s
        return None

    def compare(self, referencia: "RoutePlan") -> dict[str, float]:
        """Economia deste plano em relação a outro (positivo = este é melhor)."""
        a, b = self.kpis, referencia.kpis
        return {
            "km_economizados": round(b.total_km - a.total_km, 1),
            "km_economizados_pct": round(100 * (b.total_km - a.total_km) / b.total_km, 1) if b.total_km else 0.0,
            "reais_economizados": round(b.cost_total_brl - a.cost_total_brl, 2),
            "reais_economizados_pct": round(100 * (b.cost_total_brl - a.cost_total_brl) / b.cost_total_brl, 1) if b.cost_total_brl else 0.0,
            "horas_economizadas": round(b.route_hours - a.route_hours, 2),
            "co2_evitado_kg": round(b.co2_kg - a.co2_kg, 1),
            "pontos_sla": round(a.on_time_pct - b.on_time_pct, 1),
            "atrasos_evitados": b.late_count - a.late_count,
            "violacoes_evitadas": b.violations - a.violations,
        }

    # -------------------------------------------------------------- exportação
    def to_dict(self, include_scenario: bool = False) -> dict[str, Any]:
        d = {
            "method": self.method,
            "scenario_name": self.scenario.name,
            "date": self.scenario.date,
            "shift_start": self.scenario.shift_start,
            "depot": asdict(self.scenario.depot),
            "runtime_s": round(self.runtime_s, 3),
            "kpis": asdict(self.kpis),
            "routes": [asdict(r) for r in self.routes],
            "meta": self.meta,
        }
        if include_scenario:
            d["scenario"] = self.scenario.to_dict()
        return d

    def to_json(self, **kw) -> str:
        return json.dumps(self.to_dict(**kw), ensure_ascii=False, indent=2)

    def schedule_rows(self) -> list[dict[str, Any]]:
        """Tabela "uma linha por parada" (para DataFrame/CSV/painel)."""
        linhas = []
        for r in self.routes:
            for s in r.stops:
                linhas.append({
                    "veiculo": r.vehicle_id, "veiculo_nome": r.vehicle_name, "seq": s.seq,
                    "entrega": s.delivery_id, "destino": s.name, "prioridade": s.priority,
                    "chegada": s.arrival, "inicio": s.start, "prazo": s.deadline or "—",
                    "atraso_min": s.lateness_min, "carga_kg": s.demand_kg,
                    "requisitos": ", ".join(s.requirements) or "—", "itens": s.items,
                })
        return linhas

    def summary_text(self) -> str:
        k = self.kpis
        linhas = [
            f"{self.method} — {self.scenario.name}",
            f"  {k.deliveries} entregas | {k.vehicles_used}/{k.vehicles_total} veículos | "
            f"{k.total_km:.1f} km | R$ {k.cost_total_brl:,.2f} | {k.route_hours:.1f} h de rota | "
            f"CO2 {k.co2_kg:.1f} kg",
            f"  No prazo: {k.on_time_pct:.1f}% {k.on_time_by_priority} | atrasos: {k.late_count} "
            f"(críticos: {k.critical_late}) | violações: {k.violations} | fitness {k.fitness:.1f}",
        ]
        for r in self.routes:
            if not r.used:
                linhas.append(f"  {r.vehicle_id} {r.vehicle_name}: não sai")
                continue
            seq = " → ".join(s.delivery_id for s in r.stops)
            linhas.append(
                f"  {r.vehicle_id} {r.vehicle_name}: {len(r.stops)} paradas, {r.distance_km:.1f}/"
                f"{r.range_km:.0f} km, {r.load_kg:.0f}/{r.capacity_kg:.0f} kg, volta {r.return_time}"
                f"{'  VIOLAÇÕES ' + str(r.violations) if r.violations else ''}\n      {seq}"
            )
        return "\n".join(linhas)
