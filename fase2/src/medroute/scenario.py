"""
Gerador do cenário sintético: um dia de distribuição do hospital universitário.

Os dados são **fictícios e reprodutíveis** (semente fixa). A geografia é a de
São Paulo — os bairros e suas coordenadas aproximadas são reais, para o mapa
fazer sentido — mas as unidades, pacientes, pedidos e quantidades são
inventados. Nenhum dado pessoal real é usado: pacientes domiciliares são
identificados só por um código (``PD-07``) e o ponto é sorteado com um
deslocamento aleatório em torno do centro do bairro.

O que o gerador produz e por quê:

* **Tipos de destino** com perfis diferentes: UBS, UPA, AME, CAPS, Hospital
  Dia e atendimento domiciliar. Cada tipo tem faixa de carga, tempo de
  serviço e janela de recebimento típicos.
* **Prioridade clínica** sorteada por tipo (UPA e domicílio concentram os
  críticos), com itens coerentes com a prioridade.
* **Requisitos de transporte** derivados dos itens: insulina/vacinas exigem
  cadeia fria; morfina/clonazepam exigem veículo com cofre (controlados).
* **Frota heterogênea** de cinco veículos com capacidade, autonomia, custo e
  recursos diferentes.
* A carga total é calibrada para ocupar ``utilizacao_alvo`` da frota, para
  que a capacidade seja de fato uma restrição relevante.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from .domain import (
    CONTROLADO,
    REFRIGERADO,
    Delivery,
    Depot,
    Priority,
    PriorityPolicy,
    Scenario,
    Vehicle,
)

# ---------------------------------------------------------------------------
# Geografia (centros aproximados dos bairros de São Paulo)
# ---------------------------------------------------------------------------
BAIRROS: dict[str, tuple[float, float]] = {
    "Pinheiros": (-23.5662, -46.6936),
    "Vila Madalena": (-23.5546, -46.6907),
    "Butantã": (-23.5717, -46.7084),
    "Lapa": (-23.5226, -46.7029),
    "Perdizes": (-23.5367, -46.6779),
    "Santa Cecília": (-23.5385, -46.6526),
    "Bela Vista": (-23.5614, -46.6474),
    "Liberdade": (-23.5587, -46.6346),
    "Sé": (-23.5503, -46.6340),
    "Mooca": (-23.5599, -46.5975),
    "Tatuapé": (-23.5403, -46.5763),
    "Vila Mariana": (-23.5893, -46.6346),
    "Moema": (-23.6006, -46.6649),
    "Itaim Bibi": (-23.5847, -46.6787),
    "Jardim Paulista": (-23.5697, -46.6588),
    "Ipiranga": (-23.5888, -46.6077),
    "Santana": (-23.5017, -46.6252),
    "Brás": (-23.5433, -46.6167),
    "Barra Funda": (-23.5262, -46.6655),
    "Consolação": (-23.5506, -46.6584),
    "Aclimação": (-23.5716, -46.6311),
    "Saúde": (-23.6178, -46.6385),
    "Campo Belo": (-23.6230, -46.6697),
    "Brooklin": (-23.6148, -46.6939),
    "Morumbi": (-23.6005, -46.7202),
    "Jaguaré": (-23.5487, -46.7470),
    "Vila Leopoldina": (-23.5301, -46.7319),
    "Penha": (-23.5275, -46.5426),
    "Cambuci": (-23.5672, -46.6225),
    "Água Branca": (-23.5227, -46.6879),
    "Higienópolis": (-23.5441, -46.6580),
    "Vila Prudente": (-23.5832, -46.5810),
    "Jabaquara": (-23.6458, -46.6427),
    "Freguesia do Ó": (-23.5009, -46.6966),
    "Casa Verde": (-23.5110, -46.6593),
    "Vila Guilherme": (-23.5104, -46.6058),
    "Vila Sônia": (-23.5970, -46.7378),
    "Campo Limpo": (-23.6331, -46.7602),
    "Santo Amaro": (-23.6526, -46.7086),
    "Pompeia": (-23.5326, -46.6869),
    "Vila Formosa": (-23.5677, -46.5466),
    "Carrão": (-23.5520, -46.5450),
    "Tucuruvi": (-23.4803, -46.6036),
    "Vila Maria": (-23.5130, -46.5830),
    "Rio Pequeno": (-23.5690, -46.7520),
    "Paraíso": (-23.5747, -46.6418),
    "Sumaré": (-23.5480, -46.6770),
    "Cursino": (-23.6202, -46.6175),
}

DEPOSITO = Depot(
    name="Central de Abastecimento Farmacêutico — Hospital Universitário",
    lat=-23.5573,
    lon=-46.6702,
    address="Cerqueira César, São Paulo/SP (localização ilustrativa)",
)

# ---------------------------------------------------------------------------
# Frota padrão (heterogênea)
# ---------------------------------------------------------------------------
FROTA_PADRAO: tuple[Vehicle, ...] = (
    Vehicle(id="V1", name="Van Refrigerada 01", kind="van_refrigerada",
            capacity_kg=450, range_km=140, speed_kmh=22, cost_per_km=3.10,
            features=frozenset({REFRIGERADO, CONTROLADO}), co2_kg_per_km=0.28),
    Vehicle(id="V2", name="Van 02 (cofre)", kind="van",
            capacity_kg=650, range_km=160, speed_kmh=22, cost_per_km=2.40,
            features=frozenset({CONTROLADO}), co2_kg_per_km=0.25),
    Vehicle(id="V3", name="Van Elétrica 03", kind="van_eletrica",
            capacity_kg=550, range_km=70, speed_kmh=22, cost_per_km=0.90,
            features=frozenset(), co2_kg_per_km=0.03),
    Vehicle(id="V4", name="Moto 01 (baú térmico)", kind="moto",
            capacity_kg=25, range_km=60, speed_kmh=28, cost_per_km=0.45,
            features=frozenset({REFRIGERADO}), co2_kg_per_km=0.07),
    Vehicle(id="V5", name="Moto 02", kind="moto",
            capacity_kg=25, range_km=60, speed_kmh=28, cost_per_km=0.45,
            features=frozenset(), co2_kg_per_km=0.07),
)


# ---------------------------------------------------------------------------
# Catálogo de itens: (descrição, requisitos, prioridade)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Item:
    descricao: str
    requisitos: frozenset[str]
    prioridade: Priority
    tipos: tuple[str, ...]  # tipos de destino em que o item faz sentido


_F = frozenset
CATALOGO: tuple[Item, ...] = (
    # ---- CRÍTICOS
    Item("Insulina NPH e regular (cadeia fria)", _F({REFRIGERADO}), Priority.CRITICAL,
         ("UBS", "Domiciliar", "UPA")),
    Item("Alteplase — trombolítico (cadeia fria)", _F({REFRIGERADO}), Priority.CRITICAL,
         ("UPA", "Hospital Dia")),
    Item("Meropenem 1 g — antibiótico de reserva", _F(), Priority.CRITICAL,
         ("UPA", "Hospital Dia")),
    Item("Vacinas e imunobiológicos (cadeia fria)", _F({REFRIGERADO}), Priority.CRITICAL,
         ("UBS",)),
    Item("Heparina sódica e enoxaparina", _F(), Priority.CRITICAL,
         ("UPA", "Hospital Dia", "Domiciliar")),
    Item("Ceftriaxona IV para terapia domiciliar", _F(), Priority.CRITICAL,
         ("Domiciliar",)),
    Item("Naloxona e flumazenil — antídotos", _F(), Priority.CRITICAL,
         ("UPA",)),
    # ---- ALTA
    Item("Morfina e fentanil (controlados — Portaria 344/98)", _F({CONTROLADO}),
         Priority.HIGH, ("UPA", "Hospital Dia", "Domiciliar")),
    Item("Clonazepam e haloperidol (controlados — Portaria 344/98)", _F({CONTROLADO}),
         Priority.HIGH, ("CAPS",)),
    Item("Dieta enteral", _F(), Priority.HIGH, ("Domiciliar", "Hospital Dia")),
    Item("Curativos especiais (hidrocoloide, alginato)", _F(), Priority.HIGH,
         ("Domiciliar", "UBS", "AME")),
    Item("Anti-hipertensivos e hipoglicemiantes de uso contínuo", _F(), Priority.HIGH,
         ("UBS", "AME", "CAPS")),
    Item("Quimioterápicos orais", _F(), Priority.HIGH, ("AME", "Hospital Dia")),
    # ---- NORMAL
    Item("Luvas, seringas e gaze", _F(), Priority.NORMAL,
         ("UBS", "UPA", "AME", "Hospital Dia", "CAPS")),
    Item("Soro fisiológico 0,9% (caixas)", _F(), Priority.NORMAL,
         ("UPA", "Hospital Dia", "UBS")),
    Item("EPIs — máscaras e aventais", _F(), Priority.NORMAL,
         ("UBS", "UPA", "AME", "CAPS", "Hospital Dia")),
    Item("Fraldas geriátricas e material de higiene", _F(), Priority.NORMAL,
         ("Domiciliar",)),
    Item("Kits de coleta laboratorial", _F(), Priority.NORMAL,
         ("UBS", "AME")),
    Item("Saneantes e material de limpeza hospitalar", _F(), Priority.NORMAL,
         ("UPA", "Hospital Dia", "UBS")),
)


@dataclass(frozen=True)
class PerfilTipo:
    """Características típicas de cada tipo de destino."""

    carga_kg: tuple[float, float]
    servico_min: float
    janelas: tuple[tuple[float, float], ...]   # janelas possíveis (min do turno)
    prob_prioridade: tuple[float, float, float]  # P(normal), P(alta), P(crítica)


PERFIS: dict[str, PerfilTipo] = {
    "UBS": PerfilTipo((30, 110), 12, ((60, 300), (0, 480)), (0.55, 0.25, 0.20)),
    "UPA": PerfilTipo((50, 140), 15, ((0, 480),), (0.35, 0.25, 0.40)),
    "AME": PerfilTipo((30, 100), 12, ((0, 360), (60, 300)), (0.55, 0.45, 0.00)),
    "Hospital Dia": PerfilTipo((40, 120), 15, ((0, 480),), (0.40, 0.35, 0.25)),
    "CAPS": PerfilTipo((8, 30), 10, ((60, 420),), (0.30, 0.70, 0.00)),
    "Domiciliar": PerfilTipo((2, 12), 15,
                             ((0, 300), (60, 240), (120, 300), (180, 360), (240, 420)),
                             (0.40, 0.35, 0.25)),
}

# Composição do dia padrão (36 entregas).
COMPOSICAO_PADRAO: dict[str, int] = {
    "UBS": 8, "UPA": 4, "AME": 3, "Hospital Dia": 2, "CAPS": 3, "Domiciliar": 16,
}

DIAS_SEMANA = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta")


def _sortear_prioridade(rng: random.Random, perfil: PerfilTipo) -> Priority:
    p_normal, p_alta, _ = perfil.prob_prioridade
    r = rng.random()
    if r < p_normal:
        return Priority.NORMAL
    if r < p_normal + p_alta:
        return Priority.HIGH
    return Priority.CRITICAL


def _itens_para(rng: random.Random, tipo: str, prioridade: Priority) -> list[Item]:
    """Um item principal da prioridade sorteada + talvez um complemento normal."""
    principais = [i for i in CATALOGO if i.prioridade == prioridade and tipo in i.tipos]
    if not principais:  # tipo sem item dessa prioridade: rebaixa para normal
        principais = [i for i in CATALOGO
                      if i.prioridade == Priority.NORMAL and tipo in i.tipos]
    itens = [rng.choice(principais)]
    if tipo != "Domiciliar" and rng.random() < 0.6:
        extras = [i for i in CATALOGO if i.prioridade == Priority.NORMAL
                  and tipo in i.tipos and i not in itens]
        if extras:
            itens.append(rng.choice(extras))
    return itens


def generate_scenario(
    seed: int = 42,
    composicao: dict[str, int] | None = None,
    utilizacao_alvo: float = 0.68,
    data: str = "2026-10-13",
    nome: str | None = None,
    frota: tuple[Vehicle, ...] = FROTA_PADRAO,
    fator_demanda: float = 1.0,
) -> Scenario:
    """Gera um dia de operação reprodutível.

    Parameters
    ----------
    seed:
        Semente do sorteio (mesma semente → mesmo cenário).
    composicao:
        Quantas entregas de cada tipo. Padrão: :data:`COMPOSICAO_PADRAO`.
    utilizacao_alvo:
        Fração da capacidade total da frota que a demanda deve ocupar.
    fator_demanda:
        Multiplicador aplicado depois da calibração (simula dias mais cheios).
    """
    rng = random.Random(seed)
    composicao = dict(composicao or COMPOSICAO_PADRAO)

    bairros = list(BAIRROS)
    rng.shuffle(bairros)
    bairros_unidades = iter(bairros)          # cada unidade num bairro diferente

    entregas: list[Delivery] = []
    seq = 0
    seq_paciente = 0
    for tipo, quantidade in composicao.items():
        perfil = PERFIS[tipo]
        for _ in range(quantidade):
            seq += 1
            prioridade = _sortear_prioridade(rng, perfil)
            itens = _itens_para(rng, tipo, prioridade)
            prioridade = max(i.prioridade for i in itens)
            requisitos = frozenset().union(*(i.requisitos for i in itens))

            if tipo == "Domiciliar":
                bairro = rng.choice(list(BAIRROS))
                lat0, lon0 = BAIRROS[bairro]
                # ~ ±600 m em torno do centro do bairro: o ponto é fictício.
                lat = lat0 + rng.uniform(-0.0055, 0.0055)
                lon = lon0 + rng.uniform(-0.0060, 0.0060)
                seq_paciente += 1
                nome_destino = f"Paciente PD-{seq_paciente:02d} ({bairro})"
            else:
                try:
                    bairro = next(bairros_unidades)
                except StopIteration:  # mais unidades que bairros: reaproveita
                    bairro = rng.choice(list(BAIRROS))
                lat, lon = BAIRROS[bairro]
                nome_destino = f"{tipo} {bairro}"

            janela = rng.choice(perfil.janelas)
            if prioridade == Priority.CRITICAL:
                # Um crítico não pode ter janela que só abre depois do SLA.
                janela = (0.0, max(janela[1], 300.0))
            elif prioridade == Priority.HIGH and janela[0] > 120:
                # Alta prioridade (SLA de 4 h): a janela precisa abrir com
                # pelo menos 2 h de folga antes do prazo.
                janela = (120.0, max(janela[1], 300.0))

            carga = rng.uniform(*perfil.carga_kg)
            entregas.append(
                Delivery(
                    id=f"E{seq:02d}",
                    name=nome_destino,
                    kind=tipo,
                    lat=round(lat, 6),
                    lon=round(lon, 6),
                    priority=prioridade,
                    demand_kg=carga,
                    requirements=requisitos,
                    service_min=perfil.servico_min,
                    window=(float(janela[0]), float(janela[1])),
                    items=" · ".join(i.descricao for i in itens),
                    neighborhood=bairro,
                )
            )

    # Calibração da carga: a demanda total ocupa `utilizacao_alvo` da frota.
    capacidade = sum(v.capacity_kg for v in frota)
    fator = utilizacao_alvo * capacidade / sum(e.demand_kg for e in entregas)
    fator *= fator_demanda
    entregas = [
        replace(e, demand_kg=round(max(0.5, e.demand_kg * fator) * 2) / 2)
        for e in entregas
    ]

    total_kg = sum(e.demand_kg for e in entregas)
    n_crit = sum(e.priority == Priority.CRITICAL for e in entregas)
    return Scenario(
        name=nome or f"Distribuição diária — {data}",
        date=data,
        depot=DEPOSITO,
        deliveries=entregas,
        vehicles=list(frota),
        shift_start="07:00",
        shift_minutes=480.0,
        circuity=1.35,
        policy=PriorityPolicy(),
        description=(
            f"{len(entregas)} entregas ({n_crit} críticas), {total_kg:.0f} kg, "
            f"{len(frota)} veículos — dados sintéticos sobre a geografia de São Paulo."
        ),
    )


def scaled_fleet(n_vehicles: int) -> tuple[Vehicle, ...]:
    """Frota com ``n_vehicles`` veículos repetindo o padrão da frota padrão.

    Usada nos testes de escalabilidade (instâncias maiores precisam de mais
    veículos). Os IDs seguem V1, V2, ...
    """
    frota = []
    for i in range(n_vehicles):
        base = FROTA_PADRAO[i % len(FROTA_PADRAO)]
        sufixo = f" ({i // len(FROTA_PADRAO) + 1})" if i >= len(FROTA_PADRAO) else ""
        frota.append(replace(base, id=f"V{i + 1}", name=base.name + sufixo))
    return tuple(frota)


def scaled_scenario(n_deliveries: int, seed: int = 42) -> Scenario:
    """Cenário com ``n_deliveries`` entregas e frota proporcional (≈1 veículo a cada 7 entregas)."""
    total = sum(COMPOSICAO_PADRAO.values())
    comp = {t: max(1, round(q * n_deliveries / total)) for t, q in COMPOSICAO_PADRAO.items()}
    comp["Domiciliar"] += n_deliveries - sum(comp.values())
    n_veic = max(5, round(n_deliveries / 7.2))
    return generate_scenario(seed=seed, composicao=comp, frota=scaled_fleet(n_veic),
                             nome=f"Instância com {n_deliveries} entregas")


def default_scenario() -> Scenario:
    """O cenário de referência usado em toda a documentação (semente 42)."""
    return generate_scenario(seed=42)


def weekly_scenarios(seed: int = 100, semana_inicio: str = "2026-10-12") -> list[Scenario]:
    """Cinco dias úteis com volumes diferentes (segunda mais cheia, sexta mais leve).

    Usado para simular a operação de uma semana e alimentar o relatório
    semanal da LLM.
    """
    from datetime import date, timedelta

    base = date.fromisoformat(semana_inicio)
    fatores = (1.08, 1.00, 0.96, 1.02, 0.90)
    composicoes = (
        {"UBS": 9, "UPA": 4, "AME": 3, "Hospital Dia": 2, "CAPS": 3, "Domiciliar": 17},
        {"UBS": 8, "UPA": 4, "AME": 3, "Hospital Dia": 2, "CAPS": 2, "Domiciliar": 15},
        {"UBS": 7, "UPA": 4, "AME": 3, "Hospital Dia": 2, "CAPS": 3, "Domiciliar": 14},
        {"UBS": 8, "UPA": 4, "AME": 2, "Hospital Dia": 2, "CAPS": 3, "Domiciliar": 16},
        {"UBS": 7, "UPA": 3, "AME": 3, "Hospital Dia": 2, "CAPS": 2, "Domiciliar": 13},
    )
    cenarios = []
    for i, (dia, fator, comp) in enumerate(zip(DIAS_SEMANA, fatores, composicoes)):
        d = (base + timedelta(days=i)).isoformat()
        cenarios.append(
            generate_scenario(seed=seed + i, composicao=comp, data=d,
                              nome=f"{dia}-feira — {d}", fator_demanda=fator)
        )
    return cenarios
