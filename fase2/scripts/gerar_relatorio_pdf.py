"""
Gera o PDF entregável a partir de ``docs/RELATORIO_TECNICO.md``.

    python scripts/gerar_relatorio_pdf.py --repo <URL_DO_REPO> --video <URL_DO_VIDEO>

Conversor Markdown → PDF (reportlab) para o subconjunto usado no relatório:
títulos, parágrafos com **negrito**/*itálico*/`código`/links, listas,
citações, tabelas, blocos de código, imagens e linhas horizontais. Usa as
fontes DejaVu que vêm com o Matplotlib (cobrem acentos, setas, ≈, ₂ etc.).
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "docs" / "RELATORIO_TECNICO.md"
DESTINO = RAIZ / "Tech_Challenge_Fase2_Entregavel.pdf"

AZUL = colors.HexColor("#104281")
AZUL_CLARO = colors.HexColor("#e8f0fb")
CINZA = colors.HexColor("#52514e")
LINHA = colors.HexColor("#d6d5cf")


def _registrar_fontes() -> None:
    pasta = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for nome, arq in (("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"),
                      ("DV-I", "DejaVuSans-Oblique.ttf"), ("DV-BI", "DejaVuSans-BoldOblique.ttf"),
                      ("DVM", "DejaVuSansMono.ttf")):
        pdfmetrics.registerFont(TTFont(nome, str(pasta / arq)))
    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")


def _estilos() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="DV", fontSize=9.6, leading=13.6, textColor=colors.black,
                          alignment=TA_LEFT, spaceAfter=5)
    return {
        "p": base,
        "h1": ParagraphStyle("h1", parent=base, fontName="DV-B", fontSize=15, leading=19,
                             textColor=AZUL, spaceBefore=10, spaceAfter=7),
        "h2": ParagraphStyle("h2", parent=base, fontName="DV-B", fontSize=12, leading=16,
                             textColor=AZUL, spaceBefore=8, spaceAfter=5),
        "h3": ParagraphStyle("h3", parent=base, fontName="DV-B", fontSize=10.5, leading=14,
                             spaceBefore=6, spaceAfter=4),
        "titulo": ParagraphStyle("titulo", parent=base, fontName="DV-B", fontSize=22, leading=28,
                                 textColor=AZUL, spaceAfter=10),
        "sub": ParagraphStyle("sub", parent=base, fontSize=13, leading=18, textColor=CINZA),
        "quote": ParagraphStyle("quote", parent=base, fontName="DV-I", textColor=CINZA,
                                leftIndent=12, borderPadding=(2, 0, 2, 8)),
        "li": ParagraphStyle("li", parent=base, leftIndent=14, bulletIndent=4, spaceAfter=2.5),
        "cel": ParagraphStyle("cel", parent=base, fontSize=7.8, leading=10, spaceAfter=0),
        "celh": ParagraphStyle("celh", parent=base, fontName="DV-B", fontSize=7.8, leading=10,
                               spaceAfter=0),
        "code": ParagraphStyle("code", parent=base, fontName="DVM", fontSize=7.6, leading=10),
    }


def _inline(texto: str) -> str:
    """Markdown inline → marcação do reportlab."""
    t = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"`([^`]+)`", r'<font name="DVM">\1</font>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
               lambda m: (f'<link href="{m.group(2)}" color="#2a78d6">{m.group(1)}</link>'
                          if m.group(2).startswith("http") else m.group(1)), t)
    t = t.replace("\\*", "*")
    return t


def _tabela(linhas: list[str], st, largura: float):
    dados = []
    for l in linhas:
        cel = [c.strip() for c in l.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cel if c):
            continue
        dados.append(cel)
    if not dados:
        return Spacer(1, 1)
    n = max(len(r) for r in dados)
    dados = [r + [""] * (n - len(r)) for r in dados]
    tam = [max(6, max(len(re.sub(r"[*`]", "", r[j])) for r in dados)) for j in range(n)]
    tam = [min(t, 60) for t in tam]
    tot = sum(tam)
    larg = [largura * t / tot for t in tam]
    corpo = [[Paragraph(_inline(c), st["celh"] if i == 0 else st["cel"]) for c in r]
             for i, r in enumerate(dados)]
    t = Table(corpo, colWidths=larg, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_CLARO),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f8fa")]),
    ]))
    return t


def _imagem(caminho: Path, largura: float, altura_max: float):
    from PIL import Image as PImage

    with PImage.open(caminho) as im:
        w, h = im.size
    esc = min(largura / w, altura_max / h)
    return Image(str(caminho), width=w * esc, height=h * esc)


def converter(md: str, st, largura: float, altura: float) -> list:
    out: list = []
    linhas = md.splitlines()
    i = 0
    while i < len(linhas):
        l = linhas[i]
        s = l.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            bloco = []
            i += 1
            while i < len(linhas) and not linhas[i].strip().startswith("```"):
                bloco.append(linhas[i])
                i += 1
            i += 1
            pre = Preformatted("\n".join(bloco), st["code"])
            caixa = Table([[pre]], colWidths=[largura])
            caixa.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f4f1")),
                                       ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                       ("TOPPADDING", (0, 0), (-1, -1), 5),
                                       ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            out += [caixa, Spacer(1, 5)]
            continue
        if s.startswith("|"):
            bloco = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                bloco.append(linhas[i])
                i += 1
            out += [_tabela(bloco, st, largura), Spacer(1, 6)]
            continue
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", s)
        if m:
            caminho = (ORIGEM.parent / m.group(2)).resolve()
            if caminho.exists():
                out += [_imagem(caminho, largura, altura * 0.42), Spacer(1, 6)]
            i += 1
            continue
        if re.fullmatch(r"-{3,}", s):
            out.append(HRFlowable(width="100%", thickness=0.6, color=LINHA, spaceBefore=4, spaceAfter=6))
            i += 1
            continue
        if s.startswith("# "):
            out.append(Paragraph(_inline(s[2:]), st["titulo"]))
        elif s.startswith("## "):
            out.append(Paragraph(_inline(s[3:]), st["h1"]))
        elif s.startswith("### "):
            out.append(Paragraph(_inline(s[4:]), st["h2"]))
        elif s.startswith("#### "):
            out.append(Paragraph(_inline(s[5:]), st["h3"]))
        elif s.startswith(">"):
            txt = s.lstrip("> ")
            while i + 1 < len(linhas) and linhas[i + 1].strip().startswith(">"):
                i += 1
                txt += " " + linhas[i].strip().lstrip("> ")
            out.append(Paragraph(_inline(txt), st["quote"]))
        elif re.match(r"^\s*([*-]|\d+\.)\s", l):
            m2 = re.match(r"^(\s*)([*-]|\d+\.)\s+(.*)", l)
            txt = m2.group(3)
            while i + 1 < len(linhas) and linhas[i + 1].startswith("  ") and \
                    not re.match(r"^\s*([*-]|\d+\.)\s", linhas[i + 1]):
                i += 1
                txt += " " + linhas[i].strip()
            marcador = "•" if m2.group(2) in "*-" else m2.group(2)
            estilo = ParagraphStyle("lix", parent=st["li"], leftIndent=14 + 12 * (len(m2.group(1)) // 2))
            out.append(Paragraph(_inline(txt), estilo, bulletText=marcador))
        else:
            txt = s
            while i + 1 < len(linhas) and linhas[i + 1].strip() and not re.match(
                    r"^(#|\||>|!\[|```|\s*([*-]|\d+\.)\s|-{3,})", linhas[i + 1].strip()):
                i += 1
                txt += " " + linhas[i].strip()
            out.append(Paragraph(_inline(txt), st["p"]))
        i += 1
    return out


def capa(st, repo: str, video: str, autores: str) -> list:
    itens = [Spacer(1, 3.5 * cm),
             Paragraph("Tech Challenge — Fase 2", st["sub"]),
             Paragraph("MedRoute: otimização de rotas para distribuição de medicamentos e insumos",
                       st["titulo"]),
             Paragraph("Projeto 2 — algoritmo genético para roteamento de veículos (VRP) com "
                       "restrições hospitalares + LLM para instruções, relatórios e perguntas",
                       st["sub"]),
             Spacer(1, 1.2 * cm),
             HRFlowable(width="40%", thickness=2, color=colors.HexColor("#3987e5"), hAlign="LEFT"),
             Spacer(1, 0.6 * cm),
             Paragraph(f"<b>Autor:</b> {autores}", st["p"]),
             Paragraph(f"<b>Data:</b> {date.today().strftime('%d/%m/%Y')}", st["p"]),
             Paragraph(f"<b>Repositório:</b> {_inline(repo)}", st["p"]),
             Paragraph(f"<b>Vídeo de demonstração:</b> {_inline(video)}", st["p"]),
             Spacer(1, 0.8 * cm)]
    fig = RAIZ / "reports" / "figures" / "01_mapa_rotas_ga.png"
    if fig.exists():
        itens.append(_imagem(fig, 17 * cm, 9.5 * cm))
    itens.append(PageBreak())
    return itens


def _rodape(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("DV", 7.5)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, 1.2 * cm, "Tech Challenge Fase 2 · MedRoute · relatório técnico")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"página {doc.page}")
    canvas.restoreState()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="(inserir o link do repositório Git)")
    ap.add_argument("--video", default="(inserir o link do vídeo no YouTube/Vimeo)")
    ap.add_argument("--autores", default="Enio Rodrigues")
    ap.add_argument("--saida", default=str(DESTINO))
    a = ap.parse_args()
    _registrar_fontes()
    st = _estilos()
    doc = SimpleDocTemplate(a.saida, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Tech Challenge Fase 2 — MedRoute", author=a.autores)
    largura = A4[0] - 4 * cm
    altura = A4[1] - 3.6 * cm
    md = ORIGEM.read_text(encoding="utf-8")
    # O título/autor do Markdown já vão na capa.
    md = re.sub(r"\A# .*?\n---\n", "", md, count=1, flags=re.S)
    historia = capa(st, a.repo, a.video, a.autores) + converter(md, st, largura, altura)
    doc.build(historia, onFirstPage=lambda c, d: None, onLaterPages=_rodape)
    print(f"PDF: {a.saida}")
    _ = KeepTogether  # (disponível para ajustes de paginação)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
