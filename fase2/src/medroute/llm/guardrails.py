"""
Validação automática das saídas da LLM contra os dados do plano.

Para cada texto gerado, mede:

* **cobertura** — fração das paradas da rota citadas no texto;
* **ordem** — as paradas aparecem na mesma ordem da rota?
* **horários** — fração dos horários de chegada da rota que aparecem no texto;
* **IDs inexistentes** — códigos ``E##``/``V#`` que não existem nos dados;
* **horários inventados** — ``HH:MM`` citados que não existem em lugar
  nenhum dos dados (chegada, início, saída, janela, prazo, retorno);
* **números não rastreáveis** — valores com unidade (km, kg, R$, %) que não
  batem com nenhum número do contexto (tolerância de arredondamento). É um
  alerta, não um erro: somas e diferenças legítimas também caem aqui.

O resultado vira uma **nota de fidelidade** (0–100) exibida junto da
resposta. Assim a qualidade da LLM é avaliada objetivamente, resposta a
resposta, e não só "no olho".
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from ..plan import RoutePlan, RouteView

_RE_HORA = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")   # "2h20" é duração, não horário
_RE_ID_ENTREGA = re.compile(r"\bE\d{2}\b")
_RE_ID_VEICULO = re.compile(r"\bV\d{1,2}\b")
_RE_NUM_UNIDADE = re.compile(
    r"(R\$\s*)?(?<![\w.,:])(\d+(?:[.,]\d+)*)\s*(km|kg|%|h\b|min\b)?",
    re.IGNORECASE,
)


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _hora(h: str, m: str) -> str:
    return f"{int(h):02d}:{m}"


def horarios_do_texto(texto: str) -> list[str]:
    return [_hora(h, m) for h, m in _RE_HORA.findall(texto)]


def _chaves_parada(nome: str, ident: str) -> list[str]:
    """Formas aceitas de citar uma parada: ID, nome completo, nome sem parênteses."""
    chaves = [ident.lower(), _norm(nome)]
    base = re.sub(r"\s*\(.*?\)", "", nome).strip()
    if base and base != nome:
        chaves.append(_norm(base))
    m = re.search(r"PD-\d+", nome)
    if m:
        chaves.append(m.group(0).lower())
    return chaves


def _horarios_validos(plan: RoutePlan, contexto: Any = None) -> set[str]:
    validos = {plan.scenario.shift_start, plan.scenario.clock(plan.scenario.shift_minutes),
               plan.kpis.makespan, plan.kpis.avg_critical_arrival}
    if contexto is not None:
        validos.update(horarios_do_texto(json.dumps(contexto, ensure_ascii=False)))
    for r in plan.routes:
        validos.update({r.departure, r.return_time})
        for s in r.stops:
            validos.update({s.arrival, s.start, s.departure})
            if s.deadline:
                validos.add(s.deadline)
            validos.update(s.window.split("–"))
    return {v for v in validos if v and ":" in v}


def _numeros_validos(obj: Any, acc: set[float] | None = None,
                     por_chave: dict[str, list[float]] | None = None, chave: str = "") -> set[float]:
    """Todos os números do contexto + diferenças entre valores da mesma chave.

    As diferenças cobrem comparações legítimas ("−34,9 km" entre o ``km``
    de antes e o de depois de uma simulação) sem liberar qualquer número.
    """
    raiz = acc is None
    acc = set() if acc is None else acc
    por_chave = {} if por_chave is None else por_chave
    if isinstance(obj, bool):
        return acc
    if isinstance(obj, (int, float)):
        acc.add(round(float(obj), 1))
        acc.add(float(round(obj)))
        por_chave.setdefault(chave, []).append(float(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _numeros_validos(v, acc, por_chave, str(k))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numeros_validos(v, acc, por_chave, chave)
    elif isinstance(obj, str):
        for n in re.findall(r"\d+(?:[.,]\d+)?", obj):
            v = _para_float(n)
            if v is not None:
                acc.add(round(v, 1))
    if raiz:
        for valores in por_chave.values():
            if 2 <= len(valores) <= 40:
                for i, a in enumerate(valores):
                    for b in valores[i + 1:]:
                        acc.add(round(abs(a - b), 1))
                        acc.add(round(abs(a - b), 2))
    return acc


def _para_float(txt: str) -> float | None:
    t = txt.strip().replace(" ", "")
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):     # 1.234,56 (pt-BR)
            t = t.replace(".", "").replace(",", ".")
        else:                               # 1,234.56 (en)
            t = t.replace(",", "")
    elif "," in t:                          # 12,5
        t = t.replace(",", ".") if t.count(",") == 1 else t.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):  # 1.160 (milhar pt-BR)
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


# Palavras que indicam cada requisito e nomes de medicamentos usados para
# ligar uma frase genérica ("itens controlados (Ceftriaxona ...)") à entrega.
_CHAVES_REQUISITO = {
    "controlado": ("controlad", "344"),
    "refrigerado": ("refrigerad", "cadeia fria", "2-8", "2–8", "2 a 8", "termolabil"),
}
_REMEDIOS = ("insulina", "alteplase", "meropenem", "vacina", "heparina", "enoxaparina",
             "ceftriaxona", "naloxona", "flumazenil", "morfina", "fentanil", "clonazepam",
             "haloperidol", "quimioter")


def requisitos_inventados(texto: str, paradas: list, ignorar: Iterable[str] = (),
                          por_veiculo: dict[str, list] | None = None) -> list[str]:
    """Detecta cuidados especiais atribuídos a entregas que não os exigem.

    Ex.: chamar de "controlado (Portaria 344/98)" um antibiótico comum, ou
    pedir cadeia fria para fraldas. A leitura prioriza **precisão** (poucos
    falsos alarmes) e só liga uma palavra-chave a uma entrega quando a
    associação é inequívoca:

    * **bloco da parada** — o cabeçalho que cita uma única parada (fora de
      lista) abre o bloco; as linhas recuadas seguintes pertencem a ela;
    * **nome do medicamento** — linha sem parada citada que menciona o
      remédio de uma entrega ("lacre para controlados (Ceftriaxona…)").

    * **lista introduzida por uma frase** — "Há 7 entregas com requisito
      controlado:" seguida de itens: cada entrega listada herda o requisito
      (foi assim que a avaliação pegou a LLM listando um CAPS sem controlados);
    * **contagens** — "N entregas controladas/refrigeradas" é comparado com
      o número real dentro do escopo avaliado.

    Itens de lista que citam paradas no meio de uma frase ("priorizar a
    crítica PD-14 e os controlados") são ambíguos e não geram alerta.
    """
    alertas: set[str] = set()
    atual = None
    contexto: set[str] = set()        # requisitos anunciados pela frase que abre uma lista
    # Nomes de veículo ("Van Refrigerada 01") não são requisito da entrega.
    remover = sorted({_norm(x) for x in ignorar} | {"van refrigerada", "bau termico"},
                     key=len, reverse=True)

    texto_norm = _norm(texto)
    for nome in remover:
        texto_norm = texto_norm.replace(nome, " ")
    # "6 entregas controladas", "7 entregas com requisito controlado": o requisito
    # precisa vir logo depois, na mesma oração (sem parênteses, vírgula ou ponto).
    for m in re.finditer(r"(\d+)\s+(?:entregas?|paradas?)[^.\n,;()]{0,25}?"
                         r"(controlad|refrigerad|cadeia fria)", texto_norm):
        req = "controlado" if m.group(2).startswith("controlad") else "refrigerado"
        real = sum(req in p.requirements for p in paradas)
        # A contagem pode ser de um veículo citado na mesma linha ("2 controladas na V1").
        ini = texto_norm.rfind("\n", 0, m.start()) + 1
        fim = texto_norm.find("\n", m.end())
        linha_m = texto_norm[ini:fim if fim >= 0 else None]
        aceitos = {real}
        for vid in re.findall(r"\bv(\d{1,2})\b", linha_m):
            aceitos.add(sum(req in p.requirements
                            for p in (por_veiculo or {}).get(f"V{vid}", [])))
        if int(m.group(1)) not in aceitos:
            alertas.add(f"contagem: {m.group(1)} entregas com {req} (dados: {real})")

    for linha in texto.splitlines():
        ln = _norm(linha)
        for nome in remover:
            ln = ln.replace(nome, " ")
        bruto = ln.strip()
        if bruto.startswith("#") or bruto.startswith("---") or bruto.startswith("**pergunta") \
                or bruto.startswith("**resposta"):
            atual, contexto = None, set()
            continue
        recuada = bool(re.match(r"^\s{2,}\S", linha))
        item_lista = bool(re.match(r"^[-*] ", linha))
        reqs_linha = {req for req, chaves in _CHAVES_REQUISITO.items()
                      if any(k in ln for k in chaves)}
        citadas = [p for p in paradas
                   if any(c and c in ln for c in _chaves_parada(p.name, p.delivery_id))]
        if citadas:
            if item_lista or len(citadas) > 1:
                for p in citadas:                     # item de uma lista anunciada
                    for req in contexto:
                        if req not in p.requirements:
                            alertas.add(f"{p.delivery_id} listado como {req}")
                atual = None
                continue                              # frase de resumo: ambígua
            atual = citadas[0]
            alvo = [atual]
        elif not item_lista and not recuada and bruto:
            # Frase fora de lista e sem parada citada: pode anunciar a lista seguinte
            # ("Há 7 entregas com requisito controlado:"). Rótulos curtos em negrito
            # ("**Van 02 (V2)**") mantêm o anúncio; parágrafos comuns o encerram.
            rotulo = bruto.startswith("**") and bruto.endswith("**") and len(bruto) <= 60
            if reqs_linha:
                contexto = reqs_linha
            elif not rotulo:
                contexto = set()
            atual = None
            alvo = [p for p in paradas if any(r in ln for r in _REMEDIOS if r in _norm(p.items))]
        elif recuada and atual is not None:
            alvo = [atual]
        else:
            if item_lista or not recuada:
                atual = None
            alvo = [p for p in paradas if any(r in ln for r in _REMEDIOS if r in _norm(p.items))]
        for req, chaves in _CHAVES_REQUISITO.items():
            if any(k in ln for k in chaves):
                for p in alvo:
                    if req not in p.requirements:
                        alertas.add(f"{p.delivery_id} tratado como {req}")
    return sorted(alertas)


@dataclass
class ValidationReport:
    nota: float
    cobertura_paradas: float | None = None
    ordem_correta: bool | None = None
    horarios_citados: float | None = None
    ids_inexistentes: list[str] = field(default_factory=list)
    horarios_inventados: list[str] = field(default_factory=list)
    numeros_nao_rastreaveis: list[str] = field(default_factory=list)
    requisitos_inventados: list[str] = field(default_factory=list)
    observacoes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _checagens_gerais(texto: str, plan: RoutePlan, contexto: Any,
                      rep: ValidationReport, paradas: list | None = None) -> None:
    ids_entrega = {d.id for d in plan.scenario.deliveries}
    ids_veic = {v.id for v in plan.scenario.vehicles}
    rep.ids_inexistentes = sorted(
        {i for i in _RE_ID_ENTREGA.findall(texto) if i not in ids_entrega}
        | {i for i in _RE_ID_VEICULO.findall(texto) if i not in ids_veic}
    )
    validos = _horarios_validos(plan, contexto)
    rep.horarios_inventados = sorted({h for h in horarios_do_texto(texto) if h not in validos})
    if paradas is None:
        paradas = [st for r in plan.routes for st in r.stops]
    rep.requisitos_inventados = requisitos_inventados(
        texto, paradas, [v.name for v in plan.scenario.vehicles],
        por_veiculo={r.vehicle_id: list(r.stops) for r in plan.routes})

    nums = _numeros_validos(contexto)
    suspeitos = []
    for m in _RE_NUM_UNIDADE.finditer(texto):
        moeda, valor, unidade = m.group(1), m.group(2), m.group(3)
        if not (moeda or unidade):
            continue
        v = _para_float(valor)
        if v is None or v in (0.0, 1.0, 2.0, 100.0):
            continue
        if not any(abs(v - n) <= max(0.06, 0.006 * abs(n)) for n in nums):
            suspeitos.append(m.group(0).strip())
    rep.numeros_nao_rastreaveis = suspeitos[:12]


def _nota(rep: ValidationReport) -> float:
    nota = 100.0
    if rep.cobertura_paradas is not None:
        nota -= 40 * (1 - rep.cobertura_paradas)
    if rep.ordem_correta is False:
        nota -= 15
    if rep.horarios_citados is not None:
        nota -= 15 * (1 - rep.horarios_citados)
    nota -= 10 * min(3, len(rep.ids_inexistentes))
    nota -= 8 * min(3, len(rep.horarios_inventados))
    nota -= 2 * min(5, len(rep.numeros_nao_rastreaveis))
    nota -= 10 * min(3, len(rep.requisitos_inventados))
    return round(max(0.0, nota), 1)


def validate_route_text(texto: str, route: RouteView, plan: RoutePlan,
                        contexto: Any = None) -> ValidationReport:
    """Valida instruções de um motorista contra a rota daquele veículo."""
    t = _norm(texto)
    # Todas as menções de cada parada (o texto pode citar uma parada no
    # resumo antes da lista; a ordem é checada com a menção mais adequada).
    mencoes: list[list[int]] = []
    for s in route.stops:
        pos: set[int] = set()
        for c in _chaves_parada(s.name, s.delivery_id):
            if not c:
                continue
            for m in re.finditer(re.escape(c), t):
                pos.add(m.start())
        mencoes.append(sorted(pos))
    posicoes = [m[0] if m else -1 for m in mencoes]
    citadas = [p for p in posicoes if p >= 0]
    rep = ValidationReport(nota=0.0)
    if route.stops:
        rep.cobertura_paradas = round(len(citadas) / len(route.stops), 3)
        # Existe uma escolha de menções em ordem crescente? (guloso)
        ultimo, em_ordem = -1, True
        for m in mencoes:
            if not m:
                continue
            prox = next((p for p in m if p > ultimo), None)
            if prox is None:
                em_ordem = False
                break
            ultimo = prox
        rep.ordem_correta = em_ordem
        horas_texto = set(horarios_do_texto(texto))
        rep.horarios_citados = round(
            sum(1 for s in route.stops if s.arrival in horas_texto or s.start in horas_texto)
            / len(route.stops), 3)
        faltando = [s.delivery_id for s, p in zip(route.stops, posicoes) if p < 0]
        if faltando:
            rep.observacoes.append("paradas não citadas: " + ", ".join(faltando))
    # Paradas de OUTROS veículos citadas nas instruções deste motorista.
    outras = [s for r in plan.routes if r.vehicle_id != route.vehicle_id for s in r.stops]
    ids_citados = set(_RE_ID_ENTREGA.findall(texto))
    intrusas = [s.delivery_id for s in outras
                if s.delivery_id in ids_citados or _norm(s.name) in t]
    if intrusas:
        rep.observacoes.append("cita entregas de outros veículos: " + ", ".join(intrusas))
    _checagens_gerais(texto, plan, contexto if contexto is not None else plan.to_dict(), rep,
                      paradas=list(route.stops))
    rep.nota = _nota(rep)
    return rep


def validate_free_text(texto: str, plan: RoutePlan, contexto: Any = None,
                       required_terms: Iterable[str] = ()) -> ValidationReport:
    """Valida relatórios e respostas livres (sem exigência de cobrir paradas)."""
    rep = ValidationReport(nota=0.0)
    _checagens_gerais(texto, plan, contexto if contexto is not None else plan.to_dict(), rep)
    t = _norm(texto)
    ausentes = [termo for termo in required_terms if _norm(termo) not in t]
    if ausentes:
        rep.observacoes.append("termos esperados ausentes: " + ", ".join(ausentes))
    rep.nota = _nota(rep) - 5 * len(ausentes)
    rep.nota = max(0.0, rep.nota)
    return rep
