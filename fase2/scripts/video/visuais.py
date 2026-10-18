"""
Renderização dos quadros com Pillow.

Estáticos (uma imagem segurada pelo ffmpeg): ``titulo``, ``codigo``,
``arvore`` e ``figura``/``tela`` sem zoom.

Animados (quadro a quadro, com cache de quadros repetidos):

* ``terminal``  — o comando é "digitado" e a saída real aparece linha a linha;
* ``figura``/``tela`` com ``zoom`` — aproximação suave (efeito Ken Burns) até a
  região de interesse, para a tela não ficar parada;
* ``documento`` — o Markdown gerado pela LLM rola na tela ao longo da fala;
* ``chat``      — perguntas e respostas da LLM surgem em balões;
* ``evolucao``  — quadros-chave da evolução do GA (rotas + convergência).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from PIL import Image, ImageDraw

import captura
from fontes import fonte
from markdown_img import MarkdownImagem
from roteiro import (ALTURA, EVOLUCAO_DIR, FIGURES_DIR, LARGURA, LLM_DIR, PROJECT_ROOT, RODAPE,
                     TELAS_DIR, Cena, Visual)

# ---------------------------------------------------------------------------
# Paleta (a mesma dos gráficos do projeto)
# ---------------------------------------------------------------------------
FUNDO = "#f6f7f9"
FAIXA = "#104281"
FAIXA_2 = "#3987e5"
TEXTO = "#0b0b0b"
TEXTO_SUAVE = "#52514e"
LINHA = "#e1e0d9"
BRANCO = "#ffffff"
DESTAQUE_FUNDO = "#fff3c4"
DESTAQUE_BORDA = "#e8c547"
AZUL = "#2a78d6"

TERM_FUNDO = "#1e1e1e"
TERM_BARRA = "#323233"
TERM_TEXTO = "#d4d4d4"
TERM_PROMPT = "#6ee787"
TERM_SECAO = "#4fc1ff"
TERM_ALERTA = "#f2cc60"

ALTURA_FAIXA = 96
MARGEM = 72
ALTURA_RODAPE = 54


def _largura(texto: str, f) -> float:
    return f.getlength(texto)


def _avanco_mono(tamanho: int) -> float:
    return fonte("mono", tamanho).getlength("M")


def _tela_base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (LARGURA, ALTURA), FUNDO)
    return img, ImageDraw.Draw(img)


def _faixa_titulo(d: ImageDraw.ImageDraw, titulo: str, etiqueta: str = "") -> None:
    d.rectangle([0, 0, LARGURA, ALTURA_FAIXA], fill=FAIXA)
    d.rectangle([0, ALTURA_FAIXA, LARGURA, ALTURA_FAIXA + 5], fill=FAIXA_2)
    tamanho = 40
    f = fonte("sans_semibold", tamanho)
    limite = LARGURA - 2 * MARGEM - (_largura(etiqueta, fonte("sans", 26)) + 48 if etiqueta else 0)
    while _largura(titulo, f) > limite and tamanho > 22:
        tamanho -= 2
        f = fonte("sans_semibold", tamanho)
    d.text((MARGEM, ALTURA_FAIXA / 2), titulo, font=f, fill=BRANCO, anchor="lm")
    if etiqueta:
        d.text((LARGURA - MARGEM, ALTURA_FAIXA / 2), etiqueta, font=fonte("sans", 26),
               fill="#b7d3f6", anchor="rm")


def _rodape(d: ImageDraw.ImageDraw, texto: str) -> None:
    y = ALTURA - ALTURA_RODAPE
    d.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=LINHA, width=2)
    d.text((MARGEM, y + ALTURA_RODAPE / 2 + 2), texto, font=fonte("sans", 22),
           fill=TEXTO_SUAVE, anchor="lm")


def _quebrar(texto: str, f, largura_max: float) -> list[str]:
    if not texto:
        return [""]
    linhas: list[str] = []
    atual = ""
    for palavra in texto.split(" "):
        tentativa = f"{atual} {palavra}".strip()
        if _largura(tentativa, f) <= largura_max or not atual:
            atual = tentativa
        else:
            linhas.append(atual)
            atual = palavra
    linhas.append(atual)
    return linhas


def _cartao(img: Image.Image, conteudo: Image.Image, area: tuple[int, int, int, int],
            pad: int = 16, ampliar_max: float = 2.4) -> tuple[int, int, int, int]:
    """Cola ``conteudo`` centralizado na área, num cartão branco com sombra."""
    x0, y0, x1, y1 = area
    aw, ah = (x1 - x0) - 2 * pad, (y1 - y0) - 2 * pad
    esc = min(aw / conteudo.width, ah / conteudo.height, ampliar_max)
    novo = (max(1, int(conteudo.width * esc)), max(1, int(conteudo.height * esc)))
    c = conteudo.resize(novo, Image.LANCZOS)
    px = x0 + pad + (aw - novo[0]) // 2
    py = y0 + pad + (ah - novo[1]) // 2
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([px - pad + 6, py - pad + 8, px + novo[0] + pad + 6, py + novo[1] + pad + 8],
                        radius=14, fill="#e2e6ea")
    d.rounded_rectangle([px - pad, py - pad, px + novo[0] + pad, py + novo[1] + pad],
                        radius=14, fill=BRANCO, outline=LINHA, width=2)
    img.paste(c, (px, py))
    return px, py, px + novo[0], py + novo[1]


# ---------------------------------------------------------------------------
# Título
# ---------------------------------------------------------------------------
def render_titulo(cena: Cena, etiqueta: str) -> Image.Image:
    img, d = _tela_base()
    d.rectangle([0, 0, 22, ALTURA], fill=FAIXA)
    d.rectangle([22, 0, 30, ALTURA], fill=FAIXA_2)
    x = MARGEM + 60
    larg = LARGURA - x - MARGEM
    if etiqueta:
        d.text((x, 118), etiqueta.upper(), font=fonte("sans_semibold", 26), fill=FAIXA_2, anchor="lm")
    tam = 76
    f = fonte("sans_bold", tam)
    while len(_quebrar(cena.titulo, f, larg)) > 2 and tam > 44:
        tam -= 4
        f = fonte("sans_bold", tam)
    y = 205
    for linha in _quebrar(cena.titulo, f, larg):
        d.text((x, y), linha, font=f, fill=FAIXA, anchor="lt")
        y += int(tam * 1.22)
    if cena.subtitulo:
        y += 12
        fs = fonte("sans", 40)
        for linha in _quebrar(cena.subtitulo, fs, larg):
            d.text((x, y), linha, font=fs, fill=TEXTO_SUAVE, anchor="lt")
            y += 54
    if cena.topicos:
        y += 40
        d.line([(x, y), (x + 200, y)], fill=FAIXA_2, width=5)
        y += 40
        ft = fonte("sans", 36)
        for topico in cena.topicos:
            if not topico.strip():
                y += 24
                continue
            d.text((x + 6, y + 2), "•", font=ft, fill=FAIXA_2, anchor="lt")
            for linha in _quebrar(topico, ft, larg - 46):
                d.text((x + 46, y), linha, font=ft, fill=TEXTO, anchor="lt")
                y += 50
            y += 10
    _rodape(d, RODAPE)
    return img


# ---------------------------------------------------------------------------
# Figura e tela (estáticas ou com zoom)
# ---------------------------------------------------------------------------
def _area_conteudo(com_legenda: bool) -> tuple[int, int, int, int]:
    base = ALTURA - ALTURA_RODAPE - (70 if com_legenda else 20)
    return MARGEM, ALTURA_FAIXA + 30, LARGURA - MARGEM, base


def _imagem_ausente(d: ImageDraw.ImageDraw, nome: str, dica: str) -> None:
    d.text((LARGURA / 2, ALTURA / 2), f"[imagem ausente: {nome}]\n{dica}", font=fonte("mono", 32),
           fill="#b03a2e", anchor="mm", align="center")


def render_figura(cena: Cena, etiqueta: str) -> tuple[Image.Image, tuple[int, int, int, int] | None]:
    img, d = _tela_base()
    _faixa_titulo(d, cena.titulo or Path(cena.asset).stem, etiqueta)
    caminho = FIGURES_DIR / cena.asset
    caixa = None
    if caminho.exists():
        caixa = _cartao(img, Image.open(caminho).convert("RGB"), _area_conteudo(bool(cena.legenda)))
    else:
        _imagem_ausente(d, cena.asset, "rode: python main.py / scripts/run_experiments.py")
    if cena.legenda:
        d.text((LARGURA / 2, ALTURA - ALTURA_RODAPE - 40), cena.legenda, font=fonte("sans", 28),
               fill=TEXTO_SUAVE, anchor="mm")
    _rodape(d, f"reports/figures/{cena.asset}")
    return img, caixa


def _janela_navegador(tela: Image.Image, url: str) -> Image.Image:
    """Moldura simples de navegador em volta da captura."""
    barra = 54
    out = Image.new("RGB", (tela.width, tela.height + barra), "#dee1e6")
    d = ImageDraw.Draw(out)
    for i, cor in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        cx = 26 + i * 26
        d.ellipse([cx - 8, barra / 2 - 8, cx + 8, barra / 2 + 8], fill=cor)
    d.rounded_rectangle([110, 11, tela.width - 30, barra - 11], radius=14, fill=BRANCO)
    d.text((130, barra / 2), url, font=fonte("sans", 22), fill=TEXTO_SUAVE, anchor="lm")
    out.paste(tela, (0, barra))
    return out


URLS = {
    "painel_mapa.png": "localhost:8501  ·  painel MedRoute (Streamlit)",
    "painel_mapa_atual.png": "localhost:8501  ·  painel MedRoute (Streamlit)",
    "painel_evolucao.png": "localhost:8501  ·  aba Evolução do GA",
    "painel_comparativo.png": "localhost:8501  ·  aba Comparativo",
    "painel_llm.png": "localhost:8501  ·  aba Assistente (LLM)",
    "painel_chat.png": "localhost:8501  ·  aba Assistente (LLM)",
    "painel_dados.png": "localhost:8501  ·  aba Dados",
    "api_docs.png": "localhost:8000/docs  ·  API REST (FastAPI / OpenAPI)",
    "mapa_popup.png": "reports/maps/mapa_rotas_ga.html  ·  mapa interativo (folium)",
}


def render_tela(cena: Cena, etiqueta: str) -> tuple[Image.Image, tuple[int, int, int, int] | None]:
    img, d = _tela_base()
    _faixa_titulo(d, cena.titulo or cena.asset, etiqueta)
    caminho = TELAS_DIR / cena.asset
    caixa = None
    if caminho.exists():
        janela = _janela_navegador(Image.open(caminho).convert("RGB"), URLS.get(cena.asset, ""))
        caixa = _cartao(img, janela, _area_conteudo(False), pad=10)
        # a captura começa 54 px abaixo do topo da janela (barra do navegador)
        esc = (caixa[2] - caixa[0]) / janela.width
        caixa = (caixa[0], int(caixa[1] + 54 * esc), caixa[2], caixa[3])
    else:
        _imagem_ausente(d, cena.asset, "rode: python scripts/video/gerar_video.py --recapturar-telas")
    _rodape(d, "captura real do sistema em execução")
    return img, caixa


def _ret_16x9(x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
    """Ajusta um retângulo para a proporção 16:9 em torno do centro, dentro da tela."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = x1 - x0, y1 - y0
    if w / h > 16 / 9:
        h = w * 9 / 16
    else:
        w = h * 16 / 9
    w, h = min(w, LARGURA), min(h, ALTURA)
    x0 = min(max(0, cx - w / 2), LARGURA - w)
    y0 = min(max(0, cy - h / 2), ALTURA - h)
    return x0, y0, x0 + w, y0 + h


