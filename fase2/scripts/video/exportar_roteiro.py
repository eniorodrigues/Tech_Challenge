"""
Exporta o roteiro (``roteiro.py`` + ``narracao_texto.py``) para ``docs/ROTEIRO_VIDEO.md``.

    python scripts/video/exportar_roteiro.py

Se os áudios já foram gerados (``_cache/audio``), inclui a duração real de
cada cena e o tempo de início no vídeo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from roteiro import AUDIO_DIR, BLOCOS, LIMITE_SEGUNDOS, PROJECT_ROOT, Visual  # noqa: E402

DESTINO = PROJECT_ROOT / "docs" / "ROTEIRO_VIDEO.md"
PAUSA_CENA, PAUSA_BLOCO = 0.30, 0.75

TELA = {
    Visual.TITULO: "cartão de título",
    Visual.FIGURA: "figura",
    Visual.TERMINAL: "terminal (saída real)",
    Visual.CODIGO: "código",
    Visual.ARVORE: "árvore do projeto",
    Visual.TELA: "captura real do sistema",
    Visual.DOCUMENTO: "texto gerado pela LLM (rolagem)",
    Visual.CHAT: "chat com a LLM",
    Visual.EVOLUCAO: "animação da evolução do GA",
}


def _duracao(cid: str) -> float | None:
    meta = AUDIO_DIR / f"{cid}.json"
    try:
        return float(json.loads(meta.read_text(encoding="utf-8"))["duracao"])
    except (OSError, KeyError, ValueError):
        return None


def _mmss(s: float) -> str:
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    linhas = ["# Roteiro do vídeo de demonstração (até 15 min)", "",
              "Gerado de `scripts/video/roteiro.py` + `narracao_texto.py` por "
              "`scripts/video/exportar_roteiro.py`. O vídeo é montado automaticamente por "
              "`python scripts/video/gerar_video.py` (narração pt-BR com edge-tts, telas e saídas "
              "reais do sistema). A narração partiu de um rascunho escrito pela LLM gratuita da "
              "OpenRouter (`docs/ROTEIRO_RASCUNHO_LLM.md`) e foi revisada.", ""]
    t = 0.0
    completo = True
    resumo = []
    for b in BLOCOS:
        inicio_bloco = t
        linhas += [f"## {b.numero}. {b.titulo}", ""]
        for i, c in enumerate(b.cenas):
            d = _duracao(c.id)
            if d is None:
                completo = False
            dur = (d or c.alvo_seg) + (PAUSA_BLOCO if i == len(b.cenas) - 1 else PAUSA_CENA)
            onde = f" — `{c.asset}`" if c.asset else ""
            linhas.append(f"**[{_mmss(t)}] {c.titulo or c.id}** · {TELA[c.visual]}{onde}"
                          + (f" · {d:.0f} s" if d else f" · ~{c.alvo_seg} s"))
            linhas.append("")
            linhas.append(f"> {c.narracao}")
            linhas.append("")
            t += dur
        resumo.append((b.numero, b.titulo, inicio_bloco, t - inicio_bloco))
    linhas += ["## Resumo de tempos", "", "| Bloco | Início | Duração |", "|---|---|---|"]
    for n, tit, ini, dur in resumo:
        linhas.append(f"| {n}. {tit} | {_mmss(ini)} | {_mmss(dur)} |")
    linhas += ["", f"**Total:** {_mmss(t)} "
               + ("(medido nos áudios)" if completo else "(estimado; gere os áudios para medir)")
               + f" — limite do enunciado: {_mmss(LIMITE_SEGUNDOS)}.", ""]
    DESTINO.write_text("\n".join(linhas), encoding="utf-8")
    print(f"{DESTINO} — total {_mmss(t)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
