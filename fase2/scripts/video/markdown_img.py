"""
Renderizador mínimo de Markdown para imagem (Pillow).

Suporta o subconjunto que as respostas da LLM usam: títulos ``#``/``##``/
``###``, parágrafos, **negrito**, `código`, listas (com recuo), listas
numeradas, citações ``>``, linhas ``---`` e tabelas ``| a | b |`` com quebra
de linha dentro das células. Comentários HTML são ignorados.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PIL import Image, ImageDraw

from fontes import fonte

INK = "#0b0b0b"
INK_2 = "#52514e"
AZUL = "#104281"
LINHA = "#e1e0d9"
FUNDO_CODIGO = "#f1f0ec"
FUNDO_TABELA = "#f6f8fb"

_RE_INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


@dataclass
class _Run:
    texto: str
    estilo: str  # normal | bold | code


def _runs(texto: str) -> list[_Run]:
    texto = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", texto)       # itálico vira normal
    out: list[_Run] = []
    for parte in _RE_INLINE.split(texto):
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            out.append(_Run(parte[2:-2], "bold"))
        elif parte.startswith("`") and parte.endswith("`"):
            out.append(_Run(parte[1:-1], "code"))
        else:
            out.append(_Run(parte, "normal"))
    return out


class MarkdownImagem:
    def __init__(self, largura: int, base: int = 25) -> None:
        self.largura = largura
        self.base = base

    def _f(self, estilo: str, tam: int | None = None):
        tam = tam or self.base
        return {"normal": fonte("sans", tam), "bold": fonte("sans_bold", tam),
                "code": fonte("mono", tam - 2)}[estilo]

    # ------------------------------------------------------------ quebra
    def _linhas(self, runs: list[_Run], largura: int, tam: int, forcar_bold: bool = False):
        """Quebra runs com estilos em linhas que cabem em ``largura``."""
        palavras: list[tuple[str, str]] = []
        for r in runs:
            estilo = "bold" if forcar_bold and r.estilo == "normal" else r.estilo
            for i, w in enumerate(re.split(r"(\s+)", r.texto)):
                if w:
                    palavras.append((w, estilo))
        linhas: list[list[tuple[str, str]]] = [[]]
        x = 0.0
        for w, estilo in palavras:
            f = self._f(estilo, tam)
            lw = f.getlength(w)
            if w.isspace():
                if linhas[-1]:
                    linhas[-1].append((" ", estilo))
                    x += f.getlength(" ")
                continue
            if x + lw > largura and linhas[-1]:
                while linhas[-1] and linhas[-1][-1][0] == " ":
                    linhas[-1].pop()
                linhas.append([])
                x = 0.0
            linhas[-1].append((w, estilo))
            x += lw
        return linhas

    def _desenhar_linha(self, d: ImageDraw.ImageDraw, linha, x: float, y: float, tam: int,
                        cor: str = INK) -> None:
        for w, estilo in linha:
            f = self._f(estilo, tam)
            if estilo == "code":
                lw = f.getlength(w)
                d.rounded_rectangle([x - 2, y + 2, x + lw + 2, y + tam + 4], radius=4,
                                    fill=FUNDO_CODIGO)
                d.text((x, y + 3), w, font=f, fill=INK)
            else:
                d.text((x, y), w, font=f, fill=cor)
            x += f.getlength(w)

    # ------------------------------------------------------------ blocos
    def render(self, texto: str) -> Image.Image:
        texto = re.sub(r"<!--.*?-->", "", texto, flags=re.S).strip("\n")
        blocos = self._blocos(texto.splitlines())
        # Duas passadas: medir altura, depois desenhar.
        altura = self._desenhar(None, blocos)
        img = Image.new("RGB", (self.largura, max(10, int(altura) + 10)), "white")
        self._desenhar(ImageDraw.Draw(img), blocos)
        return img

    def _blocos(self, linhas: list[str]):
        blocos = []
        i = 0
        while i < len(linhas):
            l = linhas[i].rstrip()
            if not l.strip():
                blocos.append(("vazio", None))
            elif l.lstrip().startswith("|"):
                tabela = []
                while i < len(linhas) and linhas[i].lstrip().startswith("|"):
                    celulas = [c.strip() for c in linhas[i].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r":?-{2,}:?", c) for c in celulas if c):
                        tabela.append(celulas)
                    i += 1
                blocos.append(("tabela", tabela))
                continue
            elif re.match(r"^#{1,3} ", l):
                nivel = len(l) - len(l.lstrip("#"))
                blocos.append((f"h{nivel}", l.lstrip("#").strip()))
            elif re.match(r"^\s*[-*] ", l):
                recuo = (len(l) - len(l.lstrip())) // 2
                blocos.append(("item", (recuo, "•", l.lstrip()[2:])))
            elif re.match(r"^\s*\d+\. ", l):
                recuo = (len(l) - len(l.lstrip())) // 2
                m = re.match(r"^\s*(\d+)\. (.*)", l)
                blocos.append(("item", (recuo, f"{m.group(1)}.", m.group(2))))
            elif l.startswith(">"):
                blocos.append(("citacao", l.lstrip("> ").strip()))
            elif re.fullmatch(r"\s*(-{3,}|\*{3,})\s*", l):
                blocos.append(("hr", None))
            else:
                blocos.append(("p", l.strip()))
            i += 1
        return blocos

    def _desenhar(self, d: ImageDraw.ImageDraw | None, blocos) -> float:
        y = 4.0
        b = self.base
        W = self.largura
        anterior_vazio = True
        for tipo, conteudo in blocos:
            if tipo == "vazio":
                if not anterior_vazio:
                    y += b * 0.55
                anterior_vazio = True
                continue
            anterior_vazio = False
            if tipo in ("h1", "h2", "h3"):
                tam = {"h1": int(b * 1.5), "h2": int(b * 1.3), "h3": int(b * 1.12)}[tipo]
                y += b * 0.35
                for linha in self._linhas(_runs(conteudo), W, tam, forcar_bold=True):
                    if d:
                        self._desenhar_linha(d, linha, 0, y, tam, AZUL)
                    y += tam * 1.3
                y += b * 0.2
            elif tipo == "p":
                for linha in self._linhas(_runs(conteudo), W, b):
                    if d:
                        self._desenhar_linha(d, linha, 0, y, b)
                    y += b * 1.42
            elif tipo == "item":
                recuo, marcador, txt = conteudo
                x0 = 8 + recuo * 34
                xt = x0 + max(26, self._f("normal").getlength(marcador + " ") + 6)
                primeira = True
                for linha in self._linhas(_runs(txt), W - xt, b):
                    if d and primeira:
                        d.text((x0, y), marcador, font=self._f("bold"), fill=AZUL)
                    if d:
                        self._desenhar_linha(d, linha, xt, y, b)
                    primeira = False
                    y += b * 1.42
            elif tipo == "citacao":
                y0 = y
                for linha in self._linhas(_runs(conteudo), W - 28, b - 2):
                    if d:
                        self._desenhar_linha(d, linha, 22, y, b - 2, INK_2)
                    y += (b - 2) * 1.42
                if d:
                    d.rectangle([4, y0, 9, y - 4], fill="#86b6ef")
            elif tipo == "hr":
                y += b * 0.4
                if d:
                    d.line([(0, y), (W, y)], fill=LINHA, width=2)
                y += b * 0.6
            elif tipo == "tabela":
                y = self._tabela(d, conteudo, y)
        return y

    def _tabela(self, d, linhas: list[list[str]], y: float) -> float:
        if not linhas:
            return y
        n = max(len(l) for l in linhas)
        tam = self.base - 3
        pad = 12
        largs = [0.0] * n
        for l in linhas:
            for j, c in enumerate(l):
                txt = re.sub(r"\*\*|`", "", c)
                largs[j] = max(largs[j], self._f("bold", tam).getlength(txt) + 2 * pad)
        total = sum(largs)
        if total > self.largura:
            largs = [w * self.largura / total for w in largs]
        y += 6
        for i, l in enumerate(linhas):
            celulas = [self._linhas(_runs(c), largs[j] - 2 * pad, tam, forcar_bold=(i == 0))
                       for j, c in enumerate(l + [""] * (n - len(l)))]
            h = max(len(c) for c in celulas) * tam * 1.38 + 14
            if d:
                if i == 0:
                    d.rectangle([0, y, sum(largs), y + h], fill="#e8f0fb")
                elif i % 2 == 0:
                    d.rectangle([0, y, sum(largs), y + h], fill=FUNDO_TABELA)
                d.line([(0, y + h), (sum(largs), y + h)], fill=LINHA, width=1)
            x = 0.0
            for j, cel in enumerate(celulas):
                yy = y + 7
                for linha in cel:
                    if d:
                        self._desenhar_linha(d, linha, x + pad, yy, tam)
                    yy += tam * 1.38
                x += largs[j]
            y += h
        return y + 10