def frames_zoom(base: Image.Image, caixa: tuple[int, int, int, int], zoom, n_frames: int,
                fps: int) -> Iterator[Image.Image]:
    """Aproxima suavemente do quadro inteiro até a região ``zoom`` da imagem."""
    bx0, by0, bx1, by1 = caixa
    zx0, zy0, zx1, zy1 = zoom
    alvo = _ret_16x9(bx0 + zx0 * (bx1 - bx0), by0 + zy0 * (by1 - by0),
                     bx0 + zx1 * (bx1 - bx0), by0 + zy1 * (by1 - by0))
    ini = (0.0, 0.0, float(LARGURA), float(ALTURA))
    dur = n_frames / fps
    t_ini, t_fim = min(1.2, dur * 0.12), min(dur * 0.55, 1.2 + 4.0)
    ultimo = None
    for i in range(n_frames):
        t = i / fps
        u = 0.0 if t <= t_ini else min(1.0, (t - t_ini) / max(0.01, t_fim - t_ini))
        u = 0.5 - 0.5 * math.cos(math.pi * u)            # suavização
        ret = tuple(a + (b - a) * u for a, b in zip(ini, alvo))
        chave = tuple(round(v) for v in ret)
        if chave != ultimo:
            quadro = base.crop(chave).resize((LARGURA, ALTURA), Image.BICUBIC)
            ultimo = chave
        yield quadro


