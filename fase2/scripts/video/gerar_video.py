"""
Gerador do vídeo de demonstração — Tech Challenge Fase 2 (MedRoute).

    python scripts/video/gerar_video.py                  # vídeo completo
    python scripts/video/gerar_video.py --previa         # 1 PNG por cena (sem áudio/vídeo)
    python scripts/video/gerar_video.py --so-audio       # só narração + .srt
    python scripts/video/gerar_video.py --blocos 6,9     # só alguns blocos
    python scripts/video/gerar_video.py --recapturar     # roda o sistema de novo

Fluxo:

    saída real do terminal + telas reais + quadros da evolução do GA
      -> narração (edge-tts) -> duração medida -> quadros -> clipes -> MP4 + SRT

A duração de cada cena vem do áudio narrado. No fim o script imprime a
duração de cada bloco e avisa se o total passar dos 15 minutos do enunciado.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import captura  # noqa: E402
import montagem  # noqa: E402
import narracao  # noqa: E402
import visuais  # noqa: E402
from roteiro import (BLOCOS, CLIPES_DIR, FPS, LIMITE_SEGUNDOS, NOME_SAIDA, PREVIA_DIR,  # noqa: E402
                     SAIDA_DIR, Bloco, Cena, Visual, contar_palavras, filtrar_blocos)

PAUSA_CENA = 0.30
PAUSA_BLOCO = 0.75


@dataclass
class CenaPronta:
    bloco: Bloco
    cena: Cena
    fala: narracao.Fala
    duracao: float
    clipe: Path | None = None


def _mmss(s: float) -> str:
    return f"{int(s // 60)}:{s % 60:04.1f}"


def _etiqueta(b: Bloco) -> str:
    return f"{b.numero} · {b.titulo}"


def preparar_insumos(blocos, recapturar: bool, recapturar_telas: bool) -> None:
    visuais_usados = {c.visual for b in blocos for c in b.cenas}
    if Visual.TERMINAL in visuais_usados:
        ids = sorted({c.asset for b in blocos for c in b.cenas if c.visual is Visual.TERMINAL})
        captura.capturar_tudo(recapturar, ids)
    if Visual.TELA in visuais_usados:
        import telas

        telas.capturar_telas(recapturar_telas)
    if Visual.EVOLUCAO in visuais_usados:
        import evolucao

        evolucao.gerar_quadros(recapturar)


def modo_previa(blocos) -> int:
    shutil.rmtree(PREVIA_DIR, ignore_errors=True)
    PREVIA_DIR.mkdir(parents=True, exist_ok=True)
    for b in blocos:
        print(f"\nBloco {_etiqueta(b)}")
        for c in b.cenas:
            img = visuais.render_primeiro_frame(c, _etiqueta(b))
            img.save(PREVIA_DIR / f"{c.id}.png")
            print(f"  {c.visual.value:9s} {c.id}")
    print(f"\nprévia em {PREVIA_DIR}")
    return 0


def relatorio(prontas: list[CenaPronta], total: float) -> None:
    print("\n" + "=" * 72 + "\nDURAÇÃO POR BLOCO\n" + "=" * 72)
    por_bloco: dict[int, float] = {}
    for p in prontas:
        por_bloco[p.bloco.numero] = por_bloco.get(p.bloco.numero, 0.0) + p.duracao
    inicio = 0.0
    for b in {p.bloco.numero: p.bloco for p in prontas}.values():
        d = por_bloco[b.numero]
        print(f"  {b.numero:2d}. {b.titulo:40s} {_mmss(d):>7s}  (começa em {_mmss(inicio)})")
        inicio += d
    print("-" * 72 + f"\n  TOTAL: {_mmss(total)} ({total:.1f} s)")
    if total > LIMITE_SEGUNDOS:
        print(f"  *** ATENÇÃO: {_mmss(total - LIMITE_SEGUNDOS)} acima do limite de 15 min ***")
    else:
        print(f"  Dentro do limite de 15 min ({_mmss(LIMITE_SEGUNDOS - total)} de folga).")


def gerar(a: argparse.Namespace) -> int:
    blocos = filtrar_blocos(a.blocos)
    parcial = blocos != BLOCOS
    print("=" * 72 + "\nGERADOR DE VÍDEO — Tech Challenge Fase 2 (MedRoute)\n" + "=" * 72)
    print(f"Blocos: {len(blocos)} · cenas: {sum(len(b.cenas) for b in blocos)} · "
          f"palavras: {contar_palavras(blocos)} · voz: {a.voz} · 1920x1080 @ {FPS} fps")

    print("\n[1/4] Insumos reais (terminal, telas, evolução do GA)")
    preparar_insumos(blocos, a.recapturar, a.recapturar_telas)
    if a.previa:
        return modo_previa(blocos)

    print("\n[2/4] Narração (edge-tts) e duração de cada cena")
    prontas: list[CenaPronta] = []
    try:
        for b in blocos:
            for i, c in enumerate(b.cenas):
                if not c.narracao.strip():
                    raise SystemExit(f"cena {c.id} sem narração (preencha narracao_texto.py)")
                fala = narracao.gerar_fala(c, voz=a.voz, rate=a.rate, forcar=a.refazer_audio)
                pausa = PAUSA_BLOCO if i == len(b.cenas) - 1 else PAUSA_CENA
                prontas.append(CenaPronta(b, c, fala, fala.duracao + pausa))
                print(f"  {c.id:24s} {c.visual.value:9s} {fala.duracao:6.2f}s")
    except narracao.SemInternet as exc:
        print(f"\nERRO: {exc}", file=sys.stderr)
        return 2
    total = sum(p.duracao for p in prontas)

    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    legendas: list[montagem.Legenda] = []
    desloc = 0.0
    for p in prontas:
        legendas.extend(narracao.legendas_da_cena(p.fala, desloc))
        desloc += p.duracao
    sufixo = "_parcial" if parcial else ""
    srt = SAIDA_DIR / f"{NOME_SAIDA}{sufixo}.srt"
    montagem.escrever_srt(legendas, srt)
    print(f"\n[3/4] Legendas: {len(legendas)} entradas -> {srt.name}")
    if a.so_audio:
        relatorio(prontas, total)
        return 0

    print(f"\n[4/4] Renderizando {len(prontas)} clipes")
    CLIPES_DIR.mkdir(parents=True, exist_ok=True)
    montagem.limpar_clipes()
    t0 = time.perf_counter()
    acumulado = 0.0
    for k, p in enumerate(prontas):
        etq = _etiqueta(p.bloco)
        primeira = k == 0 or prontas[k - 1].bloco is not p.bloco
        ultima = k == len(prontas) - 1 or prontas[k + 1].bloco is not p.bloco
        fade = montagem.Fade(entrada=primeira, saida=ultima)
        destino = CLIPES_DIR / f"{k:03d}_{p.cena.id}.mp4"
        t1 = time.perf_counter()
        if visuais.eh_estatica(p.cena):
            montagem.clipe_estatico(visuais.render_estatico(p.cena, etq), p.fala.caminho,
                                    p.duracao, destino, fade)
        else:
            n = int(round(p.duracao * FPS))
            montagem.clipe_animado(visuais.frames(p.cena, etq, n, FPS), n, p.fala.caminho,
                                   p.duracao, destino, fade)
        p.clipe = destino
        acumulado += p.duracao
        print(f"  [{k + 1:2d}/{len(prontas)}] {p.cena.id:24s} {p.duracao:5.1f}s "
              f"(até {_mmss(acumulado)}) enc {time.perf_counter() - t1:4.1f}s", flush=True)
    print(f"  codificação: {time.perf_counter() - t0:.0f} s")

    mp4 = SAIDA_DIR / f"{NOME_SAIDA}{sufixo}.mp4"
    montagem.concatenar([p.clipe for p in prontas if p.clipe], mp4)
    if not a.manter_clipes:
        montagem.limpar_clipes()
    relatorio(prontas, total)
    real = montagem.duracao_audio(mp4)
    print("\n" + "=" * 72 + "\nSAÍDA\n" + "=" * 72)
    print(f"  Vídeo   : {mp4}\n  Duração : {_mmss(real)}\n  Tamanho : "
          f"{mp4.stat().st_size / 1024 / 1024:.1f} MB\n  Legenda : {srt}")
    return 0


def _blocos(valor: str | None):
    return [int(x) for x in valor.split(",")] if valor else None


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voz", default=narracao.VOZ_PADRAO)
    ap.add_argument("--rate", default="+4%", help="velocidade da fala (edge-tts)")
    ap.add_argument("--recapturar", action="store_true", help="roda o sistema de novo")
    ap.add_argument("--recapturar-telas", action="store_true", help="refaz as capturas de tela")
    ap.add_argument("--so-audio", action="store_true")
    ap.add_argument("--previa", action="store_true")
    ap.add_argument("--blocos", type=_blocos)
    ap.add_argument("--refazer-audio", action="store_true")
    ap.add_argument("--manter-clipes", action="store_true")
    return gerar(ap.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
