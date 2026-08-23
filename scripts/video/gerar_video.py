"""
Gerador do vídeo de demonstração — ponto de entrada único.

    python scripts/video/gerar_video.py
    python scripts/video/gerar_video.py --voz pt-BR-FranciscaNeural
    python scripts/video/gerar_video.py --recapturar     # re-roda main.py/pytest
    python scripts/video/gerar_video.py --so-audio       # só narração, p/ revisar
    python scripts/video/gerar_video.py --blocos 6,7,8   # só alguns blocos
    python scripts/video/gerar_video.py --previa         # 1 PNG por cena, sem vídeo

Fluxo completo:

    capturar saída real  ->  narrar (TTS)  ->  medir duração  ->  renderizar
    frames  ->  1 clipe por cena  ->  concatenar  ->  MP4 + SRT

A duração de cada cena vem da medição do MP3 narrado; nada é fixado à mão.
No fim o script imprime a duração de cada bloco, o total, e avisa (com
sugestão de corte) se passar dos 15 minutos do enunciado.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Permite rodar como script solto (python scripts/video/gerar_video.py) sem
# precisar de PYTHONPATH nem de -m.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import captura            # noqa: E402
import montagem           # noqa: E402
import narracao           # noqa: E402
import visuais            # noqa: E402
from roteiro import (     # noqa: E402
    BLOCOS,
    CLIPES_DIR,
    FPS,
    LIMITE_SEGUNDOS,
    NOME_SAIDA,
    PREVIA_DIR,
    SAIDA_DIR,
    Bloco,
    Cena,
    contar_palavras,
    filtrar_blocos,
)

# Silêncio no fim de cada cena: dá respiro à narração e serve de espaço para
# o fade das transições de bloco cair sobre o silêncio, não sobre a fala.
PAUSA_ENTRE_CENAS = 0.25
PAUSA_ENTRE_BLOCOS = 0.70


@dataclass
class CenaPronta:
    """Uma cena já narrada, medida e (talvez) codificada."""

    bloco: Bloco
    cena: Cena
    fala: narracao.Fala
    duracao_total: float          # áudio + pausa
    clipe: Path | None = None


def _mmss(segundos: float) -> str:
    return f"{int(segundos // 60):d}:{segundos % 60:04.1f}"


def _etiqueta(bloco: Bloco) -> str:
    return f"Bloco {bloco.numero} — {bloco.titulo}"


# ---------------------------------------------------------------------------
# Modos auxiliares
# ---------------------------------------------------------------------------
def modo_previa(blocos: tuple[Bloco, ...]) -> int:
    """Renderiza um PNG por cena, sem áudio e sem vídeo.

    É o jeito barato de conferir tipografia, cortes de terminal e destaques de
    código antes de gastar tempo com TTS e encoding.
    """
    if PREVIA_DIR.exists():
        shutil.rmtree(PREVIA_DIR, ignore_errors=True)
    PREVIA_DIR.mkdir(parents=True, exist_ok=True)

    n = 0
    for bloco in blocos:
        print(f"\n{_etiqueta(bloco)}")
        for cena in bloco.cenas:
            imagem = visuais.render_primeiro_frame(cena, _etiqueta(bloco))
            destino = PREVIA_DIR / f"{cena.id}.png"
            imagem.save(destino)
            n += 1
            print(f"  {cena.visual.value:8s}  {destino.name}")
    print(f"\n{n} frames de prévia em: {PREVIA_DIR}")
    return 0


def _resumo_blocos(prontas: list[CenaPronta]) -> dict[int, float]:
    por_bloco: dict[int, float] = {}
    for p in prontas:
        por_bloco[p.bloco.numero] = por_bloco.get(p.bloco.numero, 0.0) + p.duracao_total
    return por_bloco


def _relatorio_final(prontas: list[CenaPronta], total: float) -> None:
    print("\n" + "=" * 72)
    print("DURAÇÃO POR BLOCO")
    print("=" * 72)
    por_bloco = _resumo_blocos(prontas)
    acumulado = 0.0
    vistos: set[int] = set()
    for p in prontas:
        if p.bloco.numero in vistos:
            continue
        vistos.add(p.bloco.numero)
        d = por_bloco[p.bloco.numero]
        inicio = acumulado
        acumulado += d
        print(f"  Bloco {p.bloco.numero:2d}  {p.bloco.titulo:42s} "
              f"{_mmss(d):>7s}   (começa em {_mmss(inicio)})")

    print("-" * 72)
    print(f"  TOTAL: {_mmss(total)}  ({total:.1f} s)")

    if total > LIMITE_SEGUNDOS:
        excesso = total - LIMITE_SEGUNDOS
        print(f"\n  *** ATENÇÃO: passou do limite de 15 min por {_mmss(excesso)}. ***")
        # O próprio ROTEIRO_VIDEO.md diz quais blocos podem encolher primeiro;
        # depois sugerimos os mais longos que não são os de maior peso na nota.
        prioridade_de_corte = [3, 10, 1, 6, 4]
        sugestoes: list[str] = []
        economia = 0.0
        for numero in prioridade_de_corte:
            if numero in por_bloco and economia < excesso:
                economia += por_bloco[numero]
                sugestoes.append(f"bloco {numero} ({_mmss(por_bloco[numero])})")
        print("  Corte, nesta ordem: " + ", ".join(sugestoes))
        print("  (os blocos 7, 8 e 11 são os que mais pesam na avaliação — "
              "não corte esses)")
    else:
        folga = LIMITE_SEGUNDOS - total
        print(f"  Dentro do limite de 15 min, com {_mmss(folga)} de folga.")


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
def gerar(args: argparse.Namespace) -> int:
    blocos = filtrar_blocos(args.blocos)
    parcial = blocos != BLOCOS

    print("=" * 72)
    print("GERADOR DE VÍDEO — Tech Challenge Fase 1")
    print("=" * 72)
    n_cenas = sum(len(b.cenas) for b in blocos)
    print(f"Blocos: {len(blocos)}  ·  Cenas: {n_cenas}  ·  "
          f"Palavras narradas: {contar_palavras(blocos)}")
    print(f"Voz: {'SAPI offline (Windows)' if args.tts_offline else args.voz}"
          f"  ·  Formato: 1920x1080 @ {FPS} fps")
    if parcial:
        print(f"MODO PARCIAL: apenas os blocos "
              f"{', '.join(str(b.numero) for b in blocos)}")

    # ------------------------------------------------------------ 1. Captura
    print("\n[1/4] Capturando a saída real do sistema")
    precisa_terminal = any(
        c.visual.value == "terminal" for b in blocos for c in b.cenas
    )
    if precisa_terminal:
        captura.capturar_tudo(
            recapturar=args.recapturar,
            incluir_vision=not args.pular_vision,
        )
    else:
        print("  (nenhuma cena de terminal nos blocos selecionados — pulando)")

    # ------------------------------------------------------------ 2. Narração
    print("\n[2/4] Gerando a narração (TTS) e medindo a duração de cada cena")
    prontas: list[CenaPronta] = []
    try:
        for bloco in blocos:
            print(f"\n  {_etiqueta(bloco)}")
            for i, cena in enumerate(bloco.cenas):
                t0 = time.perf_counter()
                fala = narracao.gerar_fala(
                    cena,
                    voz=args.voz,
                    rate=args.rate,
                    offline=args.tts_offline,
                    forcar=args.refazer_audio,
                )
                ultima = i == len(bloco.cenas) - 1
                pausa = PAUSA_ENTRE_BLOCOS if ultima else PAUSA_ENTRE_CENAS
                prontas.append(
                    CenaPronta(bloco, cena, fala, fala.duracao + pausa)
                )
                dt = time.perf_counter() - t0
                marca = "cache" if dt < 0.35 else f"{dt:.1f}s"
                print(f"    {cena.id:28s} {cena.visual.value:8s} "
                      f"{fala.duracao:6.2f}s  [{marca}]")
    except narracao.SemInternet as exc:
        print(f"\nERRO: {exc}", file=sys.stderr)
        return 2

    total = sum(p.duracao_total for p in prontas)

    # ------------------------------------------------------------ 3. Legendas
    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    legendas: list[montagem.Legenda] = []
    deslocamento = 0.0
    for p in prontas:
        legendas.extend(narracao.legendas_da_cena(p.fala, deslocamento))
        deslocamento += p.duracao_total

    sufixo = "_parcial" if parcial else ""
    caminho_srt = SAIDA_DIR / f"{NOME_SAIDA}{sufixo}.srt"
    montagem.escrever_srt(legendas, caminho_srt)
    print(f"\n[3/4] Legendas: {len(legendas)} entradas -> {caminho_srt}")

    if args.so_audio:
        print("\n--so-audio: parando antes do vídeo.")
        print(f"  Áudios em: {prontas[0].fala.caminho.parent}")
        _relatorio_final(prontas, total)
        return 0

    # -------------------------------------------------------- 4. Renderização
    print(f"\n[4/4] Renderizando e codificando {len(prontas)} clipes")
    CLIPES_DIR.mkdir(parents=True, exist_ok=True)
    montagem.limpar_clipes()

    t_inicio = time.perf_counter()
    acumulado = 0.0
    for indice, p in enumerate(prontas):
        etiqueta = _etiqueta(p.bloco)
        primeira_do_bloco = indice == 0 or prontas[indice - 1].bloco is not p.bloco
        ultima_do_bloco = (
            indice == len(prontas) - 1 or prontas[indice + 1].bloco is not p.bloco
        )
        fade = montagem.Fade(entrada=primeira_do_bloco, saida=ultima_do_bloco)
        destino = CLIPES_DIR / f"{indice:03d}_{p.cena.id}.mp4"

        t0 = time.perf_counter()
        if visuais.eh_estatica(p.cena):
            imagem = visuais.render_estatico(p.cena, etiqueta)
            montagem.clipe_estatico(
                imagem, p.fala.caminho, p.duracao_total, destino, fade
            )
        else:
            n_frames = int(round(p.duracao_total * FPS))
            frames = visuais.frames_terminal(p.cena, etiqueta, n_frames, FPS)
            montagem.clipe_animado(
                frames, n_frames, p.fala.caminho, p.duracao_total, destino, fade
            )
        p.clipe = destino
        acumulado += p.duracao_total
        print(f"  [{indice + 1:2d}/{len(prontas)}] B{p.bloco.numero:02d} "
              f"{p.cena.id:28s} {p.duracao_total:5.2f}s  "
              f"(vídeo em {_mmss(acumulado)})  enc {time.perf_counter() - t0:4.1f}s")

    print(f"\n  Codificação: {time.perf_counter() - t_inicio:.1f}s")

    # ---------------------------------------------------------- Concatenação
    caminho_mp4 = SAIDA_DIR / f"{NOME_SAIDA}{sufixo}.mp4"
    print(f"  Concatenando -> {caminho_mp4.name}")
    montagem.concatenar([p.clipe for p in prontas if p.clipe], caminho_mp4)

    if not args.manter_clipes:
        montagem.limpar_clipes()

    # ------------------------------------------------------------- Relatório
    real = montagem.duracao_audio(caminho_mp4)
    tamanho_mb = caminho_mp4.stat().st_size / (1024 * 1024)

    _relatorio_final(prontas, total)
    print("\n" + "=" * 72)
    print("SAÍDA")
    print("=" * 72)
    print(f"  Vídeo   : {caminho_mp4}")
    print(f"  Duração : {_mmss(real)}  ({real:.1f} s medidos no MP4)")
    print(f"  Tamanho : {tamanho_mb:.1f} MB")
    print(f"  Legenda : {caminho_srt}")
    if parcial:
        print("\n  Este é um render PARCIAL (--blocos). Rode sem --blocos "
              "para o vídeo completo.")
    return 0


def _parse_blocos(valor: str | None) -> list[int] | None:
    if not valor:
        return None
    try:
        return [int(x) for x in valor.replace(" ", "").split(",") if x]
    except ValueError:
        raise argparse.ArgumentTypeError(
            "--blocos espera números separados por vírgula, ex.: --blocos 6,7,8"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gerar_video.py",
        description="Gera o vídeo de demonstração (MP4 1080p + SRT) do Tech Challenge Fase 1.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--voz", default=narracao.VOZ_PADRAO,
        help=f"Voz do edge-tts. Sugestões: {', '.join(narracao.VOZES_SUGERIDAS)}. "
             f"Padrão: {narracao.VOZ_PADRAO}",
    )
    parser.add_argument(
        "--rate", default="+0%",
        help="Velocidade da fala, ex.: '+10%%' para acelerar. Padrão: +0%%",
    )
    parser.add_argument(
        "--recapturar", action="store_true",
        help="Re-executa main.py, pytest e main_vision.py em vez de usar o cache.",
    )
    parser.add_argument(
        "--pular-vision", action="store_true",
        help="Não roda main_vision.py (lento); usa o cache se existir.",
    )
    parser.add_argument(
        "--so-audio", action="store_true",
        help="Gera apenas a narração e o SRT, para revisar o texto antes do vídeo.",
    )
    parser.add_argument(
        "--previa", action="store_true",
        help="Gera 1 PNG por cena em _cache/previa/ e sai. Sem TTS, sem vídeo.",
    )
    parser.add_argument(
        "--blocos", type=_parse_blocos, default=None, metavar="1,2,3",
        help="Renderiza só os blocos indicados (iteração rápida).",
    )
    parser.add_argument(
        "--tts-offline", action="store_true",
        help="Usa o TTS do Windows (System.Speech) em vez do edge-tts. "
             "Funciona sem internet, com qualidade bem inferior.",
    )
    parser.add_argument(
        "--refazer-audio", action="store_true",
        help="Ignora o cache de áudio e regera todas as narrações.",
    )
    parser.add_argument(
        "--manter-clipes", action="store_true",
        help="Não apaga os clipes por cena em _cache/clipes/ (útil para depurar).",
    )
    args = parser.parse_args(argv)

    if args.previa:
        return modo_previa(filtrar_blocos(args.blocos))
    return gerar(args)


if __name__ == "__main__":
    raise SystemExit(main())