# ---------------------------------------------------------------------------
# Código
# ---------------------------------------------------------------------------
def render_codigo(cena: Cena, etiqueta: str) -> Image.Image:
    img, d = _tela_base()
    _faixa_titulo(d, cena.titulo or cena.asset, etiqueta)
    caminho = PROJECT_ROOT / cena.asset
    if not caminho.exists():
        _imagem_ausente(d, cena.asset, "")
        return img
    todas = caminho.read_text(encoding="utf-8").splitlines()
    ini = (cena.linha_inicial or 1) - 1
    fim = cena.linha_final or len(todas)
    trecho = todas[ini:fim]
    numeros = list(range(ini + 1, ini + 1 + len(trecho)))
    topo, base = ALTURA_FAIXA + 34, ALTURA - ALTURA_RODAPE - 20
    larg_cartao = LARGURA - 2 * MARGEM
    gutter = 96
    tam = 31
    while tam > 15:
        f = fonte("mono", tam)
        alt = int(tam * 1.5)
        if len(trecho) * alt + 50 <= base - topo and \
                max((_largura(l, f) for l in trecho), default=0) + gutter + 60 <= larg_cartao:
            break
        tam -= 1
    f = fonte("mono", tam)
    alt = int(tam * 1.5)
    h_cartao = len(trecho) * alt + 50
    cy = topo + max(0, ((base - topo) - h_cartao) // 2)
    d.rounded_rectangle([MARGEM + 6, cy + 8, MARGEM + larg_cartao + 6, cy + h_cartao + 8], radius=12,
                        fill="#e2e6ea")
    d.rounded_rectangle([MARGEM, cy, MARGEM + larg_cartao, cy + h_cartao], radius=12, fill=BRANCO,
                        outline=LINHA, width=2)
    d.rectangle([MARGEM + 2, cy + 2, MARGEM + gutter, cy + h_cartao - 2], fill="#eef3f6")
    destaque = set(cena.destaque)
    y = cy + 25
    for num, linha in zip(numeros, trecho):
        if num in destaque:
            d.rectangle([MARGEM + gutter + 2, y - 3, MARGEM + larg_cartao - 3, y + alt - 4],
                        fill=DESTAQUE_FUNDO)
            d.rectangle([MARGEM + gutter + 2, y - 3, MARGEM + gutter + 7, y + alt - 4],
                        fill=DESTAQUE_BORDA)
        d.text((MARGEM + gutter - 16, y), str(num), font=f, fill="#9aa9b4", anchor="rt")
        cor = "#4a6572" if linha.lstrip().startswith("#") or linha.lstrip().startswith('"""') else TEXTO
        d.text((MARGEM + gutter + 22, y), linha, font=f, fill=cor, anchor="lt")
        y += alt
    _rodape(d, f"{cena.asset}  ·  linhas {numeros[0]}–{numeros[-1]}" if numeros else cena.asset)
    return img


# ---------------------------------------------------------------------------
# Árvore do projeto
# ---------------------------------------------------------------------------
_IGNORAR = {".venv", "venv", "__pycache__", ".git", ".pytest_cache", ".ipynb_checkpoints",
            "_cache", ".cache", "medroute.egg-info", ".streamlit"}
_COLAPSAR = {"data", "reports", "notebooks", "legacy", "video"}
_COMENTARIOS = {
    "ga/": "algoritmo genético (representação, operadores, motor)",
    "llm/": "OpenRouter, prompts, guardrails, modo offline",
    "viz/": "mapas folium/PNG, gráficos, pygame",
    "api/": "API REST (FastAPI)",
    "problem.py": "função fitness",
    "baselines.py": "abordagens de comparação",
    "plan.py": "plano de rotas + KPIs",
    "dashboard.py": "painel Streamlit",
    "run_experiments.py": "comparativo, ablação, escala",
    "avaliar_llm.py": "avaliação da LLM",
    "main.py": "pipeline completo",
    "tests/": "testes automatizados (pytest)",
    "docs/": "arquitetura, API, prompts, relatório",
}


def _arvore_linhas(raiz: Path = PROJECT_ROOT) -> list[str]:
    linhas = [f"{raiz.name}/"]

    def caminhar(base: Path, prefixo: str, nivel: int) -> None:
        try:
            itens = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return
        visiveis = [p for p in itens if p.name not in _IGNORAR and not p.name.startswith(".")
                    and not p.name.endswith((".pdf", ".txt", ".srt", ".pyc"))]
        if nivel >= 1:
            visiveis = [p for p in visiveis if p.is_dir() or p.suffix in (".py", ".md", ".toml")]
        if nivel >= 2:
            visiveis = [p for p in visiveis if p.is_dir() or p.name in _COMENTARIOS]
        for i, item in enumerate(visiveis):
            ultimo = i == len(visiveis) - 1
            con = "└── " if ultimo else "├── "
            if item.is_dir():
                if item.name in _COLAPSAR or nivel >= 3:
                    n = sum(1 for _ in item.iterdir())
                    linhas.append(f"{prefixo}{con}{item.name}/  ({n} itens)")
                    continue
                linhas.append(f"{prefixo}{con}{item.name}/")
                caminhar(item, prefixo + ("    " if ultimo else "│   "), nivel + 1)
            else:
                linhas.append(f"{prefixo}{con}{item.name}")

    caminhar(raiz, "", 0)
    return linhas


def render_arvore(cena: Cena, etiqueta: str) -> Image.Image:
    img, d = _tela_base()
    _faixa_titulo(d, cena.titulo or "Organização do projeto", etiqueta)
    linhas = _arvore_linhas()
    topo, base = ALTURA_FAIXA + 30, ALTURA - ALTURA_RODAPE - 16
    disp = base - topo
    tam = 28
    while tam > 12 and len(linhas) * int(tam * 1.45) + 40 > disp:
        tam -= 1
    alt = int(tam * 1.45)
    cabem = max(1, (disp - 40) // alt)
    if len(linhas) > cabem:
        linhas = linhas[:cabem - 1] + ["..."]
    f, fc = fonte("mono", tam), fonte("mono", max(12, tam - 3))
    larg = LARGURA - 2 * MARGEM
    h = len(linhas) * alt + 40
    cy = topo + max(0, (disp - h) // 2)
    d.rounded_rectangle([MARGEM, cy, MARGEM + larg, cy + h], radius=12, fill=BRANCO, outline=LINHA,
                        width=2)
    mais_longa = max(len(l) for l in linhas)
    col = min(MARGEM + 28 + int((mais_longa + 3) * _avanco_mono(tam)), MARGEM + larg - 620)
    y = cy + 20
    for l in linhas:
        nome = l.split("── ")[-1].split("  (")[0]
        eh_dir = nome.endswith("/")
        d.text((MARGEM + 28, y), l, font=f, fill=FAIXA if eh_dir else TEXTO, anchor="lt")
        com = _COMENTARIOS.get(nome)
        if com:
            d.text((col, y + 2), f"# {com}", font=fc, fill=AZUL, anchor="lt")
        y += alt
    _rodape(d, "pacote Python instalável (pyproject) + scripts + testes + documentação")
    return img


# ---------------------------------------------------------------------------
# Terminal (animado)
# ---------------------------------------------------------------------------
@dataclass
class _PlanoTerminal:
    comando: str
    arquivo: str
    linhas: list[str]
    tamanho: int
    visiveis: int
    caixa: tuple[int, int, int, int]


def _recortar(linhas: list[str], cena: Cena) -> list[str]:
    ini, fim = 0, len(linhas)
    if cena.marcador_inicio:
        for i, l in enumerate(linhas):
            if cena.marcador_inicio in l:
                ini = i - 1 if i > 0 and set(linhas[i - 1].strip()) == {"="} else i
                break
    if cena.marcador_fim:
        for j in range(ini + 1, len(linhas)):
            if cena.marcador_fim in linhas[j]:
                fim = j - 1 if set(linhas[j - 1].strip()) == {"="} else j
                break
    recorte = linhas[ini:fim]
    while recorte and not recorte[0].strip():
        recorte.pop(0)
    while recorte and not recorte[-1].strip():
        recorte.pop()
    if cena.linhas_finais:
        finais = [l for l in linhas[-cena.linhas_finais:] if l.strip()]
        if finais and finais[-1] not in recorte:
            recorte += ["", "  [...]", ""] + finais
    return recorte


def _planejar_terminal(cena: Cena) -> _PlanoTerminal:
    linhas = _recortar(captura.ler_captura(cena.asset), cena)
    cmd = captura.COMANDOS[cena.asset].rotulo
    x0, y0 = MARGEM, ALTURA_FAIXA + 40
    x1, y1 = LARGURA - MARGEM, ALTURA - ALTURA_RODAPE - 20
    larg_txt = (x1 - x0) - 60
    alt_txt = (y1 - y0) - 46 - 32
    mais_longa = max(max((len(l) for l in linhas), default=0), len(cmd) + 30)
    tam = 26
    while tam > 13 and _avanco_mono(tam) * mais_longa > larg_txt:
        tam -= 1
    alt = int(tam * 1.45)
    vis = max(6, alt_txt // alt)
    if len(linhas) + 2 < vis:
        vis = max(8, len(linhas) + 2)
        h = 46 + 32 + vis * alt
        y0 += ((y1 - y0) - h) // 2
        y1 = y0 + h
    return _PlanoTerminal(cmd, captura.caminho_captura(cena.asset).name, linhas, tam, vis,
                          (x0, y0, x1, y1))


def _cor_terminal(linha: str) -> str:
    s = linha.strip()
    if not s:
        return TERM_TEXTO
    if set(s) == {"="} or s.startswith("===") or s.startswith("---"):
        return TERM_SECAO
    if s[0].isdigit() and ". " in s[:4] and s == s.upper():
        return TERM_SECAO
    if "PASSED" in linha or " passed" in s or "viável: sim" in s or "fidelidade=100" in s.replace(" ", ""):
        return TERM_PROMPT
    if s.startswith("->") or "MedRoute" in s or "Parada:" in s or "VIOLA" in s:
        return TERM_ALERTA
    return TERM_TEXTO


def _desenhar_terminal(p: _PlanoTerminal, n_chars: int, n_linhas: int, cursor: bool,
                       titulo: str, etiqueta: str) -> Image.Image:
    img, d = _tela_base()
    _faixa_titulo(d, titulo, etiqueta)
    x0, y0, x1, y1 = p.caixa
    barra = 46
    d.rounded_rectangle([x0 + 6, y0 + 8, x1 + 6, y1 + 8], radius=14, fill="#dde5ea")
    d.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=TERM_FUNDO)
    d.rounded_rectangle([x0, y0, x1, y0 + barra], radius=14, fill=TERM_BARRA)
    d.rectangle([x0, y0 + barra - 14, x1, y0 + barra], fill=TERM_BARRA)
    for i, cor in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        cx = x0 + 28 + i * 26
        d.ellipse([cx - 8, y0 + barra / 2 - 8, cx + 8, y0 + barra / 2 + 8], fill=cor)
    d.text((x0 + (x1 - x0) / 2, y0 + barra / 2), "Windows PowerShell — Tech_Challenge-main\\fase2",
           font=fonte("sans", 22), fill="#9aa3ab", anchor="mm")
    f = fonte("mono", p.tamanho)
    alt = int(p.tamanho * 1.45)
    tx, ty = x0 + 30, y0 + barra + 18
    prompt = "PS fase2> "
    d.text((tx, ty), prompt, font=f, fill=TERM_PROMPT, anchor="lt")
    lp = _avanco_mono(p.tamanho) * len(prompt)
    dig = p.comando[:n_chars]
    d.text((tx + lp, ty), dig, font=f, fill=BRANCO, anchor="lt")
    if cursor:
        cx = tx + lp + _avanco_mono(p.tamanho) * len(dig)
        d.rectangle([cx, ty + 2, cx + _avanco_mono(p.tamanho) * 0.85, ty + alt - 6], fill="#cccccc")
    ty += alt + 6
    vis = p.visiveis - 2
    rev = p.linhas[:n_linhas]
    if len(rev) > vis:
        rev = rev[len(rev) - vis:]
    for l in rev:
        d.text((tx, ty), l, font=f, fill=_cor_terminal(l), anchor="lt")
        ty += alt
    _rodape(d, f"saída real de `{p.comando}` (capturada na execução)")
    return img


def frames_terminal(cena: Cena, etiqueta: str, n_frames: int, fps: int) -> Iterator[Image.Image]:
    p = _planejar_terminal(cena)
    dur = n_frames / fps
    fim_dig = min(1.6, dur * 0.2)
    ini_saida = fim_dig + min(0.35, dur * 0.05)
    fim_saida = max(ini_saida + 0.1, dur * 0.9)
    cache: dict = {}
    total = len(p.linhas)
    for i in range(n_frames):
        t = i / fps
        if t < fim_dig:
            nc, nl = int(len(p.comando) * t / fim_dig), 0
        else:
            nc = len(p.comando)
            nl = 0 if t <= ini_saida else int(round(total * min(1.0, (t - ini_saida) /
                                                                (fim_saida - ini_saida))))
        cur = t < ini_saida and int(t * 2) % 2 == 0
        k = (nc, nl, cur)
        if k not in cache:
            if len(cache) > 200:
                cache.clear()
            cache[k] = _desenhar_terminal(p, nc, nl, cur, cena.titulo, etiqueta)
        yield cache[k]


# ---------------------------------------------------------------------------
# Documento (Markdown da LLM com rolagem)
# ---------------------------------------------------------------------------
def _ler_markdown(nome: str) -> str:
    texto = (LLM_DIR / nome).read_text(encoding="utf-8")
    return re.sub(r"^<!--.*?-->\s*", "", texto, flags=re.S)


def _meta_llm(nome: str) -> str:
    """Selo com origem/modelo/nota (lido do cabeçalho do arquivo)."""
    cab = (LLM_DIR / nome).read_text(encoding="utf-8").splitlines()[0]
    m = re.search(r"modelo (\S+).*fidelidade ([\d.]+)", cab)
    if not m:
        return "gerado pela LLM"
    return f"gerado por {m.group(1)} (OpenRouter, gratuito)  ·  fidelidade aos dados {float(m.group(2)):.0f}/100"


def _plano_documento(cena: Cena, etiqueta: str):
    base, d = _tela_base()
    _faixa_titulo(d, cena.titulo, etiqueta)
    area = (MARGEM + 120, ALTURA_FAIXA + 70, LARGURA - MARGEM - 120, ALTURA - ALTURA_RODAPE - 22)
    d.rounded_rectangle([area[0] + 6, area[1] + 8, area[2] + 6, area[3] + 8], radius=14, fill="#e2e6ea")
    d.rounded_rectangle(area, radius=14, fill=BRANCO, outline=LINHA, width=2)
    d.text((area[0], ALTURA_FAIXA + 36), _meta_llm(cena.asset), font=fonte("sans", 24),
           fill=AZUL, anchor="lm")
    _rodape(d, f"reports/llm/{cena.asset}")
    pad = 34
    doc = MarkdownImagem(area[2] - area[0] - 2 * pad, base=27).render(_ler_markdown(cena.asset))
    janela = (area[0] + pad, area[1] + pad - 6, area[2] - pad, area[3] - pad + 6)
    return base, doc, janela


def _quadro_documento(base: Image.Image, doc: Image.Image, janela, desloc: int) -> Image.Image:
    img = base.copy()
    x0, y0, x1, y1 = janela
    h = y1 - y0
    img.paste(doc.crop((0, desloc, doc.width, min(doc.height, desloc + h))), (x0, y0))
    if doc.height > h:   # barra de rolagem discreta
        frac = h / doc.height
        pos = desloc / doc.height
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([x1 + 14, y0 + pos * h, x1 + 20, y0 + (pos + frac) * h], radius=3,
                            fill="#c3c2b7")
    return img


def frames_documento(cena: Cena, etiqueta: str, n_frames: int, fps: int) -> Iterator[Image.Image]:
    base, doc, janela = _plano_documento(cena, etiqueta)
    excesso = max(0, doc.height - (janela[3] - janela[1]))
    dur = n_frames / fps
    t0, t1 = dur * 0.10, dur * 0.92
    ultimo, quadro = None, None
    for i in range(n_frames):
        t = i / fps
        u = 0.0 if t <= t0 else min(1.0, (t - t0) / max(0.01, t1 - t0))
        desloc = int(excesso * u)
        if desloc != ultimo:
            quadro = _quadro_documento(base, doc, janela, desloc)
            ultimo = desloc
        yield quadro


# ---------------------------------------------------------------------------
# Chat (perguntas e respostas)
# ---------------------------------------------------------------------------
def _ler_conversa(nome: str) -> list[tuple[str, str, str]]:
    texto = (LLM_DIR / nome).read_text(encoding="utf-8")
    conversa = []
    for parte in texto.split("\n---\n"):
        m = re.search(r"\*\*Pergunta:\*\*\s*(.+?)\n\n\*\*Resposta\*\*\s*\((.*?)\):\s*\n\n(.*)", parte, re.S)
        if m:
            conversa.append((m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))
    return conversa


def _balao_usuario(texto: str, largura: int) -> Image.Image:
    f = fonte("sans", 27)
    linhas = _quebrar(texto, f, largura - 60)
    h = len(linhas) * 38 + 34
    w = int(min(largura, max(_largura(l, f) for l in linhas) + 60))
    img = Image.new("RGB", (w, h), FUNDO)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=22, fill=AZUL)
    y = 17
    for l in linhas:
        d.text((30, y), l, font=f, fill=BRANCO)
        y += 38
    return img


def _balao_assistente(texto: str, meta: str, largura: int) -> Image.Image:
    corpo = MarkdownImagem(largura - 64, base=24).render(texto)
    fm = fonte("sans", 20)
    nota = re.search(r"fidelidade ([\d.]+)", meta)
    m_modelo = re.search(r"[\w.-]+/([\w.:-]+)", meta)
    modelo = m_modelo.group(1) if m_modelo else "LLM"
    selo = f"{modelo}  ·  fidelidade {float(nota.group(1)):.0f}/100" if nota else modelo
    h = corpo.height + 72
    img = Image.new("RGB", (largura, h), FUNDO)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, largura - 1, h - 1], radius=22, fill=BRANCO, outline=LINHA, width=2)
    d.text((32, 18), "MedRoute · assistente", font=fonte("sans_bold", 21), fill=FAIXA)
    d.text((largura - 32, 18), selo, font=fm, fill=TEXTO_SUAVE, anchor="ra")
    img.paste(corpo, (32, 56))
    return img


