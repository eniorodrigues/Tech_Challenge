"""
Entidades do domínio: entregas, veículos, depósito e cenário.

Convenções de unidade usadas no projeto inteiro:

* distância em **km**; carga em **kg**; custo em **R$**;
* tempo em **minutos contados a partir do início do turno** (0 = saída da
  central). ``Scenario.clock`` converte para ``HH:MM`` só na apresentação.

Requisitos e recursos
---------------------
Restrições de compatibilidade carga × veículo são modeladas como conjuntos de
rótulos: uma entrega exige ``requirements`` e um veículo oferece ``features``.
A entrega só pode ir num veículo se ``requirements ⊆ features``. Hoje há dois
rótulos (``REFRIGERADO`` e ``CONTROLADO``), mas o mecanismo aceita qualquer
outro sem mudar o algoritmo.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any

# Rótulos de requisito/recurso -------------------------------------------------
REFRIGERADO = "refrigerado"   # cadeia fria 2–8 °C (insulina, vacinas, trombolíticos)
CONTROLADO = "controlado"     # Portaria SVS/MS 344/98: exige cofre/lacre e registro


class Priority(IntEnum):
    """Prioridade clínica da entrega (quanto maior, mais urgente)."""

    NORMAL = 1     # insumos regulares (luvas, seringas, soro, EPIs)
    HIGH = 2       # medicamentos de uso contínuo, dietas, curativos especiais
    CRITICAL = 3   # medicamentos críticos (antibióticos de reserva, insulina, trombolíticos)

    @property
    def label(self) -> str:
        return {3: "CRÍTICA", 2: "ALTA", 1: "NORMAL"}[int(self)]

    @classmethod
    def parse(cls, valor: Any) -> "Priority":
        """Aceita o inteiro, o nome em inglês ou o rótulo em português."""
        if isinstance(valor, Priority):
            return valor
        if isinstance(valor, int):
            return cls(valor)
        texto = str(valor).strip().upper()
        mapa = {"CRÍTICA": 3, "CRITICA": 3, "CRITICAL": 3, "ALTA": 2, "HIGH": 2,
                "NORMAL": 1}
        if texto in mapa:
            return cls(mapa[texto])
        return cls(int(texto))


@dataclass(frozen=True)
class PriorityPolicy:
    """Como cada prioridade pesa na função fitness.

    ``weights``: multiplicador do tempo de chegada e do atraso. Uma entrega
    crítica atrasada 10 min custa 10x mais que uma normal atrasada 10 min.

    ``sla_min``: prazo máximo (minutos após a saída) para entregar. ``None``
    significa "até o fim do turno".
    """

    weights: dict[int, float] = field(
        default_factory=lambda: {3: 10.0, 2: 3.0, 1: 1.0}
    )
    sla_min: dict[int, float | None] = field(
        default_factory=lambda: {3: 120.0, 2: 240.0, 1: None}
    )

    def weight(self, p: Priority) -> float:
        return float(self.weights[int(p)])

    def sla(self, p: Priority) -> float | None:
        return self.sla_min[int(p)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights": {str(k): v for k, v in self.weights.items()},
            "sla_min": {str(k): v for k, v in self.sla_min.items()},
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "PriorityPolicy":
        if not d:
            return cls()
        return cls(
            weights={int(k): float(v) for k, v in d["weights"].items()},
            sla_min={int(k): (None if v is None else float(v))
                     for k, v in d["sla_min"].items()},
        )


@dataclass(frozen=True)
class Depot:
    """Ponto de saída e retorno de todos os veículos."""

    name: str
    lat: float
    lon: float
    address: str = ""


@dataclass(frozen=True)
class Delivery:
    """Um pedido a ser entregue numa unidade ou num domicílio."""

    id: str
    name: str
    kind: str                       # UBS, UPA, AME, Hospital Dia, CAPS, Domiciliar...
    lat: float
    lon: float
    priority: Priority
    demand_kg: float
    requirements: frozenset[str] = frozenset()
    service_min: float = 10.0       # descarga + conferência + assinatura
    window: tuple[float, float] = (0.0, 480.0)  # janela de recebimento (min do turno)
    items: str = ""
    neighborhood: str = ""

    @property
    def refrigerated(self) -> bool:
        return REFRIGERADO in self.requirements

    @property
    def controlled(self) -> bool:
        return CONTROLADO in self.requirements

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["priority"] = self.priority.label
        d["requirements"] = sorted(self.requirements)
        d["window"] = list(self.window)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Delivery":
        return cls(
            id=str(d["id"]),
            name=str(d["name"]),
            kind=str(d.get("kind", "")),
            lat=float(d["lat"]),
            lon=float(d["lon"]),
            priority=Priority.parse(d["priority"]),
            demand_kg=float(d["demand_kg"]),
            requirements=frozenset(d.get("requirements", ())),
            service_min=float(d.get("service_min", 10.0)),
            window=(float(d.get("window", (0, 480))[0]), float(d.get("window", (0, 480))[1])),
            items=str(d.get("items", "")),
            neighborhood=str(d.get("neighborhood", "")),
        )


@dataclass(frozen=True)
class Vehicle:
    """Um veículo da frota (frota heterogênea)."""

    id: str
    name: str
    kind: str                       # van_refrigerada, van, van_eletrica, moto
    capacity_kg: float
    range_km: float                 # autonomia útil, já com margem de segurança
    speed_kmh: float                # velocidade média urbana
    cost_per_km: float              # R$/km (combustível/energia + desgaste)
    features: frozenset[str] = frozenset()
    co2_kg_per_km: float = 0.0
    max_shift_min: float | None = None   # None = usa o turno do cenário

    def can_carry(self, delivery: Delivery) -> bool:
        return delivery.requirements <= self.features

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["features"] = sorted(self.features)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Vehicle":
        return cls(
            id=str(d["id"]),
            name=str(d["name"]),
            kind=str(d.get("kind", "")),
            capacity_kg=float(d["capacity_kg"]),
            range_km=float(d["range_km"]),
            speed_kmh=float(d["speed_kmh"]),
            cost_per_km=float(d.get("cost_per_km", 1.0)),
            features=frozenset(d.get("features", ())),
            co2_kg_per_km=float(d.get("co2_kg_per_km", 0.0)),
            max_shift_min=(None if d.get("max_shift_min") is None
                           else float(d["max_shift_min"])),
        )


@dataclass
class Scenario:
    """Uma instância completa do problema (um dia de operação)."""

    name: str
    depot: Depot
    deliveries: list[Delivery]
    vehicles: list[Vehicle]
    date: str = ""
    shift_start: str = "07:00"
    shift_minutes: float = 480.0
    circuity: float = 1.35          # fator de tortuosidade: km de rua / km em linha reta
    policy: PriorityPolicy = field(default_factory=PriorityPolicy)
    description: str = ""

    # ------------------------------------------------------------ utilidades
    def clock(self, minutes: float) -> str:
        """Converte minutos do turno em ``HH:MM`` (relógio de parede)."""
        h0, m0 = (int(x) for x in self.shift_start.split(":"))
        total = h0 * 60 + m0 + int(round(minutes))
        return f"{(total // 60) % 24:02d}:{total % 60:02d}"

    def delivery_by_id(self, delivery_id: str) -> Delivery:
        for d in self.deliveries:
            if d.id == delivery_id:
                return d
        raise KeyError(delivery_id)

    def vehicle_by_id(self, vehicle_id: str) -> Vehicle:
        for v in self.vehicles:
            if v.id == vehicle_id:
                return v
        raise KeyError(vehicle_id)

    @property
    def total_demand_kg(self) -> float:
        return sum(d.demand_kg for d in self.deliveries)

    @property
    def total_capacity_kg(self) -> float:
        return sum(v.capacity_kg for v in self.vehicles)

    def validate(self) -> list[str]:
        """Problemas estruturais que tornam a instância impossível."""
        problemas: list[str] = []
        ids = [d.id for d in self.deliveries]
        if len(ids) != len(set(ids)):
            problemas.append("IDs de entrega duplicados")
        if not self.vehicles:
            problemas.append("Nenhum veículo na frota")
        for d in self.deliveries:
            if not any(v.can_carry(d) for v in self.vehicles):
                problemas.append(
                    f"{d.id} ({d.name}) exige {sorted(d.requirements)} e nenhum "
                    "veículo oferece esses recursos"
                )
            if d.window[0] > d.window[1]:
                problemas.append(f"{d.id}: janela de horário invertida")
        if self.total_demand_kg > self.total_capacity_kg:
            problemas.append(
                f"Demanda total ({self.total_demand_kg:.0f} kg) maior que a "
                f"capacidade da frota ({self.total_capacity_kg:.0f} kg)"
            )
        return problemas

    # ----------------------------------------------------------- serialização
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "date": self.date,
            "description": self.description,
            "shift_start": self.shift_start,
            "shift_minutes": self.shift_minutes,
            "circuity": self.circuity,
            "policy": self.policy.to_dict(),
            "depot": asdict(self.depot),
            "vehicles": [v.to_dict() for v in self.vehicles],
            "deliveries": [d.to_dict() for d in self.deliveries],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Scenario":
        return cls(
            name=d["name"],
            date=d.get("date", ""),
            description=d.get("description", ""),
            shift_start=d.get("shift_start", "07:00"),
            shift_minutes=float(d.get("shift_minutes", 480.0)),
            circuity=float(d.get("circuity", 1.35)),
            policy=PriorityPolicy.from_dict(d.get("policy")),
            depot=Depot(**d["depot"]),
            vehicles=[Vehicle.from_dict(v) for v in d["vehicles"]],
            deliveries=[Delivery.from_dict(x) for x in d["deliveries"]],
        )

    def to_json(self, path: str | Path | None = None) -> str:
        texto = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        if path is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(texto, encoding="utf-8")
        return texto

    @classmethod
    def from_json(cls, path_or_text: str | Path) -> "Scenario":
        p = Path(path_or_text)
        if len(str(path_or_text)) < 260 and p.exists():
            texto = p.read_text(encoding="utf-8")
        else:
            texto = str(path_or_text)
        return cls.from_dict(json.loads(texto))
