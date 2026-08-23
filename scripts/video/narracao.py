"""
Narração em pt-BR com edge-tts (vozes neurais da Microsoft).

Para cada cena o módulo gera um MP3 em ``_cache/audio/`` e mede a **duração
real** do arquivo — é essa duração, e só ela, que define quantos frames a cena
vai ter. Nenhuma duração é fixada no roteiro.

Junto com o áudio, o edge-tts devolve *boundaries* (limites de sentença) com
tempos precisos. Eles viram as entradas do ``.srt``, então a legenda bate
exatamente com o que foi falado.

Cache: o MP3 é indexado por ``sha256(texto + voz + rate)``. Reescrever uma
frase regera só aquela cena; trocar a voz regera tudo. As chamadas vão pela
rede e são o passo mais lento do gerador, então o cache importa muito.

Sem internet: o módulo falha com uma mensagem clara e oferece
``--tts-offline``, que usa o ``System.Speech.Synthesis.SpeechSynthesizer`` do
Windows via PowerShell. A qualidade é bem inferior (voz concatenativa, prosódia
pobre), mas não depende de rede.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import montagem
from roteiro import AUDIO_DIR, Cena

VOZ_PADRAO = "pt-BR-AntonioNeural"
VOZES_SUGERIDAS = ("pt-BR-AntonioNeural", "pt-BR-FranciscaNeural")

# 100 nanossegundos: unidade dos offsets devolvidos pelo serviço.
TICKS_POR_SEGUNDO = 10_000_000


@dataclass
class Trecho:
    """Uma sentença falada, com início e fim relativos ao começo da cena."""

    inicio: float
    fim: float
    texto: str


@dataclass
class Fala:
    """O áudio de uma cena, já medido."""

    cena_id: str
    caminho: Path
    duracao: float
    trechos: list[Trecho]


class SemInternet(RuntimeError):
    """Levantada quando o edge-tts não consegue falar com o serviço."""


def _hash(texto: str, voz: str, rate: str) -> str:
    bruto = f"{voz}||{rate}||{texto}".encode("utf-8")
    return hashlib.sha256(bruto).hexdigest()[:16]


def _sidecar(cena_id: str) -> Path:
    return AUDIO_DIR / f"{cena_id}.json"


# ---------------------------------------------------------------------------
# edge-tts (online)
# ---------------------------------------------------------------------------
async def _sintetizar_edge(texto: str, voz: str, rate: str, destino: Path) -> list[dict]:
    """Baixa o áudio e os limites de sentença de uma cena."""
    import edge_tts

    comunicador = edge_tts.Communicate(texto, voz, rate=rate, boundary="SentenceBoundary")
    audio = bytearray()
    boundaries: list[dict] = []
    async for pedaco in comunicador.stream():
        if pedaco["type"] == "audio":
            audio.extend(pedaco["data"])
        elif pedaco["type"].endswith("Boundary"):
            boundaries.append(pedaco)

    if not audio:
        raise SemInternet("O serviço de TTS devolveu áudio vazio.")
    destino.write_bytes(bytes(audio))
    return boundaries


def _sintetizar_online(texto: str, voz: str, rate: str, destino: Path) -> list[Trecho]:
    try:
        boundaries = asyncio.run(_sintetizar_edge(texto, voz, rate, destino))
    except Exception as exc:  # rede, DNS, DRM, bloqueio corporativo...
        raise SemInternet(
            "Não consegui falar com o serviço de TTS da Microsoft (edge-tts).\n"
            f"  Causa: {type(exc).__name__}: {exc}\n\n"
            "  Verifique a conexão com a internet e tente de novo. Se não houver\n"
            "  rede disponível, use o TTS offline do Windows:\n"
            "      python scripts/video/gerar_video.py --tts-offline\n"
            "  (qualidade bem inferior, mas funciona sem rede)"
        ) from exc

    return [
        Trecho(
            inicio=b["offset"] / TICKS_POR_SEGUNDO,
            fim=(b["offset"] + b["duration"]) / TICKS_POR_SEGUNDO,
            texto=b["text"],
        )
        for b in boundaries
    ]


# ---------------------------------------------------------------------------
# System.Speech (offline, só Windows)
# ---------------------------------------------------------------------------
_PS_TEMPLATE = """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$texto = [System.IO.File]::ReadAllText('{texto}', [System.Text.Encoding]::UTF8)
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$ptbr = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -eq 'pt-BR' }}
if ($ptbr) {{ $s.SelectVoice($ptbr[0].VoiceInfo.Name) }}
$s.Rate = 1
$s.SetOutputToWaveFile('{wav}')
$s.Speak($texto)
$s.Dispose()
"""


def _sintetizar_offline(texto: str, destino_wav: Path) -> list[Trecho]:
    """Fallback sem rede: voz SAPI do Windows. Não devolve boundaries."""
    if sys.platform != "win32":
        raise SystemExit(
            "O TTS offline usa System.Speech (PowerShell) e só existe no Windows."
        )
    arquivo_texto = destino_wav.with_suffix(".txt")
    arquivo_texto.write_text(texto, encoding="utf-8")
    script = _PS_TEMPLATE.format(
        texto=str(arquivo_texto).replace("'", "''"),
        wav=str(destino_wav).replace("'", "''"),
    )
    arquivo_ps = destino_wav.with_suffix(".ps1")
    arquivo_ps.write_text(script, encoding="utf-8")
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-File", str(arquivo_ps)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    arquivo_ps.unlink(missing_ok=True)
    arquivo_texto.unlink(missing_ok=True)
    if proc.returncode != 0 or not destino_wav.exists():
        raise SystemExit(f"TTS offline falhou:\n{proc.stderr}")

    # Sem boundaries: divide o texto por sentença e distribui o tempo
    # proporcionalmente ao número de caracteres. É aproximado, mas suficiente.
    with wave.open(str(destino_wav), "rb") as w:
        duracao = w.getnframes() / float(w.getframerate())
    return _distribuir_por_caractere(texto, duracao)


def _distribuir_por_caractere(texto: str, duracao: float) -> list[Trecho]:
    """Reparte a duração entre as sentenças conforme o tamanho de cada uma."""
    import re

    sentencas = [s.strip() for s in re.split(r"(?<=[.!?])\s+", texto) if s.strip()]
    if not sentencas:
        return [Trecho(0.0, duracao, texto)]
    total = sum(len(s) for s in sentencas)
    trechos: list[Trecho] = []
    t = 0.0
    for s in sentencas:
        dt = duracao * len(s) / total
        trechos.append(Trecho(t, t + dt, s))
        t += dt
    return trechos


# ---------------------------------------------------------------------------
# API do módulo
# ---------------------------------------------------------------------------
def gerar_fala(
    cena: Cena,
    voz: str = VOZ_PADRAO,
    rate: str = "+0%",
    offline: bool = False,
    forcar: bool = False,
) -> Fala:
    """Gera (ou reaproveita do cache) o áudio narrado de uma cena."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    assinatura = _hash(cena.narracao, "sapi" if offline else voz, rate)
    extensao = ".wav" if offline else ".mp3"
    destino = AUDIO_DIR / f"{cena.id}{extensao}"
    sidecar = _sidecar(cena.id)

    if not forcar and destino.exists() and sidecar.exists():
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            if meta.get("hash") == assinatura:
                return Fala(
                    cena_id=cena.id,
                    caminho=destino,
                    duracao=float(meta["duracao"]),
                    trechos=[Trecho(**t) for t in meta["trechos"]],
                )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass  # cache corrompido: regera

    if offline:
        trechos = _sintetizar_offline(cena.narracao, destino)
    else:
        trechos = _sintetizar_online(cena.narracao, voz, rate, destino)

    duracao = montagem.duracao_audio(destino)
    # Os boundaries às vezes ultrapassam levemente o fim do arquivo; apara.
    for t in trechos:
        t.fim = min(t.fim, duracao)

    sidecar.write_text(
        json.dumps(
            {
                "hash": assinatura,
                "voz": "sapi" if offline else voz,
                "duracao": duracao,
                "trechos": [t.__dict__ for t in trechos],
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return Fala(cena_id=cena.id, caminho=destino, duracao=duracao, trechos=trechos)


def legendas_da_cena(fala: Fala, deslocamento: float) -> list[montagem.Legenda]:
    """Converte os trechos de uma cena em entradas de legenda do vídeo todo."""
    legendas: list[montagem.Legenda] = []
    for trecho in fala.trechos:
        texto = trecho.texto.strip()
        if not texto:
            continue
        partes = montagem.quebrar_legenda(texto)
        duracao = max(0.4, trecho.fim - trecho.inicio)
        # Uma sentença longa vira várias legendas. O tempo é repartido em
        # proporção ao tamanho de cada pedaço — dividir igualmente deixaria um
        # resto de duas palavras parado na tela pelo mesmo tempo que uma linha
        # cheia.
        total_chars = sum(len(p) for p in partes) or 1
        t = deslocamento + trecho.inicio
        for parte in partes:
            fatia = duracao * len(parte) / total_chars
            legendas.append(
                montagem.Legenda(inicio=t, fim=t + fatia, texto=parte)
            )
            t += fatia
    return legendas


def listar_vozes_ptbr() -> list[str]:  # pragma: no cover - utilitário
    """Lista as vozes pt-BR disponíveis no serviço (precisa de rede)."""
    import edge_tts

    async def _go() -> list[str]:
        vozes = await edge_tts.list_voices()
        return sorted(v["ShortName"] for v in vozes if v["Locale"].startswith("pt-BR"))

    return asyncio.run(_go())


if __name__ == "__main__":  # pragma: no cover
    for nome in listar_vozes_ptbr():
        print(nome)