def frames_chat(cena: Cena, etiqueta: str, n_frames: int, fps: int) -> Iterator[Image.Image]:
    base, d = _tela_base()
    _faixa_titulo(d, cena.titulo, etiqueta)
    _rodape(d, f"reports/llm/{cena.asset}  ·  respostas reais da LLM, com histórico da conversa")
    area = (MARGEM + 60, ALTURA_FAIXA + 30, LARGURA - MARGEM - 60, ALTURA - ALTURA_RODAPE - 16)
    larg = area[2] - area[0]
    itens: list[tuple[str, Image.Image]] = []
    for p, meta, r in _ler_conversa(cena.asset):
        itens.append(("u", _balao_usuario(p, int(larg * 0.62))))
        itens.append(("a", _balao_assistente(r, meta, int(larg * 0.86))))
    if not itens:
        yield from (base for _ in range(n_frames))
        return
    dur = n_frames / fps
    # Cada pergunta aparece e, 0,8 s depois, a resposta.
    janela_t = (dur * 0.92) / (len(itens) / 2)
    tempos = []
    for k in range(0, len(itens), 2):
        t = (k // 2) * janela_t + 0.3
        tempos += [t, t + 0.8]
    h_area = area[3] - area[1]
    ultimo, quadro = None, None
    for i in range(n_frames):
        t = i / fps
        n = sum(1 for tt in tempos if tt <= t)
        if n != ultimo:
            img = base.copy()
            alturas = [im.height + 22 for _, im in itens[:n]]
            total = sum(alturas)
            y = area[1] + min(0, h_area - total)
            for (quem, im), hh in zip(itens[:n], alturas):
                if y + im.height > area[1] - 400:
                    x = area[2] - im.width if quem == "u" else area[0]
                    img.paste(im, (int(x), int(y)))
                y += hh
            # o que passou do topo some sob a faixa do título
            dd = ImageDraw.Draw(img)
            dd.rectangle([0, 0, LARGURA, ALTURA_FAIXA + 5], fill=FAIXA)
            dd.rectangle([0, ALTURA_FAIXA, LARGURA, ALTURA_FAIXA + 5], fill=FAIXA_2)
            _faixa_titulo(dd, cena.titulo, etiqueta)
            dd.rectangle([0, ALTURA - ALTURA_RODAPE - 6, LARGURA, ALTURA], fill=FUNDO)
            _rodape(dd, f"reports/llm/{cena.asset}  ·  respostas reais da LLM, com histórico da conversa")
            quadro, ultimo = img, n
        yield quadro


# ---------------------------------------------------------------------------
# Evolução do GA
# ---------------------------------------------------------------------------
def frames_evolucao(cena: Cena, etiqueta: str, n_frames: int, fps: int) -> Iterator[Image.Image]:
    quadros = sorted(EVOLUCAO_DIR.glob("q_*.png"))
    if not quadros:
        img, d = _tela_base()
        _faixa_titulo(d, cena.titulo, etiqueta)
        _imagem_ausente(d, "quadros da evolução", "rode: python scripts/video/evolucao.py")
        yield from (img for _ in range(n_frames))
        return
    # Mais tempo nos primeiros quadros (onde a mudança é visível), o último fica parado.
    pesos = [1.0 + 1.5 * (1 - k / max(1, len(quadros) - 1)) for k in range(len(quadros))]
    pesos[-1] += 3.0
    total = sum(pesos)
    limites = []
    acc = 0.0
    for w in pesos:
        acc += w / total * n_frames
        limites.append(acc)
    cache: dict[int, Image.Image] = {}
    k = 0
    for i in range(n_frames):
        while k < len(limites) - 1 and i >= limites[k]:
            k += 1
        if k not in cache:
            cache.clear()
            cache[k] = Image.open(quadros[k]).convert("RGB").resize((LARGURA, ALTURA), Image.LANCZOS)
        yield cache[k]


# ---------------------------------------------------------------------------
# Despacho
# ---------------------------------------------------------------------------
_ANIMADOS = {Visual.TERMINAL, Visual.DOCUMENTO, Visual.CHAT, Visual.EVOLUCAO}


def eh_estatica(cena: Cena) -> bool:
    if cena.visual in _ANIMADOS:
        return False
    if cena.visual in (Visual.FIGURA, Visual.TELA) and cena.zoom:
        return False
    return True


def render_estatico(cena: Cena, etiqueta: str) -> Image.Image:
    if cena.visual is Visual.TITULO:
        return render_titulo(cena, etiqueta)
    if cena.visual is Visual.FIGURA:
        return render_figura(cena, etiqueta)[0]
    if cena.visual is Visual.TELA:
        return render_tela(cena, etiqueta)[0]
    if cena.visual is Visual.CODIGO:
        return render_codigo(cena, etiqueta)
    if cena.visual is Visual.ARVORE:
        return render_arvore(cena, etiqueta)
    raise ValueError(f"cena {cena.id} não é estática")


def frames(cena: Cena, etiqueta: str, n_frames: int, fps: int) -> Iterator[Image.Image]:
    if cena.visual is Visual.TERMINAL:
        return frames_terminal(cena, etiqueta, n_frames, fps)
    if cena.visual is Visual.DOCUMENTO:
        return frames_documento(cena, etiqueta, n_frames, fps)
    if cena.visual is Visual.CHAT:
        return frames_chat(cena, etiqueta, n_frames, fps)
    if cena.visual is Visual.EVOLUCAO:
        return frames_evolucao(cena, etiqueta, n_frames, fps)
    if cena.visual in (Visual.FIGURA, Visual.TELA):
        base, caixa = (render_figura if cena.visual is Visual.FIGURA else render_tela)(cena, etiqueta)
        if caixa is None or not cena.zoom:
            return iter([base] * n_frames)
        return frames_zoom(base, caixa, cena.zoom, n_frames, fps)
    raise ValueError(f"cena {cena.id} não é animada")


def render_primeiro_frame(cena: Cena, etiqueta: str) -> Image.Image:
    """Quadro representativo (modo --previa): o meio da animação."""
    if eh_estatica(cena):
        return render_estatico(cena, etiqueta)
    n = 30 * 20
    alvo = n // 2 if cena.visual is not Visual.TERMINAL else n - 1
    for i, q in enumerate(frames(cena, etiqueta, n, 30)):
        if i >= alvo:
            return q
    return q
