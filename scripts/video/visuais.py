"""
Renderização dos frames com Pillow — nada de browser/Selenium.

Cinco renderizadores, um por tipo de :class:`~roteiro.Visual`:

``titulo``
    Cartão estático: faixa azul-petróleo no topo, título grande, subtítulo e
    uma lista de tópicos. Combina com a identidade do PDF entregável.
``figura``
    Um PNG de ``reports/figures/`` centralizado num cartão branco, com título
    em cima e legenda embaixo. Redimensiona mantendo proporção.
``terminal``
    O único renderizador **animado**: janela de terminal escura em que o
    comando é digitado caractere a caractere e a saída real (capturada por
    ``captura.py``) aparece linha a linha ao longo da narração, com scroll
    quando passa do fim da janela.
``codigo``
    Trecho de um ``.py`` com números de linha e realce amarelo opcional.
``arvore``
    Árvore de arquivos real do projeto, em monoespaçada.

Decisão de desempenho: cenas estáticas devolvem **uma** imagem, e a montagem
pede ao ffmpeg para segurá-la pela duração (``-loop 1 -t``). Só o terminal
gera frame a frame, e mesmo assim com cache — frames consecutivos idênticos
não são redesenhados. Nenhum PNG intermediário vai para o disco.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from PIL import Image, ImageDraw, ImageFont

import captura
from roteiro import ALTURA, FIGURES_DIR, LARGURA, PROJECT_ROOT, Cena, Visual

# ---------------------------------------------------------------------------
# Paleta (alinhada ao PDF entregável)
# ---------------------------------------------------------------------------
FUNDO = "#f7f9fb"
AZUL_PETROLEO = "#1b4965"
AZUL_CLARO = "#5fa8d3"
AZUL_MEDIO = "#2c6e91"
TEXTO = "#1c2833"
TEXTO_SUAVE = "#5a6b78"
LINHA = "#d9e2e8"
BRANCO = "#ffffff"
DESTAQUE_FUNDO = "#fff3c4"
DESTAQUE_BORDA = "#e8c547"

TERM_FUNDO = "#1e1e1e"
TERM_BARRA = "#323233"
TERM_TEXTO = "#d4d4d4"
TERM_PROMPT = "#6ee787"
TERM_SECAO = "#4fc1ff"
TERM_ALERTA = "#f2cc60"

ALTURA_FAIXA = 96          # faixa de título no topo
MARGEM = 72
ALTURA_RODAPE = 54


# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------
def _dir_fontes_matplotlib() -> Path:
    """Pasta de fontes que vem junto do matplotlib (fallback multiplataforma)."""
    try:
        import matplotlib

        return Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    except Exception:  # pragma: no cover - matplotlib está no requirements
        return Path("/nonexistent")


_FONTES_WINDOWS = Path("C:/Windows/Fonts")

# Ordem de preferência: fonte do sistema -> fonte do matplotlib -> bitmap.
_CANDIDATAS = {
    "sans": [
        _FONTES_WINDOWS / "segoeui.ttf",
        _FONTES_WINDOWS / "arial.ttf",
        _dir_fontes_matplotlib() / "DejaVuSans.ttf",
    ],
    "sans_bold": [
        _FONTES_WINDOWS / "segoeuib.ttf",
        _FONTES_WINDOWS / "arialbd.ttf",
        _dir_fontes_matplotlib() / "DejaVuSans-Bold.ttf",
    ],
    "sans_semibold": [
        _FONTES_WINDOWS / "seguisb.ttf",
        _FONTES_WINDOWS / "segoeuib.ttf",
        _dir_fontes_matplotlib() / "DejaVuSans-Bold.ttf",
    ],
    "mono": [
        _FONTES_WINDOWS / "consola.ttf",
        _dir_fontes_matplotlib() / "DejaVuSansMono.ttf",
    ],
    "mono_bold": [
        _FONTES_WINDOWS / "consolab.ttf",
        _dir_fontes_matplotlib() / "DejaVuSansMono-Bold.ttf",
    ],
}


@functools.lru_cache(maxsize=256)
def fonte(familia: str, tamanho: int) -> ImageFont.FreeTypeFont:
    """Carrega uma fonte por família lógica, com fallback em cascata."""
    for caminho in _CANDIDATAS[familia]:
        try:
            if caminho.exists():
                return ImageFont.truetype(str(caminho), tamanho)
        except Exception:
            continue
    return ImageFont.load_default(size=tamanho)


def _largura(texto: str, f: ImageFont.FreeTypeFont) -> float:
    return f.getlength(texto)


def _avanco_mono(tamanho: int) -> float:
    """Largura de um caractere na monoespaçada (todas têm o mesmo avanço)."""
    return fonte("mono", tamanho).getlength("M")


# ---------------------------------------------------------------------------
# Blocos de desenho reutilizáveis
# ---------------------------------------------------------------------------
def _tela_base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (LARGURA, ALTURA), FUNDO)
    return img, ImageDraw.Draw(img)


def _faixa_titulo(d: ImageDraw.ImageDraw, titulo: str, etiqueta: str = "") -> None:
    """Faixa azul-petróleo no topo com o título da cena e a etiqueta do bloco."""
    d.rectangle([0, 0, LARGURA, ALTURA_FAIXA], fill=AZUL_PETROLEO)
    d.rectangle([0, ALTURA_FAIXA, LARGURA, ALTURA_FAIXA + 5], fill=AZUL_CLARO)

    f = fonte("sans_semibold", 40)
    # Encolhe o título se não couber (reserva espaço para a etiqueta).
    limite = LARGURA - 2 * MARGEM - (_largura(etiqueta, fonte("sans", 26)) + 48 if etiqueta else 0)
    tamanho = 40
    while _largura(titulo, f) > limite and tamanho > 22:
        tamanho -= 2
        f = fonte("sans_semibold", tamanho)
    d.text((MARGEM, ALTURA_FAIXA / 2), titulo, font=f, fill=BRANCO, anchor="lm")

    if etiqueta:
        fe = fonte("sans", 26)
        d.text(
            (LARGURA - MARGEM, ALTURA_FAIXA / 2),
            etiqueta,
            font=fe,
            fill="#a8cbe0",
            anchor="rm",
        )


def _rodape(d: ImageDraw.ImageDraw, texto: str) -> None:
    y = ALTURA - ALTURA_RODAPE
    d.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=LINHA, width=2)
    d.text(
        (MARGEM, y + ALTURA_RODAPE / 2 + 2),
        texto,
        font=fonte("sans", 22),
        fill=TEXTO_SUAVE,
        anchor="lm",
    )


def _quebrar(texto: str, f: ImageFont.FreeTypeFont, largura_max: float) -> list[str]:
    """Quebra de linha por palavra respeitando uma largura em pixels."""
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


# ---------------------------------------------------------------------------
# 1. Cartão de título
# ---------------------------------------------------------------------------
def render_titulo(cena: Cena, etiqueta: str) -> Image.Image:
    img, d = _tela_base()

    # Faixa decorativa lateral no lugar da faixa cheia: cartão de título tem
    # respiro maior, o que ajuda na leitura em tela cheia.
    d.rectangle([0, 0, 22, ALTURA], fill=AZUL_PETROLEO)
    d.rectangle([22, 0, 30, ALTURA], fill=AZUL_CLARO)

    x = MARGEM + 60
    largura_util = LARGURA - x - MARGEM

    if etiqueta:
        d.text((x, 118), etiqueta.upper(), font=fonte("sans_semibold", 26),
               fill=AZUL_CLARO, anchor="lm")

    # Título (encolhe até caber em duas linhas)
    tamanho = 78
    f = fonte("sans_bold", tamanho)
    while len(_quebrar(cena.titulo, f, largura_util)) > 2 and tamanho > 44:
        tamanho -= 4
        f = fonte("sans_bold", tamanho)
    linhas_titulo = _quebrar(cena.titulo, f, largura_util)

    y = 210
    for linha in linhas_titulo:
        d.text((x, y), linha, font=f, fill=AZUL_PETROLEO, anchor="lt")
        y += int(tamanho * 1.22)

    if cena.subtitulo:
        y += 14
        fs = fonte("sans", 40)
        for linha in _quebrar(cena.subtitulo, fs, largura_util):
            d.text((x, y), linha, font=fs, fill=TEXTO_SUAVE, anchor="lt")
            y += 54

    if cena.topicos:
        y += 46
        d.line([(x, y), (x + 200, y)], fill=AZUL_CLARO, width=5)
        y += 44
        ft = fonte("sans", 36)
        for topico in cena.topicos:
            if not topico.strip():          # linha em branco = respiro
                y += 26
                continue
            # Marcador só em tópicos que não começam com numeração própria.
            marcador = "" if topico[0].isdigit() else "•"
            if marcador:
                d.text((x + 6, y + 4), marcador, font=ft, fill=AZUL_CLARO, anchor="lt")
            for i, linha in enumerate(_quebrar(topico, ft, largura_util - 46)):
                d.text((x + 46, y), linha, font=ft, fill=TEXTO, anchor="lt")
                y += 50
            y += 12

    _rodape(d, "Tech Challenge — Fase 1  ·  Sistema de suporte ao diagnóstico")
    return img


# ---------------------------------------------------------------------------
# 2. Figura
# ---------------------------------------------------------------------------
def render_figura(cena: Cena, etiqueta: str) -> Image.Image:
    img, d = _tela_base()
    _faixa_titulo(d, cena.titulo or Path(cena.asset).stem, etiqueta)

    caminho = FIGURES_DIR / cena.asset
    topo = ALTURA_FAIXA + 40
    base = ALTURA - ALTURA_RODAPE - (74 if cena.legenda else 24)
    # A moldura branca cresce `pad` px além da imagem em cada lado, então a
    # área disponível para a imagem em si é menor que a área útil da tela —
    # sem descontar isso, o cartão invade a legenda.
    pad = 18
    area_w = LARGURA - 2 * MARGEM - 2 * pad
    area_h = (base - topo) - 2 * pad

    if not caminho.exists():
        d.text(
            (LARGURA / 2, ALTURA / 2),
            f"[figura ausente: {cena.asset}]\nRode: python main.py",
            font=fonte("mono", 34), fill="#b03a2e", anchor="mm", align="center",
        )
        _rodape(d, cena.legenda or "")
        return img

    figura = Image.open(caminho).convert("RGB")
    # Escala mantendo proporção; permite ampliar figuras pequenas (a maioria
    # tem ~500-900 px) até 2,4x, o que ainda fica nítido em 1080p.
    escala = min(area_w / figura.width, area_h / figura.height, 2.4)
    novo = (max(1, int(figura.width * escala)), max(1, int(figura.height * escala)))
    figura = figura.resize(novo, Image.LANCZOS)

    px = int((LARGURA - novo[0]) / 2)
    py = topo + pad + int((area_h - novo[1]) / 2)

    # Cartão branco com uma sombra discreta atrás da imagem.
    d.rounded_rectangle(
        [px - pad + 6, py - pad + 8, px + novo[0] + pad + 6, py + novo[1] + pad + 8],
        radius=14, fill="#e3eaee",
    )
    d.rounded_rectangle(
        [px - pad, py - pad, px + novo[0] + pad, py + novo[1] + pad],
        radius=14, fill=BRANCO, outline=LINHA, width=2,
    )
    img.paste(figura, (px, py))

    if cena.legenda:
        fl = fonte("sans", 28)
        y = base + 16
        for linha in _quebrar(cena.legenda, fl, LARGURA - 2 * MARGEM):
            d.text((LARGURA / 2, y), linha, font=fl, fill=TEXTO_SUAVE, anchor="mt")
            y += 36

    _rodape(d, f"reports/figures/{cena.asset}")
    return img


# ---------------------------------------------------------------------------
# 3. Código
# ---------------------------------------------------------------------------
def render_codigo(cena: Cena, etiqueta: str) -> Image.Image:
    img, d = _tela_base()
    _faixa_titulo(d, cena.titulo or cena.asset, etiqueta)

    caminho = PROJECT_ROOT / cena.asset
    if not caminho.exists():
        d.text((LARGURA / 2, ALTURA / 2), f"[arquivo ausente: {cena.asset}]",
               font=fonte("mono", 34), fill="#b03a2e", anchor="mm")
        return img

    todas = caminho.read_text(encoding="utf-8").splitlines()
    ini = (cena.linha_inicial or 1) - 1
    fim = cena.linha_final or len(todas)
    trecho = todas[ini:fim]
    numeros = list(range(ini + 1, ini + 1 + len(trecho)))

    topo = ALTURA_FAIXA + 40
    base = ALTURA - ALTURA_RODAPE - 24
    largura_cartao = LARGURA - 2 * MARGEM

    # Auto-ajuste do tamanho da fonte: precisa caber em altura E em largura.
    gutter = 96
    tamanho = 32
    while tamanho > 15:
        f = fonte("mono", tamanho)
        alt_linha = int(tamanho * 1.55)
        cabe_altura = len(trecho) * alt_linha + 56 <= base - topo
        mais_larga = max((_largura(l, f) for l in trecho), default=0)
        cabe_largura = mais_larga + gutter + 60 <= largura_cartao
        if cabe_altura and cabe_largura:
            break
        tamanho -= 1
    f = fonte("mono", tamanho)
    alt_linha = int(tamanho * 1.55)

    altura_cartao = len(trecho) * alt_linha + 56
    cy = topo + max(0, ((base - topo) - altura_cartao) // 2)

    d.rounded_rectangle(
        [MARGEM + 6, cy + 8, MARGEM + largura_cartao + 6, cy + altura_cartao + 8],
        radius=12, fill="#e3eaee",
    )
    d.rounded_rectangle(
        [MARGEM, cy, MARGEM + largura_cartao, cy + altura_cartao],
        radius=12, fill=BRANCO, outline=LINHA, width=2,
    )
    # Calha dos números de linha.
    d.rectangle([MARGEM + 2, cy + 2, MARGEM + gutter, cy + altura_cartao - 2],
                fill="#eef3f6")
    d.line([(MARGEM + gutter, cy + 2), (MARGEM + gutter, cy + altura_cartao - 2)],
           fill=LINHA, width=2)

    destaque = set(cena.destaque)
    y = cy + 28
    for numero, linha in zip(numeros, trecho):
        if numero in destaque:
            d.rectangle(
                [MARGEM + gutter + 2, y - 3,
                 MARGEM + largura_cartao - 3, y + alt_linha - 4],
                fill=DESTAQUE_FUNDO,
            )
            d.rectangle(
                [MARGEM + gutter + 2, y - 3, MARGEM + gutter + 7, y + alt_linha - 4],
                fill=DESTAQUE_BORDA,
            )
        d.text((MARGEM + gutter - 16, y), str(numero), font=f,
               fill="#9aa9b4", anchor="rt")
        cor = "#4a6572" if linha.lstrip().startswith("#") else TEXTO
        d.text((MARGEM + gutter + 22, y), linha, font=f, fill=cor, anchor="lt")
        y += alt_linha

    _rodape(d, f"{cena.asset}  ·  linhas {numeros[0]}–{numeros[-1]}" if numeros else cena.asset)
    return img


# ---------------------------------------------------------------------------
# 4. Árvore de arquivos
# ---------------------------------------------------------------------------
_IGNORAR_DIRS = {
    ".venv", "venv", "__pycache__", ".git", ".pytest_cache", ".ipynb_checkpoints",
    ".idea", ".vscode", "_cache", "breastmnist", "figures",
    # A pasta do próprio gerador e a saída dele não fazem parte do projeto
    # que o vídeo apresenta — listá-las só polui a tela.
    "video", "clipes", "previa",
}
_IGNORAR_ARQUIVOS = {".gitkeep", ".DS_Store", "Thumbs.db"}

# Pastas mostradas fechadas: são artefatos gerados, e o conteúdo delas não
# acrescenta nada à explicação da arquitetura (além de estourar a tela).
_COLAPSAR = {"data", "docs", "models", "reports"}


def _arvore_texto(raiz: Path = PROJECT_ROOT, max_arquivos: int = 9) -> list[str]:
    """Monta a árvore real do projeto (filtrando ruído) como linhas de texto."""
    linhas = [f"{raiz.name}/"]

    def caminhar(base: Path, prefixo: str, nivel: int) -> None:
        if nivel > 2:
            return
        try:
            itens = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return
        dirs = [p for p in itens if p.is_dir() and p.name not in _IGNORAR_DIRS
                and not p.name.startswith(".")]
        arqs = [p for p in itens if p.is_file() and p.name not in _IGNORAR_ARQUIVOS
                and not p.name.startswith(".")]
        if len(arqs) > max_arquivos:
            arqs = arqs[:max_arquivos] + [None]  # type: ignore[list-item]

        visiveis: list[Path | None] = [*dirs, *arqs]
        for i, item in enumerate(visiveis):
            ultimo = i == len(visiveis) - 1
            conector = "└── " if ultimo else "├── "
            if item is None:
                linhas.append(f"{prefixo}{conector}...")
                continue
            if item.is_dir():
                if item.name in _COLAPSAR:
                    n = sum(1 for _ in item.iterdir())
                    plural = "item" if n == 1 else "itens"
                    linhas.append(f"{prefixo}{conector}{item.name}/  ({n} {plural})")
                    continue
                linhas.append(f"{prefixo}{conector}{item.name}/")
                caminhar(item, prefixo + ("    " if ultimo else "│   "), nivel + 1)
            else:
                linhas.append(f"{prefixo}{conector}{item.name}")

    caminhar(raiz, "", 0)
    return linhas


# Comentários didáticos ao lado das entradas principais (o que a narração fala).
_COMENTARIOS_ARVORE = {
    "config.py": "caminhos, semente, convenção 1 = maligno",
    "data_loader.py": "carrega e remapeia o alvo",
    "preprocessing.py": "limpeza, imputação, split estratificado",
    "eda.py": "análise exploratória e figuras 01–03",
    "modeling.py": "os 4 classificadores (Pipeline + CV)",
    "evaluation.py": "métricas, matriz de confusão, ROC",
    "explainability.py": "feature importance + SHAP",
    "vision.py": "EXTRA: CNN, limiar clínico, Grad-CAM",
    "main.py": "orquestra o pipeline tabular",
    "main_vision.py": "orquestra o pipeline de imagem",
    "test_pipeline.py": "12 testes do pipeline tabular",
    "test_vision.py": "7 testes da CNN",
    "Dockerfile": "roda sem instalar nada",
    "README.md": "documentação e discussão crítica",
}


def render_arvore(cena: Cena, etiqueta: str) -> Image.Image:
    img, d = _tela_base()
    _faixa_titulo(d, cena.titulo or "Arquitetura do projeto", etiqueta)

    linhas = _arvore_texto()
    topo = ALTURA_FAIXA + 34
    base = ALTURA - ALTURA_RODAPE - 20
    disponivel = base - topo

    tamanho = 30
    while tamanho > 13 and len(linhas) * int(tamanho * 1.5) + 48 > disponivel:
        tamanho -= 1
    alt_linha = int(tamanho * 1.5)

    # Trava dura: se nem no menor corpo couber, trunca a lista de forma
    # explícita em vez de deixar o texto atravessar o rodapé.
    cabem = max(1, (disponivel - 48) // alt_linha)
    if len(linhas) > cabem:
        linhas = linhas[:cabem - 1] + ["..."]

    f = fonte("mono", tamanho)
    fc = fonte("mono", max(12, tamanho - 4))

    largura_cartao = LARGURA - 2 * MARGEM
    altura_cartao = len(linhas) * alt_linha + 48
    cy = topo + max(0, (disponivel - altura_cartao) // 2)
    d.rounded_rectangle(
        [MARGEM, cy, MARGEM + largura_cartao, cy + altura_cartao],
        radius=12, fill=BRANCO, outline=LINHA, width=2,
    )

    # Coluna dos comentários logo depois da linha mais longa da árvore.
    largura_char = _avanco_mono(tamanho)
    mais_longa = max(len(l) for l in linhas)
    col_comentario = min(
        MARGEM + 28 + int((mais_longa + 4) * largura_char),
        MARGEM + largura_cartao - 480,
    )
    y = cy + 24
    for linha in linhas:
        nome = linha.split("── ")[-1].rstrip("/")
        eh_dir = linha.rstrip().endswith("/")
        cor = AZUL_PETROLEO if eh_dir else TEXTO
        d.text((MARGEM + 28, y), linha, font=f, fill=cor, anchor="lt")
        comentario = _COMENTARIOS_ARVORE.get(nome)
        if comentario:
            d.text((col_comentario, y + 2), f"# {comentario}", font=fc,
                   fill=AZUL_MEDIO, anchor="lt")
        y += alt_linha

    _rodape(d, "Pacote Python reutilizável — não é um notebook solto")
    return img


# ---------------------------------------------------------------------------
# 5. Terminal (animado)
# ---------------------------------------------------------------------------
@dataclass
class _PlanoTerminal:
    """Pré-cálculo do layout e do conteúdo de uma cena de terminal."""

    comando: str
    arquivo: str
    linhas: list[str]
    tamanho_fonte: int
    linhas_visiveis: int
    caixa: tuple[int, int, int, int]  # x0, y0, x1, y1 da janela


def _recortar(linhas: list[str], cena: Cena) -> list[str]:
    """Aplica o recorte da cena: por marcador de conteúdo ou por linha."""
    ini, fim = 0, len(linhas)

    if cena.marcador_inicio:
        for i, linha in enumerate(linhas):
            if cena.marcador_inicio in linha:
                # Sobe até a régua de '=' que abre a seção, se houver.
                ini = i - 1 if i > 0 and set(linhas[i - 1].strip()) == {"="} else i
                break
    elif cena.linha_inicial:
        ini = cena.linha_inicial - 1

    if cena.marcador_fim:
        for j in range(ini + 1, len(linhas)):
            if cena.marcador_fim in linhas[j]:
                fim = j - 1 if set(linhas[j - 1].strip()) == {"="} else j
                break
    elif cena.linha_final:
        fim = cena.linha_final

    recorte = linhas[ini:fim]
    # Remove linhas em branco nas pontas (o pipeline imprime \n antes de cada seção).
    while recorte and not recorte[0].strip():
        recorte.pop(0)
    while recorte and not recorte[-1].strip():
        recorte.pop()

    # Elisão explícita do miolo: usada no pytest, cujo bloco de "warnings"
    # ocupa metade da tela sem dizer nada. O marcador [...] deixa claro que
    # há saída omitida — nada é reescrito nem inventado.
    if cena.linhas_finais:
        finais = [l for l in linhas[-cena.linhas_finais:] if l.strip()]
        if finais and finais[-1] not in recorte:
            recorte += ["", "  [...]", ""] + finais
    return recorte


def _planejar_terminal(cena: Cena) -> _PlanoTerminal:
    linhas = _recortar(captura.ler_captura(cena.asset), cena)
    cmd = captura.COMANDOS[cena.asset].rotulo
    arquivo = captura.caminho_captura(cena.asset).name

    x0, y0 = MARGEM, ALTURA_FAIXA + 44
    x1, y1 = LARGURA - MARGEM, ALTURA - ALTURA_RODAPE - 24
    pad_x, barra = 30, 46
    largura_texto = (x1 - x0) - 2 * pad_x
    altura_texto = (y1 - y0) - barra - 32

    # Escolhe o maior corpo que faça a linha mais longa caber sem quebrar.
    mais_longa = max((len(l) for l in linhas), default=0)
    mais_longa = max(mais_longa, len(cmd) + 30)
    tamanho = 28
    while tamanho > 13 and _avanco_mono(tamanho) * mais_longa > largura_texto:
        tamanho -= 1

    alt_linha = int(tamanho * 1.45)
    visiveis = max(6, altura_texto // alt_linha)

    # Se a saída é curta, a janela encolhe até o conteúdo em vez de deixar
    # meia tela de preto vazio — e fica centralizada verticalmente.
    necessarias = len(linhas) + 2                    # + prompt + respiro
    if necessarias < visiveis:
        visiveis = max(8, necessarias)
        altura_janela = barra + 32 + visiveis * alt_linha
        folga = (y1 - y0) - altura_janela
        y0 += folga // 2
        y1 = y0 + altura_janela

    return _PlanoTerminal(cmd, arquivo, linhas, tamanho, visiveis, (x0, y0, x1, y1))


def _cor_linha_terminal(linha: str) -> str:
    """Colore a saída para dar hierarquia visual — sem alterar o texto.

    Réguas e cabeçalhos de seção em azul, sinais de sucesso em verde, o
    destaque dos falsos negativos em amarelo, o resto em cinza claro.
    """
    limpa = linha.strip()
    if not limpa:
        return TERM_TEXTO
    if set(limpa) == {"="} or limpa.startswith("===") or limpa.startswith("---"):
        return TERM_SECAO
    # "1. CARREGAMENTO DOS DADOS", "5. AVALIAÇÃO NO CONJUNTO DE TESTE", ...
    if limpa[0].isdigit() and ". " in limpa[:4] and limpa == limpa.upper():
        return TERM_SECAO
    if "PASSED" in linha or "passed" in limpa:
        return TERM_PROMPT
    if limpa.startswith("->") or "falso" in limpa.lower() or "Melhor modelo" in limpa:
        return TERM_ALERTA
    return TERM_TEXTO


def _desenhar_terminal(
    plano: _PlanoTerminal, n_chars_cmd: int, n_linhas: int, cursor: bool,
    titulo_cena: str, etiqueta: str,
) -> Image.Image:
    img, d = _tela_base()
    _faixa_titulo(d, titulo_cena, etiqueta)

    x0, y0, x1, y1 = plano.caixa
    barra = 46

    # Sombra + janela.
    d.rounded_rectangle([x0 + 6, y0 + 8, x1 + 6, y1 + 8], radius=14, fill="#dde5ea")
    d.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=TERM_FUNDO)
    d.rounded_rectangle([x0, y0, x1, y0 + barra], radius=14, fill=TERM_BARRA)
    d.rectangle([x0, y0 + barra - 14, x1, y0 + barra], fill=TERM_BARRA)

    # Três bolinhas.
    for i, cor in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        cx = x0 + 28 + i * 26
        d.ellipse([cx - 8, y0 + barra / 2 - 8, cx + 8, y0 + barra / 2 + 8], fill=cor)
    d.text((x0 + (x1 - x0) / 2, y0 + barra / 2), "Windows PowerShell — Tech_Challenge",
           font=fonte("sans", 22), fill="#9aa3ab", anchor="mm")

    f = fonte("mono", plano.tamanho_fonte)
    alt_linha = int(plano.tamanho_fonte * 1.45)
    tx = x0 + 30
    ty = y0 + barra + 18

    # Linha do prompt com o comando sendo digitado.
    prompt = "PS C:\\Tech_Challenge-main> "
    d.text((tx, ty), prompt, font=f, fill=TERM_PROMPT, anchor="lt")
    largura_prompt = _avanco_mono(plano.tamanho_fonte) * len(prompt)
    digitado = plano.comando[:n_chars_cmd]
    d.text((tx + largura_prompt, ty), digitado, font=f, fill=BRANCO, anchor="lt")
    if cursor:
        cx = tx + largura_prompt + _avanco_mono(plano.tamanho_fonte) * len(digitado)
        d.rectangle([cx, ty + 2, cx + _avanco_mono(plano.tamanho_fonte) * 0.85,
                     ty + alt_linha - 6], fill="#cccccc")
    ty += alt_linha + 6

    # Saída, com scroll: mostra a janela que termina na última linha revelada.
    visiveis = plano.linhas_visiveis - 2
    reveladas = plano.linhas[:n_linhas]
    if len(reveladas) > visiveis:
        reveladas = reveladas[len(reveladas) - visiveis:]
    for linha in reveladas:
        d.text((tx, ty), linha, font=f, fill=_cor_linha_terminal(linha), anchor="lt")
        ty += alt_linha

    _rodape(d, f"saída real de `{plano.comando}`  ·  capturada em "
               f"scripts/video/_cache/{plano.arquivo}")
    return img


def frames_terminal(
    cena: Cena, etiqueta: str, n_frames: int, fps: int,
) -> Iterator[Image.Image]:
    """Gera os frames da animação de digitação de uma cena de terminal.

    Linha do tempo, em fração da duração da cena:

    * 0 → 22 % (no máx. 1,6 s): o comando é digitado caractere a caractere;
    * pequena pausa (o "Enter");
    * até 92 %: as linhas da saída aparecem progressivamente;
    * 92 % → 100 %: a tela final fica parada, para dar tempo de ler.

    Frames idênticos são desenhados uma vez só e reaproveitados.
    """
    plano = _planejar_terminal(cena)
    duracao = n_frames / fps

    fim_digitacao = min(1.6, duracao * 0.22)
    inicio_saida = fim_digitacao + min(0.35, duracao * 0.05)
    fim_saida = max(inicio_saida + 0.1, duracao * 0.92)

    cache: dict[tuple[int, int, bool], Image.Image] = {}
    total_linhas = len(plano.linhas)

    for i in range(n_frames):
        t = i / fps
        if t < fim_digitacao:
            n_chars = int(len(plano.comando) * (t / fim_digitacao)) if fim_digitacao else len(plano.comando)
            n_linhas = 0
        else:
            n_chars = len(plano.comando)
            if t <= inicio_saida:
                n_linhas = 0
            else:
                prog = min(1.0, (t - inicio_saida) / (fim_saida - inicio_saida))
                n_linhas = int(round(total_linhas * prog))

        # Cursor piscando só enquanto digita (2 Hz).
        cursor = t < inicio_saida and int(t * 2) % 2 == 0
        chave = (n_chars, n_linhas, cursor)
        if chave not in cache:
            if len(cache) > 220:            # trava de memória
                cache.clear()
            cache[chave] = _desenhar_terminal(
                plano, n_chars, n_linhas, cursor, cena.titulo, etiqueta
            )
        yield cache[chave]


# ---------------------------------------------------------------------------
# Despacho
# ---------------------------------------------------------------------------
def eh_estatica(cena: Cena) -> bool:
    """Cenas estáticas viram uma imagem só; o ffmpeg segura pela duração."""
    return cena.visual is not Visual.TERMINAL


def render_estatico(cena: Cena, etiqueta: str) -> Image.Image:
    """Renderiza o frame único de uma cena estática."""
    if cena.visual is Visual.TITULO:
        return render_titulo(cena, etiqueta)
    if cena.visual is Visual.FIGURA:
        return render_figura(cena, etiqueta)
    if cena.visual is Visual.CODIGO:
        return render_codigo(cena, etiqueta)
    if cena.visual is Visual.ARVORE:
        return render_arvore(cena, etiqueta)
    raise ValueError(f"Cena {cena.id} não é estática ({cena.visual}).")


def render_primeiro_frame(cena: Cena, etiqueta: str) -> Image.Image:
    """Um frame representativo da cena — usado pelo modo ``--previa``."""
    if eh_estatica(cena):
        return render_estatico(cena, etiqueta)
    plano = _planejar_terminal(cena)
    return _desenhar_terminal(
        plano, len(plano.comando), len(plano.linhas), False, cena.titulo, etiqueta
    )
