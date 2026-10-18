"""
Fachada do assistente: cada método é um produto da LLM pedido no enunciado.

=================================  ==========================================
``driver_instructions(veiculo)``   instruções detalhadas para o(a) motorista
``daily_report()``                 relatório diário de eficiência
``weekly_report(semana)``          relatório semanal (economia acumulada)
``improvement_suggestions()``      sugestões de melhoria a partir de padrões
``ask(pergunta, historico)``       perguntas em linguagem natural (chat)
=================================  ==========================================

Modos: ``auto`` (usa a LLM e cai para o offline se faltar chave/cota/rede),
``llm`` (exige a LLM) e ``offline`` (só templates). Toda resposta volta com
a origem (``llm``/``cache``/``offline``), o modelo, a latência e o relatório
de validação dos guardrails.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from ..plan import RoutePlan
from . import context as ctx
from . import guardrails, insights, offline, prompts
from .client import LLMError, OpenRouterClient


@dataclass
class AssistantAnswer:
    task: str
    text: str
    source: str                      # llm | cache | offline
    model: str | None = None
    latency_s: float = 0.0
    validation: dict[str, Any] | None = None
    warning: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RouteAssistant:
    """Gera textos a partir de um :class:`~medroute.plan.RoutePlan`."""

    def __init__(self, plan: RoutePlan, baseline: RoutePlan | None = None,
                 client: OpenRouterClient | None = None, mode: str = "auto") -> None:
        if mode not in ("auto", "llm", "offline"):
            raise ValueError("mode deve ser auto, llm ou offline")
        self.plan = plan
        self.baseline = baseline
        self.mode = mode
        self.client = client if client is not None else (None if mode == "offline" else OpenRouterClient())

    # ------------------------------------------------------------------ núcleo
    def _usa_llm(self) -> bool:
        return self.mode != "offline" and self.client is not None and self.client.available

    def _chamar(self, task: str, mensagens: list[dict[str, str]], max_tokens: int,
                fallback: Callable[[], str],
                validar: Callable[[str], guardrails.ValidationReport]) -> AssistantAnswer:
        aviso = None
        if self._usa_llm():
            try:
                resp = self.client.chat(mensagens, temperature=prompts.TEMPERATURA.get(task, 0.3),
                                        max_tokens=max_tokens)
                truncada = resp.finish_reason == "length"
                return AssistantAnswer(
                    task=task, text=resp.text, source="cache" if resp.cached else "llm",
                    model=resp.model, latency_s=round(resp.latency_s, 2),
                    validation=validar(resp.text).to_dict(),
                    warning="Resposta truncada pelo limite de tokens." if truncada else None,
                    extra={"usage": resp.usage, "finish_reason": resp.finish_reason,
                           "prompt_version": prompts.PROMPT_VERSION},
                )
            except LLMError as exc:
                if self.mode == "llm":
                    raise
                aviso = f"LLM indisponível ({exc}); resposta gerada em modo offline."
        elif self.mode == "llm":
            raise LLMError("modo 'llm' exige OPENROUTER_API_KEY configurada")
        elif self.mode == "auto":
            aviso = "Sem chave da OpenRouter configurada; resposta gerada em modo offline."
        texto = fallback()
        return AssistantAnswer(task=task, text=texto, source="offline",
                               validation=validar(texto).to_dict(), warning=aviso)

    @staticmethod
    def _msgs(user: str) -> list[dict[str, str]]:
        return [{"role": "system", "content": prompts.SYSTEM}, {"role": "user", "content": user}]

    # ------------------------------------------------------------- produtos
    def driver_instructions(self, vehicle_id: str) -> AssistantAnswer:
        rota = self.plan.route(vehicle_id)
        dados = ctx.route_context(rota)
        dados["data"] = self.plan.scenario.date
        dados["central"] = self.plan.scenario.depot.name
        user = prompts.instrucoes_motorista(ctx.to_json(dados), rota.vehicle_id, rota.vehicle_name)
        return self._chamar(
            "instrucoes", self._msgs(user), 3500,
            lambda: offline.driver_instructions(self.plan, rota),
            lambda t: guardrails.validate_route_text(t, rota, self.plan, dados),
        )

    def daily_report(self) -> AssistantAnswer:
        if self.baseline is not None:
            dados = ctx.comparison_context(self.plan, self.baseline)
        else:
            dados = {"medroute": ctx.kpi_context(self.plan)}
        dados["frota"] = ctx.plan_context(self.plan, include_stops=False)["veiculos"]
        dados["atrasos"] = [
            {"veiculo": r.vehicle_id, "entrega": s.delivery_id, "destino": s.name,
             "prioridade": s.priority, "prazo": s.deadline, "inicio": s.start,
             "atraso_min": round(s.lateness_min)}
            for r in self.plan.routes for s in r.stops if s.lateness_min > 0.5
        ]
        dados["data"] = self.plan.scenario.date
        user = prompts.relatorio_diario(ctx.to_json(dados), self.plan.scenario.date)
        return self._chamar(
            "relatorio_diario", self._msgs(user), 3000,
            lambda: offline.daily_report(self.plan, self.baseline),
            lambda t: guardrails.validate_free_text(t, self.plan, dados),
        )

    def weekly_report(self, semana: dict[str, Any]) -> AssistantAnswer:
        user = prompts.relatorio_semanal(ctx.to_json(semana), semana["periodo"])
        return self._chamar(
            "relatorio_semanal", self._msgs(user), 3000,
            lambda: offline.weekly_report(semana),
            lambda t: guardrails.validate_free_text(t, self.plan, semana),
        )

    def improvement_suggestions(self, run_simulations: bool = True,
                                generations: int = 250) -> AssistantAnswer:
        achados = insights.analyze_plan(self.plan, self.baseline)
        sims = []
        if run_simulations:
            for nome in insights.suggested_what_ifs(achados):
                sims.append(insights.run_what_if(self.plan, nome, generations=generations).to_dict())
        dados = {"data": self.plan.scenario.date,
                 "indicadores": ctx.kpi_context(self.plan),
                 "achados": [a.to_dict() for a in achados],
                 "simulacoes": sims}
        user = prompts.sugestoes_melhoria(ctx.to_json(dados))
        resp = self._chamar(
            "sugestoes", self._msgs(user), 3000,
            lambda: offline.suggestions(dados),
            lambda t: guardrails.validate_free_text(t, self.plan, dados),
        )
        resp.extra["achados"] = dados["achados"]
        resp.extra["simulacoes"] = sims
        return resp

    def ask(self, pergunta: str, historico: list[tuple[str, str]] | None = None) -> AssistantAnswer:
        dados = ctx.plan_context(self.plan)
        mensagens = [
            {"role": "system", "content": prompts.SYSTEM},
            {"role": "user", "content": f"<dados>\n{ctx.to_json(dados)}\n</dados>\n\n"
                                        f"{prompts.ABERTURA_CHAT}"},
            {"role": "assistant", "content": prompts.CONFIRMACAO_CHAT},
        ]
        for p, r in (historico or [])[-3:]:
            mensagens += [{"role": "user", "content": prompts.pergunta(p)},
                          {"role": "assistant", "content": r}]
        mensagens.append({"role": "user", "content": prompts.pergunta(pergunta)})
        return self._chamar(
            "pergunta", mensagens, 1200,
            lambda: offline.answer(self.plan, pergunta),
            lambda t: guardrails.validate_free_text(t, self.plan, dados),
        )
