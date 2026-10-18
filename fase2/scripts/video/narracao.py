"""
Narração em pt-BR com voz neural gratuita.

Motor padrão: **Piper** (TTS neural de código aberto, roda localmente,
voz ``pt_BR-faber-medium``). O edge-tts usado na Fase 1 passou a receber
HTTP 403 do serviço da Microsoft (versão do cliente recusada) e a OpenRouter
não oferece voz gratuita — o Piper resolve sem rede, sem chave e sem custo.

* A voz é baixada uma vez para ``_cache/vozes`` (``python -m piper.download_voices``).
* O Piper devolve o áudio **frase a frase**, então as legendas ``.srt`` saem
  com os tempos reais de cada frase.
* ``PRONUNCIA`` ajusta siglas e termos em inglês **só no texto enviado à voz**
  (ex.: "UBS" → "U B S"); a legenda mantém a grafia correta.
* Cache por ``sha256(motor + voz + velocidade + texto)``.

Também aceita ``--voz edge:pt-BR-AntonioNeural`` (edge-tts), se o serviço
voltar a responder.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import re
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import montagem
from roteiro import AUDIO_DIR, CACHE_DIR, Cena

VOZ_PADRAO = "piper:pt_BR-faber-medium"
VOZES_DIR = CACHE_DIR / "vozes"
TICKS_POR_SEGUNDO = 10_000_000

# Só para a voz: a legenda continua com o texto original.
PRONUNCIA: dict[str, str] = {
    "python main ponto py": "páiton mêin ponto pai",
    "Simulated Annealing": "Símiuleited Anílin",
    "OR-Tools": "ó érre túls",
    "OpenRouter": "Ópen Ráuter",
    "Med Route": "Méd Ráut",
    "API REST": "A P I rést",
    "Streamlit": "Strímlit",
    "Matplotlib": "Mét plót lib",
    "Nemotron": "Nêmotron",
    "guardrails": "gárd rêils",
    "relocate": "rilokêit",
    "pygame": "pai gueime",
    "Python": "Páiton",
    "NVIDIA": "en vídia",
    "Google": "Gúgol",
    "fitness": "fítnes",
    "offline": "óf láine",
    "prompt": "prômpt",
    "cache": "quéche",
    "JSON": "jêison",
    "BCRC": "B C R C",
    "LLM": "L L M",
    "API": "A P I",
    "UBS": "U B S",
    "AME": "A M E",
    "CAPS": "Caps",
    "UPA": "Úpa",
    "PMX": "P M X",
    "ERX": "E R X",
    "TSP": "T S P",
    "VRP": "V R P",
    "OX": "O X",
    "V1": "vê um",
    "V2": "vê dois",
    "V3": "vê três",
    "V4": "vê quatro",
    "V5": "vê cinco",
    "bug": "bâg",
    "dois opt": "dois ópt",
}


def texto_falado(texto: str) -> str:
    for termo in sorted(PRONUNCIA, key=len, reverse=True):
        texto = re.sub(rf"(?<!\w){re.escape(termo)}(?!\w)", PRONUNCIA[termo], texto)
    return texto


@dataclass
class Trecho:
    inicio: float
    fim: float
    texto: str


@dataclass
class Fala:
    cena_id: str
    caminho: Path
    duracao: float
    trechos: list[Trecho]


class SemInternet(RuntimeError):
    """Mantido por compatibilidade (edge-tts precisa de rede)."""


def _frases(texto: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", texto) if s.strip()]


def _hash(*partes: str) -> str:
    return hashlib.sha256("||".join(partes).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Piper (padrão)
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=2)
def _voz_piper(nome: str):
    from piper import PiperVoice

    modelo = VOZES_DIR / f"{nome}.onnx"
    if not modelo.exists():
        VOZES_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "piper.download_voices", "--data-dir",
                        str(VOZES_DIR), nome], check=True)
    return PiperVoice.load(str(modelo))


def _escala(rate: str) -> float:
    """'+4%' → fala 4% mais rápida (length_scale menor)."""
    m = re.fullmatch(r"([+-]?\d+)%", rate.strip())
    pct = int(m.group(1)) if m else 0
    return 0.95 / (1 + pct / 100)


def _sintetizar_piper(texto: str, nome: str, rate: str, destino: Path) -> list[Trecho]:
    from piper import SynthesisConfig

    voz = _voz_piper(nome)
    falado = texto_falado(texto)
    cfg = SynthesisConfig(length_scale=_escala(rate))
    partes = list(voz.synthesize(falado, syn_config=cfg))
    if not partes:
        raise RuntimeError("Piper não gerou áudio")
    taxa, larg, canais = partes[0].sample_rate, partes[0].sample_width, partes[0].sample_channels
    silencio = b"\x00" * int(taxa * 0.18) * larg * canais        # respiro entre frases
    duracoes = []
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(canais)
        w.setsampwidth(larg)
        w.setframerate(taxa)
        for k, p in enumerate(partes):
            w.writeframes(p.audio_int16_bytes)
            extra = silencio if k < len(partes) - 1 else b""
            w.writeframes(extra)
            duracoes.append((len(p.audio_int16_bytes) + len(extra)) / (taxa * larg * canais))
    frases = _frases(texto)
    trechos: list[Trecho] = []
    if len(frases) == len(partes):
        t = 0.0
        for f, d in zip(frases, duracoes):
            trechos.append(Trecho(t, t + d, f))
            t += d
    else:   # segmentação diferente: reparte pelo tamanho das frases
        total, chars = sum(duracoes), sum(len(f) for f in frases) or 1
        t = 0.0
        for f in frases:
            d = total * len(f) / chars
            trechos.append(Trecho(t, t + d, f))
            t += d
    return trechos


# ---------------------------------------------------------------------------
# edge-tts (opcional)
# ---------------------------------------------------------------------------
async def _edge(texto: str, voz: str, rate: str, destino: Path) -> list[dict]:
    import edge_tts

    com = edge_tts.Communicate(texto, voz, rate=rate, boundary="SentenceBoundary")
    audio, bounds = bytearray(), []
    async for p in com.stream():
        if p["type"] == "audio":
            audio.extend(p["data"])
        elif p["type"].endswith("Boundary"):
            bounds.append(p)
    if not audio:
        raise SemInternet("edge-tts devolveu áudio vazio")
    destino.write_bytes(bytes(audio))
    return bounds


def _sintetizar_edge(texto: str, voz: str, rate: str, destino: Path) -> list[Trecho]:
    try:
        bounds = asyncio.run(_edge(texto_falado(texto), voz, rate, destino))
    except Exception as exc:
        raise SemInternet(f"edge-tts indisponível ({type(exc).__name__}: {exc}). "
                          "Use a voz padrão (Piper).") from exc
    frases = _frases(texto)
    trechos = [Trecho(b["offset"] / TICKS_POR_SEGUNDO,
                      (b["offset"] + b["duration"]) / TICKS_POR_SEGUNDO, b["text"]) for b in bounds]
    if len(trechos) == len(frases):
        for t, f in zip(trechos, frases):
            t.texto = f
    return trechos


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def gerar_fala(cena: Cena, voz: str = VOZ_PADRAO, rate: str = "+0%", forcar: bool = False) -> Fala:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    motor, _, nome = voz.partition(":") if ":" in voz else ("edge", "", voz)
    assinatura = _hash(motor, nome, rate, texto_falado(cena.narracao), cena.narracao)
    destino = AUDIO_DIR / f"{cena.id}.{'wav' if motor == 'piper' else 'mp3'}"
    meta = AUDIO_DIR / f"{cena.id}.json"
    if not forcar and destino.exists() and meta.exists():
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
            if m.get("hash") == assinatura:
                return Fala(cena.id, destino, float(m["duracao"]), [Trecho(**t) for t in m["trechos"]])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
    if motor == "piper":
        trechos = _sintetizar_piper(cena.narracao, nome, rate, destino)
    else:
        trechos = _sintetizar_edge(cena.narracao, nome, rate, destino)
    duracao = montagem.duracao_audio(destino)
    for t in trechos:
        t.fim = min(t.fim, duracao)
    meta.write_text(json.dumps({"hash": assinatura, "voz": voz, "duracao": duracao,
                                "trechos": [t.__dict__ for t in trechos]}, ensure_ascii=False,
                               indent=1), encoding="utf-8")
    return Fala(cena.id, destino, duracao, trechos)


def legendas_da_cena(fala: Fala, deslocamento: float) -> list[montagem.Legenda]:
    legendas: list[montagem.Legenda] = []
    for tr in fala.trechos:
        texto = tr.texto.strip()
        if not texto:
            continue
        partes = montagem.quebrar_legenda(texto)
        dur = max(0.4, tr.fim - tr.inicio)
        total = sum(len(p) for p in partes) or 1
        t = deslocamento + tr.inicio
        for p in partes:
            fatia = dur * len(p) / total
            legendas.append(montagem.Legenda(inicio=t, fim=t + fatia, texto=p))
            t += fatia
    return legendas
