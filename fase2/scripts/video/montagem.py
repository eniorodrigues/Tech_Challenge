"""
Montagem final com ffmpeg.

O ffmpeg **não está no PATH desta máquina** e instalar exigiria winget/admin.
Por isso o binário vem do pacote ``imageio-ffmpeg``
(:func:`imageio_ffmpeg.get_ffmpeg_exe`), que traz um ffmpeg estático dentro do
próprio venv. Nada de dependência externa.

Estratégia de montagem, em duas fases:

1. **Um clipe MP4 por cena.** Cenas estáticas usam ``-loop 1`` sobre um único
   PNG (rápido e nítido); a cena de terminal recebe os frames RGB crus pelo
   ``stdin`` do ffmpeg, sem escrever milhares de PNGs no disco.
2. **Concatenação** de todos os clipes com o *concat demuxer* e ``-c copy``.
   Como todo clipe sai com exatamente os mesmos parâmetros de codec, a
   concatenação é instantânea e sem recompressão.

As transições entre blocos são resolvidas dentro da fase 1: a primeira cena de
cada bloco ganha ``fade in`` e a última ganha ``fade out``, ambos de 0,3 s,
posicionados sobre a pequena pausa de silêncio no fim de cada cena. Isso dá o
efeito de transição sem precisar de ``xfade`` nem de re-encodar o vídeo todo.
"""

from __future__ import annotations

import functools
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from PIL import Image

from roteiro import ALTURA, CLIPES_DIR, FPS, LARGURA

DURACAO_FADE = 0.30
CRF = 20
PRESET = "medium"
BITRATE_AUDIO = "192k"


@functools.lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    """Caminho do ffmpeg embutido no venv (via imageio-ffmpeg)."""
    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "imageio-ffmpeg não está instalado. Rode:\n"
            "  .venv\\Scripts\\python.exe -m pip install imageio-ffmpeg"
        ) from exc
    caminho = imageio_ffmpeg.get_ffmpeg_exe()
    if not Path(caminho).exists():  # pragma: no cover
        raise SystemExit(f"ffmpeg não encontrado em {caminho}")
    return caminho


def _rodar(args: Sequence[str], entrada: bytes | None = None) -> None:
    """Executa o ffmpeg escondendo o ruído, mas mostrando o erro se falhar."""
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args],
        input=entrada,
        capture_output=True,
    )
    if proc.returncode != 0:
        erro = proc.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"ffmpeg falhou ({proc.returncode}):\n{erro}")


_RE_TEMPO = re.compile(r"time=(\d+):(\d{2}):(\d{2}\.\d+)")


def duracao_audio(caminho: Path) -> float:
    """Duração real de um arquivo de áudio, em segundos.

    Decodifica o arquivo inteiro para ``null`` e lê o último ``time=`` do log.
    É mais confiável do que estimar pela taxa de bits do cabeçalho MP3 e não
    exige ffprobe nem mutagen.
    """
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(caminho), "-f", "null", "-"],
        capture_output=True,
    )
    log = proc.stderr.decode("utf-8", "replace")
    tempos = _RE_TEMPO.findall(log)
    if not tempos:
        raise RuntimeError(f"Não consegui medir a duração de {caminho}:\n{log[-800:]}")
    h, m, s = tempos[-1]
    return int(h) * 3600 + int(m) * 60 + float(s)


# ---------------------------------------------------------------------------
# Clipes
# ---------------------------------------------------------------------------
@dataclass
class Fade:
    """Quais bordas do clipe recebem transição."""

    entrada: bool = False
    saida: bool = False

    def filtro(self, duracao: float) -> str:
        partes = []
        if self.entrada:
            partes.append(f"fade=t=in:st=0:d={DURACAO_FADE:.2f}")
        if self.saida:
            inicio = max(0.0, duracao - DURACAO_FADE)
            partes.append(f"fade=t=out:st={inicio:.3f}:d={DURACAO_FADE:.2f}")
        return ",".join(partes)


def _vf(fade: Fade, duracao: float) -> str:
    """Cadeia de filtros de vídeo: transições + pixel format do YouTube."""
    partes = [f"fps={FPS}", f"scale={LARGURA}:{ALTURA}"]
    f = fade.filtro(duracao)
    if f:
        partes.append(f)
    partes.append("format=yuv420p")
    return ",".join(partes)


_ARGS_SAIDA = (
    "-c:v", "libx264",
    "-preset", PRESET,
    "-crf", str(CRF),
    "-profile:v", "high",
    "-level", "4.1",
    "-g", str(FPS * 2),
    "-c:a", "aac",
    "-b:a", BITRATE_AUDIO,
    "-ar", "48000",
    "-ac", "2",
    "-movflags", "+faststart",
)


