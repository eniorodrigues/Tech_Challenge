"""
Cliente da OpenRouter (API compatível com a da OpenAI) para modelos gratuitos.

Decisões de projeto
-------------------
* **Só modelos gratuitos** (sufixo ``:free``). A conta usada no projeto só
  libera provedores NVIDIA/Z-AI, por isso a cadeia padrão é a família
  Nemotron. A lista pode ser trocada pela variável ``MEDROUTE_LLM_MODELS``.
* **Cadeia de fallback**: se um modelo falha (indisponível, sobrecarregado,
  resposta vazia), tenta o próximo. ``openrouter/free`` fecha a cadeia — é o
  roteador da própria OpenRouter que escolhe um modelo gratuito disponível.
* **Cache em disco** por hash do pedido: a cota gratuita é de ~50
  requisições/dia, então a mesma pergunta nunca é paga duas vezes (e as
  demonstrações ficam reprodutíveis).
* **Cota diária esgotada** levanta :class:`QuotaExceeded`; o assistente cai
  para o modo offline (templates determinísticos) em vez de quebrar.
* A chave vem de ``OPENROUTER_API_KEY`` (arquivo ``.env`` local, fora do git)
  e nunca é registrada em log nem gravada no cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from ..config import CACHE_DIR, PROJECT_ROOT

BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODELS = (
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/free",
)


class LLMError(RuntimeError):
    """Falha ao obter resposta de qualquer modelo da cadeia."""


class QuotaExceeded(LLMError):
    """A cota diária de requisições gratuitas acabou."""


@dataclass
class LLMResponse:
    text: str
    model: str
    cached: bool
    latency_s: float
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""


def _carregar_env() -> None:
    """Carrega ``fase2/.env`` se existir (sem sobrescrever o ambiente)."""
    arquivo = PROJECT_ROOT / ".env"
    if arquivo.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(arquivo, override=False)
        except ImportError:  # pragma: no cover - python-dotenv está nas dependências
            for linha in arquivo.read_text(encoding="utf-8").splitlines():
                if "=" in linha and not linha.lstrip().startswith("#"):
                    k, v = linha.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


class OpenRouterClient:
    """Cliente mínimo, com fallback de modelos, *retry* e cache."""

    def __init__(
        self,
        api_key: str | None = None,
        models: list[str] | tuple[str, ...] | None = None,
        base_url: str = BASE_URL,
        timeout: float = 180.0,
        cache_dir: Path | None = CACHE_DIR / "llm",
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
        reasoning: dict[str, Any] | None = None,
    ) -> None:
        _carregar_env()
        self.reasoning = reasoning if reasoning is not None else {"enabled": False}
        self._api_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY", "")
        env_models = os.getenv("MEDROUTE_LLM_MODELS", "").strip()
        if models is None:
            models = [m.strip() for m in env_models.split(",") if m.strip()] or list(DEFAULT_MODELS)
        self.models = list(models)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cache_dir = cache_dir
        self.max_retries = max_retries
        self._transport = transport
        self.calls = 0          # requisições reais feitas (sem contar cache)

    # ---------------------------------------------------------------- estado
    @property
    def available(self) -> bool:
        """Há chave configurada? (não garante cota nem rede)."""
        return bool(self._api_key)

    def __repr__(self) -> str:  # nunca expõe a chave
        return f"OpenRouterClient(models={self.models}, key={'sim' if self.available else 'não'})"

    # ----------------------------------------------------------------- cache
    def _chave_cache(self, payload: dict[str, Any]) -> str:
        bruto = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(bruto).hexdigest()[:32]

    def _ler_cache(self, chave: str) -> LLMResponse | None:
        if self.cache_dir is None:
            return None
        arq = self.cache_dir / f"{chave}.json"
        if not arq.exists():
            return None
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
            return LLMResponse(text=d["text"], model=d["model"], cached=True, latency_s=0.0,
                               usage=d.get("usage", {}), finish_reason=d.get("finish_reason", ""))
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def _gravar_cache(self, chave: str, resp: LLMResponse, payload: dict[str, Any]) -> None:
        if self.cache_dir is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / f"{chave}.json").write_text(json.dumps({
            "text": resp.text, "model": resp.model, "usage": resp.usage,
            "finish_reason": resp.finish_reason, "latency_s": resp.latency_s,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "messages": payload["messages"],
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------ HTTP
    def _post(self, body: dict[str, Any]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/tech-challenge-fiap/medroute",
            "X-Title": "MedRoute - Tech Challenge Fase 2",
        }
        with httpx.Client(timeout=self.timeout, transport=self._transport) as cli:
            return cli.post(f"{self.base_url}/chat/completions", headers=headers, json=body)

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        use_cache: bool = True,
    ) -> LLMResponse:
        """Envia a conversa e devolve o texto da primeira resposta válida."""
        payload = {"models": self.models, "messages": messages, "temperature": temperature,
                   "max_tokens": max_tokens, "reasoning": self.reasoning}
        chave = self._chave_cache(payload)
        if use_cache:
            hit = self._ler_cache(chave)
            if hit is not None:
                return hit
        if not self.available:
            raise LLMError("OPENROUTER_API_KEY não configurada (veja .env.example).")

        erros: list[str] = []
        for modelo in self.models:
            body = {
                "model": modelo,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                # Modelos de raciocínio: o "pensamento" interno conta no limite de
                # tokens e triplica a latência. Para redigir dados já calculados
                # ele não é necessário, então fica desligado (configurável).
                "reasoning": self.reasoning,
            }
            for tentativa in range(self.max_retries + 1):
                t0 = time.perf_counter()
                try:
                    r = self._post(body)
                except httpx.HTTPError as exc:
                    erros.append(f"{modelo}: rede ({type(exc).__name__})")
                    time.sleep(2 * (tentativa + 1))
                    continue
                dt = time.perf_counter() - t0
                self.calls += 1
                if r.status_code == 200:
                    try:
                        dados = r.json()
                        escolha = dados["choices"][0]
                        texto = (escolha.get("message") or {}).get("content") or ""
                    except (ValueError, KeyError, IndexError):
                        erros.append(f"{modelo}: resposta malformada")
                        break
                    if not texto.strip():
                        erros.append(f"{modelo}: resposta vazia")
                        break  # próximo modelo
                    if escolha.get("finish_reason") == "error":
                        # O provedor caiu no meio da geração e a OpenRouter devolveu
                        # o texto parcial. Não serve (nem para o cache): tenta de novo.
                        erros.append(f"{modelo}: geração interrompida pelo provedor")
                        time.sleep(2 * (tentativa + 1))
                        continue
                    resp = LLMResponse(
                        text=texto.strip(), model=dados.get("model", modelo), cached=False,
                        latency_s=dt, usage=dados.get("usage") or {},
                        finish_reason=escolha.get("finish_reason") or "",
                    )
                    self._gravar_cache(chave, resp, payload)
                    return resp
                msg = r.text[:300]
                if r.status_code == 429:
                    if "per-day" in msg or "per day" in msg or "free-models-per-day" in msg:
                        raise QuotaExceeded(
                            "Cota diária de requisições gratuitas da OpenRouter esgotada "
                            "(renova à 0h UTC).")
                    espera = float(r.headers.get("Retry-After", 0) or 0) or 5 * (tentativa + 1)
                    erros.append(f"{modelo}: 429 (aguardando {espera:.0f}s)")
                    time.sleep(min(espera, 30))
                    continue
                if r.status_code in (500, 502, 503, 504):
                    erros.append(f"{modelo}: {r.status_code}")
                    time.sleep(3 * (tentativa + 1))
                    continue
                # 400/401/403/404: problema do modelo/conta -> próximo modelo
                erros.append(f"{modelo}: HTTP {r.status_code}")
                if r.status_code == 401:
                    raise LLMError("Chave da OpenRouter recusada (401). Verifique o .env.")
                break
        raise LLMError("Nenhum modelo respondeu: " + "; ".join(erros))
