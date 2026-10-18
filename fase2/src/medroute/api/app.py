"""
API REST do MedRoute.

    uvicorn medroute.api.app:app --reload        # http://127.0.0.1:8000/docs

Fluxo típico: ``POST /otimizar`` devolve um ``plano_id``; com ele o cliente
pede o mapa (``GET /planos/{id}/mapa``), as instruções de cada motorista, o
relatório do dia, as sugestões de melhoria ou faz perguntas em linguagem
natural. Os planos ficam em memória (é uma API de demonstração, sem banco).
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .. import __version__
from ..baselines import BASELINES, nearest_neighbor, ortools_available, run_baseline
from ..domain import Scenario
from ..ga import GAConfig, GeneticAlgorithm
from ..llm import RouteAssistant
from ..llm.client import OpenRouterClient
from ..plan import RoutePlan
from ..problem import FitnessWeights, Problem
from ..scenario import default_scenario, generate_scenario

app = FastAPI(
    title="MedRoute API",
    version=__version__,
    description=(
        "Otimização de rotas para distribuição de medicamentos e insumos hospitalares "
        "(VRP com prioridades, capacidade, autonomia, frota heterogênea, cadeia fria, "
        "controlados e janelas de horário) por **algoritmo genético**, com uma **LLM** "
        "gerando instruções, relatórios, sugestões e respostas em linguagem natural.\n\n"
        "Tech Challenge — Fase 2 (FIAP · IA para Devs)."
    ),
    openapi_tags=[
        {"name": "sistema", "description": "Saúde da API e configuração."},
        {"name": "cenários", "description": "Instâncias do problema (um dia de operação)."},
        {"name": "otimização", "description": "Algoritmo genético e abordagens de comparação."},
        {"name": "planos", "description": "Planos de rota gerados (consulta e mapa)."},
        {"name": "llm", "description": "Produtos da LLM sobre um plano."},
    ],
)

# plano_id -> (plano do GA, plano do processo atual)
PLANOS: dict[str, tuple[RoutePlan, RoutePlan]] = {}
ModoLLM = Literal["auto", "llm", "offline"]


# ---------------------------------------------------------------------------
# Modelos de entrada
# ---------------------------------------------------------------------------
class ConfigGA(BaseModel):
    geracoes: int = Field(400, ge=1, le=5000, description="Máximo de gerações")
    populacao: int = Field(120, ge=10, le=1000, description="Tamanho da população")
    seed: int = Field(42, description="Semente (mesma semente → mesmo resultado)")
    crossover: Literal["mix", "ox", "pmx", "erx", "bcrc"] = "mix"
    selecao: Literal["tournament", "roulette", "rank", "truncation"] = "tournament"
    taxa_mutacao: float = Field(0.4, ge=0, le=1)
    elitismo: int = Field(2, ge=0, le=50)
    sementes_heuristicas: bool = Field(True, description="Inclui soluções heurísticas na população inicial")
    busca_local: bool = Field(True, description="GA memético (2-opt/relocate no melhor)")
    paciencia: int | None = Field(250, description="Para após N gerações sem melhora")
    tempo_limite_s: float | None = Field(None, description="Limite de tempo em segundos")

    def to_config(self) -> GAConfig:
        return GAConfig(
            generations=self.geracoes, population_size=self.populacao, seed=self.seed,
            crossover=self.crossover, selection=self.selecao, mutation_rate=self.taxa_mutacao,
            elitism=self.elitismo, heuristic_seeds=self.sementes_heuristicas,
            local_search=self.busca_local, final_polish=self.busca_local,
            patience=self.paciencia, time_limit_s=self.tempo_limite_s,
        )


class PesosFitness(BaseModel):
    distancia: float = Field(1.0, description="Peso por km")
    prioridade: float = Field(1.0, description="Peso por (peso da prioridade × hora de chegada)")
    atraso: float = Field(1.0, description="Peso por (peso da prioridade × minuto de atraso)")
    custo: float = Field(0.0, description="Peso por R$ (0 = desligado)")

    def to_weights(self) -> FitnessWeights:
        return FitnessWeights(distance=self.distancia, priority_time=self.prioridade,
                              lateness=self.atraso, cost=self.custo)


class PedidoOtimizacao(BaseModel):
    cenario: dict[str, Any] | None = Field(
        None, description="Cenário no formato de GET /cenarios/padrao. Omitido = cenário padrão.")
    config: ConfigGA = Field(default_factory=ConfigGA)
    pesos: PesosFitness = Field(default_factory=PesosFitness)
    incluir_historico: bool = Field(False, description="Devolve a curva de convergência")


class PedidoCenario(BaseModel):
    seed: int = 42
    utilizacao_alvo: float = Field(0.68, gt=0, le=1.2,
                                   description="Fração da capacidade da frota ocupada pela demanda")
    composicao: dict[str, int] | None = Field(
        None, description='Ex.: {"UBS": 8, "UPA": 4, "AME": 3, "Hospital Dia": 2, "CAPS": 3, "Domiciliar": 16}')
    data: str = "2026-10-13"


class PedidoComparacao(BaseModel):
    cenario: dict[str, Any] | None = None
    metodos: list[str] = Field(
        default_factory=lambda: [*BASELINES, "simulated_annealing", "tsp_base_split"],
        description=f"Opções: {', '.join([*BASELINES, 'simulated_annealing', 'tsp_base_split', 'busca_aleatoria', 'melhoria_local', 'ortools'])}")
    incluir_ga: bool = True
    ortools_tempo_s: int = Field(10, ge=1, le=120)


class Pergunta(BaseModel):
    pergunta: str = Field(..., min_length=3, examples=["Qual veículo leva a insulina do PD-05?"])
    historico: list[tuple[str, str]] = Field(default_factory=list,
                                             description="Pares (pergunta, resposta) anteriores")


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------
def _cenario(d: dict[str, Any] | None) -> Scenario:
    if d is None:
        return default_scenario()
    try:
        sc = Scenario.from_dict(d)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f"cenário inválido: {exc}") from exc
    problemas = sc.validate()
    if problemas:
        raise HTTPException(422, {"cenario_invalido": problemas})
    return sc


def _plano(plano_id: str) -> tuple[RoutePlan, RoutePlan]:
    if plano_id not in PLANOS:
        raise HTTPException(404, f"plano {plano_id} não encontrado (gere com POST /otimizar)")
    return PLANOS[plano_id]


def _assistente(plano_id: str, modo: str) -> RouteAssistant:
    ga, atual = _plano(plano_id)
    return RouteAssistant(ga, atual, mode=modo)


def _resposta(r) -> dict[str, Any]:
    return r.to_dict()


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@app.get("/health", tags=["sistema"], summary="Estado da API")
def health() -> dict[str, Any]:
    cli = OpenRouterClient()
    return {"status": "ok", "versao": __version__,
            "llm": {"chave_configurada": cli.available, "modelos": cli.models},
            "ortools_disponivel": ortools_available(), "planos_em_memoria": len(PLANOS)}


@app.get("/cenarios/padrao", tags=["cenários"], summary="Cenário de referência (semente 42)")
def cenario_padrao() -> dict[str, Any]:
    return default_scenario().to_dict()


@app.post("/cenarios/gerar", tags=["cenários"], summary="Gera um cenário sintético reprodutível")
def gerar_cenario(p: PedidoCenario) -> dict[str, Any]:
    return generate_scenario(seed=p.seed, composicao=p.composicao,
                             utilizacao_alvo=p.utilizacao_alvo, data=p.data).to_dict()


@app.post("/otimizar", tags=["otimização"], summary="Roda o algoritmo genético")
def otimizar(p: PedidoOtimizacao) -> dict[str, Any]:
    sc = _cenario(p.cenario)
    problema = Problem(sc, p.pesos.to_weights())
    cfg = p.config.to_config()
    res = GeneticAlgorithm(problema, cfg).run()
    ga = RoutePlan.from_evaluation(problema, res.evaluation, "MedRoute (algoritmo genético)",
                                   res.runtime_s, meta={"config": cfg.to_dict(),
                                                        "parada": res.stop_reason})
    atual = RoutePlan.from_evaluation(problema, problema.evaluate(nearest_neighbor(problema, True)),
                                      "Processo atual (despachante)")
    plano_id = uuid.uuid4().hex[:10]
    PLANOS[plano_id] = (ga, atual)
    out: dict[str, Any] = {"plano_id": plano_id, "plano": ga.to_dict(),
                           "comparacao_processo_atual": ga.compare(atual),
                           "geracoes": res.generations_run, "avaliacoes": res.evaluations}
    if p.incluir_historico:
        out["historico"] = [{"geracao": h.generation, "melhor": round(h.best, 2),
                             "media": round(h.mean, 2), "km": round(h.best_distance_km, 2)}
                            for h in res.history]
    return out


@app.post("/comparar", tags=["otimização"], summary="Compara abordagens no mesmo cenário")
def comparar(p: PedidoComparacao) -> dict[str, Any]:
    sc = _cenario(p.cenario)
    problema = Problem(sc)
    linhas = []
    for nome in p.metodos:
        if nome == "ortools" and not ortools_available():
            linhas.append({"metodo": "ortools", "erro": "OR-Tools indisponível neste ambiente"})
            continue
        try:
            r = run_baseline(nome, problema, time_limit_s=p.ortools_tempo_s)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        k = RoutePlan.from_evaluation(problema, r.evaluation, r.name, r.runtime_s).kpis
        linhas.append({"metodo": r.name, "km": k.total_km, "custo_rs": k.cost_total_brl,
                       "no_prazo_pct": k.on_time_pct, "violacoes": k.violations,
                       "fitness": k.fitness, "tempo_s": round(r.runtime_s, 3)})
    if p.incluir_ga:
        res = GeneticAlgorithm(problema, GAConfig()).run()
        k = RoutePlan.from_evaluation(problema, res.evaluation, "GA", res.runtime_s).kpis
        linhas.append({"metodo": "MedRoute (algoritmo genético)", "km": k.total_km,
                       "custo_rs": k.cost_total_brl, "no_prazo_pct": k.on_time_pct,
                       "violacoes": k.violations, "fitness": k.fitness,
                       "tempo_s": round(res.runtime_s, 3)})
    return {"resultados": sorted(linhas, key=lambda x: x.get("fitness", float("inf")))}


@app.get("/planos/{plano_id}", tags=["planos"], summary="Plano completo (rotas, horários, KPIs)")
def obter_plano(plano_id: str) -> dict[str, Any]:
    ga, atual = _plano(plano_id)
    return {"plano": ga.to_dict(), "processo_atual": atual.to_dict()}


@app.get("/planos/{plano_id}/mapa", tags=["planos"], response_class=HTMLResponse,
         summary="Mapa interativo (HTML/Leaflet)")
def mapa(plano_id: str, processo_atual: bool = False) -> HTMLResponse:
    from ..viz.folium_map import build_route_map

    ga, atual = _plano(plano_id)
    return HTMLResponse(build_route_map(atual if processo_atual else ga).get_root().render())


@app.post("/planos/{plano_id}/instrucoes/{veiculo}", tags=["llm"],
          summary="Instruções detalhadas para o(a) motorista")
def instrucoes(plano_id: str, veiculo: str, modo: ModoLLM = Query("auto")) -> dict[str, Any]:
    a = _assistente(plano_id, modo)
    try:
        a.plan.route(veiculo)
    except KeyError as exc:
        raise HTTPException(404, f"veículo {veiculo} não existe") from exc
    return _resposta(a.driver_instructions(veiculo))


@app.post("/planos/{plano_id}/relatorio", tags=["llm"], summary="Relatório diário de eficiência")
def relatorio(plano_id: str, modo: ModoLLM = Query("auto")) -> dict[str, Any]:
    return _resposta(_assistente(plano_id, modo).daily_report())


@app.post("/planos/{plano_id}/sugestoes", tags=["llm"],
          summary="Sugestões de melhoria (com simulações 'e se')")
def sugestoes(plano_id: str, modo: ModoLLM = Query("auto"),
              simular: bool = Query(True, description="Roda as simulações 'e se'")) -> dict[str, Any]:
    return _resposta(_assistente(plano_id, modo).improvement_suggestions(run_simulations=simular))


@app.post("/planos/{plano_id}/perguntar", tags=["llm"], summary="Pergunta em linguagem natural")
def perguntar(plano_id: str, p: Pergunta, modo: ModoLLM = Query("auto")) -> dict[str, Any]:
    return _resposta(_assistente(plano_id, modo).ask(p.pergunta, list(p.historico)))