def clipe_estatico(
    imagem: Image.Image, audio: Path, duracao: float, saida: Path, fade: Fade,
) -> Path:
    """Clipe de uma cena estática: um PNG segurado por ``-loop 1``."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    temp_png = saida.with_suffix(".png")
    imagem.save(temp_png, format="PNG", optimize=False, compress_level=1)
    try:
        _rodar([
            "-loop", "1", "-framerate", str(FPS), "-i", str(temp_png),
            "-i", str(audio),
            "-t", f"{duracao:.3f}",
            "-vf", _vf(fade, duracao),
            # apad completa o áudio com silêncio até o -t (a pausa entre cenas).
            "-af", "apad",
            "-tune", "stillimage",
            *_ARGS_SAIDA,
            str(saida),
        ])
    finally:
        temp_png.unlink(missing_ok=True)
    return saida


def clipe_animado(
    frames: Iterable[Image.Image], n_frames: int, audio: Path, duracao: float,
    saida: Path, fade: Fade,
) -> Path:
    """Clipe animado: frames RGB crus entregues pelo stdin do ffmpeg.

    Nenhum PNG intermediário toca o disco — o gerador de frames alimenta o
    pipe quadro a quadro.
    """
    saida.parent.mkdir(parents=True, exist_ok=True)
    args = [
        ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{LARGURA}x{ALTURA}", "-framerate", str(FPS),
        "-i", "pipe:0",
        "-i", str(audio),
        "-t", f"{duracao:.3f}",
        "-vf", _vf(fade, duracao),
        "-af", "apad",
        *_ARGS_SAIDA,
        str(saida),
    ]
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    enviados = 0
    try:
        for frame in frames:
            if enviados >= n_frames:
                break
            proc.stdin.write(frame.tobytes())
            enviados += 1
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falhou ({proc.returncode}) no clipe {saida.name}:\n"
            f"{stderr.decode('utf-8', 'replace')}"
        )
    return saida


def concatenar(clipes: Sequence[Path], saida: Path) -> Path:
    """Junta os clipes sem recompressão (concat demuxer + ``-c copy``)."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    lista = CLIPES_DIR / "lista_concat.txt"
    lista.parent.mkdir(parents=True, exist_ok=True)
    lista.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in clipes) + "\n",
        encoding="utf-8",
    )
    _rodar([
        "-f", "concat", "-safe", "0", "-i", str(lista),
        "-c", "copy", "-movflags", "+faststart",
        str(saida),
    ])
    return saida


def extrair_frame(video: Path, instante: float, saida: Path) -> Path:
    """Extrai um frame do MP4 final — usado para conferir o resultado."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    _rodar([
        "-ss", f"{instante:.3f}", "-i", str(video),
        "-frames:v", "1", "-q:v", "2", str(saida),
    ])
    return saida


def limpar_clipes() -> None:
    """Remove os clipes intermediários (o MP4 final já os contém)."""
    if not CLIPES_DIR.exists():
        return
    for arquivo in CLIPES_DIR.glob("*"):
        try:
            arquivo.unlink()
        except OSError:  # pragma: no cover
            pass


# ---------------------------------------------------------------------------
# Legendas
# ---------------------------------------------------------------------------
@dataclass
class Legenda:
    """Uma entrada de legenda já posicionada na linha do tempo do vídeo."""

    inicio: float
    fim: float
    texto: str


def _tempo_srt(segundos: float) -> str:
    segundos = max(0.0, segundos)
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    ms = int(round((segundos - int(segundos)) * 1000))
    if ms == 1000:  # arredondamento para cima estourando o segundo
        ms, s = 0, s + 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _normalizar(legendas: Sequence[Legenda]) -> list[Legenda]:
    """Ordena e resolve sobreposições entre legendas vizinhas.

    Os limites de sentença do TTS às vezes se sobrepõem em alguns
    centésimos; o YouTube aceita, mas alguns players engasgam. Aqui cada
    legenda é aparada para terminar antes do início da seguinte, respeitando
    uma duração mínima legível.
    """
    ordenadas = sorted(
        (l for l in legendas if l.texto.strip()), key=lambda l: l.inicio
    )
    for atual, proxima in zip(ordenadas, ordenadas[1:]):
        atual.fim = min(atual.fim, proxima.inicio - 0.02)
        atual.fim = max(atual.fim, atual.inicio + 0.4)
    return ordenadas


def escrever_srt(legendas: Sequence[Legenda], saida: Path) -> Path:
    """Grava o arquivo ``.srt`` (UTF-8, como o YouTube espera)."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    blocos = []
    for i, leg in enumerate(_normalizar(legendas), start=1):
        blocos.append(
            f"{i}\n{_tempo_srt(leg.inicio)} --> {_tempo_srt(leg.fim)}\n{leg.texto}\n"
        )
    saida.write_text("\n".join(blocos), encoding="utf-8")
    return saida


def quebrar_legenda(texto: str, largura: int = 46, max_linhas: int = 2) -> list[str]:
    """Quebra o texto de uma legenda em no máximo ``max_linhas`` linhas.

    Devolve uma lista de *legendas* (não de linhas): se o texto não couber em
    ``max_linhas``, ele é dividido em várias entradas consecutivas.
    """
    palavras = texto.split()
    if not palavras:
        return [""]
    linhas: list[str] = []
    atual = ""
    for palavra in palavras:
        tentativa = f"{atual} {palavra}".strip()
        if len(tentativa) <= largura or not atual:
            atual = tentativa
        else:
            linhas.append(atual)
            atual = palavra
    linhas.append(atual)

    return [
        "\n".join(linhas[i:i + max_linhas])
        for i in range(0, len(linhas), max_linhas)
    ]


if __name__ == "__main__":  # pragma: no cover
    print("ffmpeg:", ffmpeg_exe())
    if len(sys.argv) > 1:
        print("duração:", duracao_audio(Path(sys.argv[1])), "s")
