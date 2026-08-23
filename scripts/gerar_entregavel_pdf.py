"""
Gera o PDF entregável do Tech Challenge — Fase 1.

O PDF consolida tudo que o enunciado pede em um único arquivo:
    * link do repositório Git e do vídeo
    * mapa do código-fonte completo
    * instruções de execução (local e Docker)
    * dataset (origem e link)
    * resultados obtidos (tabelas + todas as figuras geradas)
    * relatório técnico (EDA, pré-processamento, modelos, interpretação)
    * roteiro do vídeo de demonstração

As tabelas de métricas são lidas de ``reports/*.csv``, então o PDF fica sempre
sincronizado com a última execução de ``main.py``.

Uso:
    python scripts/gerar_entregavel_pdf.py
    python scripts/gerar_entregavel_pdf.py --repo https://github.com/user/repo \
                                           --video https://youtu.be/xxxx \
                                           --autores "Fulano, Ciclano"
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------------- #
# Caminhos e constantes
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIGURES = PROJECT_ROOT / "reports" / "figures"
REPORTS = PROJECT_ROOT / "reports"
OUTPUT = PROJECT_ROOT / "Tech_Challenge_Fase1_Entregavel.pdf"

PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

AZUL = colors.HexColor("#1b4965")
AZUL_CLARO = colors.HexColor("#cfe3ee")
VERDE = colors.HexColor("#2f7d4f")
VERMELHO = colors.HexColor("#a83232")
CINZA = colors.HexColor("#555555")
CINZA_CLARO = colors.HexColor("#f2f4f6")

PLACEHOLDER_REPO = "https://github.com/SEU-USUARIO/SEU-REPOSITORIO"
PLACEHOLDER_VIDEO = "https://youtu.be/SEU-VIDEO"


# --------------------------------------------------------------------------- #
# Estilos
# --------------------------------------------------------------------------- #
def build_styles() -> dict:
    base = getSampleStyleSheet()
    s = {}

    s["titulo_capa"] = ParagraphStyle(
        "titulo_capa", parent=base["Title"], fontSize=26, leading=31,
        textColor=AZUL, spaceAfter=10,
    )
    s["sub_capa"] = ParagraphStyle(
        "sub_capa", parent=base["Normal"], fontSize=14, leading=20,
        alignment=TA_CENTER, textColor=CINZA,
    )
    s["h1"] = ParagraphStyle(
        "h1", parent=base["Heading1"], fontSize=16, leading=20, textColor=AZUL,
        spaceBefore=16, spaceAfter=8,
    )
    s["h2"] = ParagraphStyle(
        "h2", parent=base["Heading2"], fontSize=12.5, leading=16, textColor=AZUL,
        spaceBefore=12, spaceAfter=5,
    )
    s["h3"] = ParagraphStyle(
        "h3", parent=base["Heading3"], fontSize=11, leading=14,
        textColor=colors.HexColor("#333333"), spaceBefore=9, spaceAfter=4,
    )
    s["corpo"] = ParagraphStyle(
        "corpo", parent=base["BodyText"], fontSize=9.6, leading=14.2,
        alignment=TA_JUSTIFY, spaceAfter=6,
    )
    s["bullet"] = ParagraphStyle(
        "bullet", parent=s["corpo"], leftIndent=14, bulletIndent=4, spaceAfter=3,
    )
    s["legenda"] = ParagraphStyle(
        "legenda", parent=base["Normal"], fontSize=8.3, leading=11.5,
        alignment=TA_CENTER, textColor=CINZA, spaceBefore=3, spaceAfter=10,
    )
    s["celula"] = ParagraphStyle(
        "celula", parent=base["Normal"], fontSize=8.2, leading=10.8,
    )
    s["celula_cab"] = ParagraphStyle(
        "celula_cab", parent=base["Normal"], fontSize=8.2, leading=10.8,
        textColor=colors.white, fontName="Helvetica-Bold",
    )
    s["codigo"] = ParagraphStyle(
        "codigo", parent=base["Code"], fontSize=8.2, leading=11.4,
        backColor=CINZA_CLARO, borderPadding=6, leftIndent=4, spaceAfter=8,
        textColor=colors.HexColor("#1a1a1a"),
    )
    s["destaque"] = ParagraphStyle(
        "destaque", parent=s["corpo"], backColor=colors.HexColor("#fff6e0"),
        borderColor=colors.HexColor("#e0a800"), borderWidth=0.8, borderPadding=8,
        spaceBefore=6, spaceAfter=10,
    )
    s["nota"] = ParagraphStyle(
        "nota", parent=s["corpo"], backColor=AZUL_CLARO,
        borderColor=AZUL, borderWidth=0.8, borderPadding=8,
        spaceBefore=6, spaceAfter=10,
    )
    return s


# --------------------------------------------------------------------------- #
# Helpers de conteúdo
# --------------------------------------------------------------------------- #
def p(text: str, st) -> Paragraph:
    return Paragraph(text, st)


def bullets(items: list[str], st) -> list:
    return [Paragraph(t, st["bullet"], bulletText="•") for t in items]


def figura(nome: str, legenda: str, st, largura: float = CONTENT_W) -> list:
    """Insere uma figura ajustada à largura útil, com legenda."""
    caminho = FIGURES / nome
    if not caminho.exists():
        return [p(f"<i>[figura ausente: {nome} — rode <b>python main.py</b> "
                 f"e <b>python main_vision.py</b>]</i>", st["legenda"])]

    from PIL import Image as PILImage

    with PILImage.open(caminho) as im:
        w, h = im.size
    escala = largura / w
    altura = h * escala
    # Nenhuma figura pode ultrapassar ~60% da altura útil da página.
    max_h = (PAGE_H - 2 * MARGIN) * 0.62
    if altura > max_h:
        escala = max_h / h
        largura = w * escala
        altura = max_h

    img = Image(str(caminho), width=largura, height=altura)
    img.hAlign = "CENTER"
    return [KeepTogether([img, p(legenda, st["legenda"])])]


def tabela(dados: list[list], st, larguras=None, destaque_linha: int | None = None,
           align_num: bool = True) -> Table:
    """Tabela com cabeçalho azul e zebra."""
    corpo = []
    for i, linha in enumerate(dados):
        estilo = st["celula_cab"] if i == 0 else st["celula"]
        corpo.append([Paragraph(str(c), estilo) for c in linha])

    t = Table(corpo, colWidths=larguras, repeatRows=1, hAlign="CENTER")
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8cfd6")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(dados)):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), CINZA_CLARO))
    if align_num and len(dados[0]) > 2:
        cmds.append(("ALIGN", (1, 1), (-1, -1), "CENTER"))
    if destaque_linha is not None:
        cmds.append(("BACKGROUND", (0, destaque_linha), (-1, destaque_linha),
                     colors.HexColor("#d8f0e0")))
        cmds.append(("LINEBELOW", (0, destaque_linha), (-1, destaque_linha), 1.0, VERDE))
        cmds.append(("LINEABOVE", (0, destaque_linha), (-1, destaque_linha), 1.0, VERDE))
    t.setStyle(TableStyle(cmds))
    return t


def url_clone(repo: str) -> str:
    """URL canônica de clone: garante o sufixo .git sem duplicá-lo."""
    return repo if repo.endswith(".git") else f"{repo.rstrip('/')}.git"


def nome_repo(repo: str) -> str:
    """Nome da pasta criada pelo clone (último segmento da URL, sem .git)."""
    return repo.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git") or "Tech_Challenge"


def num(valor: float, casas: int = 3) -> str:
    """Formata número com vírgula decimal (padrão brasileiro)."""
    return f"{valor:.{casas}f}".replace(".", ",")


def bloco_codigo(texto: str, st) -> Paragraph:
    esc = (texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
           .replace("\n", "<br/>").replace(" ", "&nbsp;"))
    return Paragraph(esc, st["codigo"])


# --------------------------------------------------------------------------- #
# Dados dinâmicos (lidos dos CSVs gerados pelo pipeline)
# --------------------------------------------------------------------------- #
def tabela_metricas_teste(st):
    caminho = REPORTS / "metricas_teste.csv"
    if not caminho.exists():
        return p("<i>[reports/metricas_teste.csv ausente — rode python main.py]</i>",
                 st["corpo"]), None

    df = pd.read_csv(caminho).set_index("modelo")
    df = df.sort_values("recall", ascending=False)
    cab = ["Modelo", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC"]
    linhas = [cab]
    for nome, r in df.iterrows():
        campeao = nome == df.index[0]
        linhas.append([
            f"<b>{nome}</b>" if campeao else nome,
            num(r["accuracy"]), num(r["precision"]),
            f"<b>{num(r['recall'])}</b>" if campeao else num(r["recall"]),
            num(r["f1"]), num(r["roc_auc"]),
        ])
    larguras = [5.4 * cm] + [2.32 * cm] * 5
    return tabela(linhas, st, larguras, destaque_linha=1), df


def tabela_metricas_cv(st):
    caminho = REPORTS / "metricas_validacao_cruzada.csv"
    if not caminho.exists():
        return p("<i>[reports/metricas_validacao_cruzada.csv ausente]</i>", st["corpo"])

    df = pd.read_csv(caminho).set_index("modelo").sort_values(
        "recall_media", ascending=False)
    cab = ["Modelo", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC"]
    linhas = [cab]
    for nome, r in df.iterrows():
        linhas.append([
            nome,
            f"{num(r['accuracy_media'])} ± {num(r['accuracy_desvio'])}",
            f"{num(r['precision_media'])} ± {num(r['precision_desvio'])}",
            f"{num(r['recall_media'])} ± {num(r['recall_desvio'])}",
            f"{num(r['f1_media'])} ± {num(r['f1_desvio'])}",
            f"{num(r['roc_auc_media'])} ± {num(r['roc_auc_desvio'])}",
        ])
    larguras = [4.0 * cm] + [2.6 * cm] * 5
    return tabela(linhas, st, larguras)


# --------------------------------------------------------------------------- #
# Cabeçalho / rodapé
# --------------------------------------------------------------------------- #
def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d5dbe0"))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, MARGIN - 0.45 * cm, PAGE_W - MARGIN, MARGIN - 0.45 * cm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(CINZA)
    canvas.drawString(MARGIN, MARGIN - 0.95 * cm,
                      "Tech Challenge — Fase 1 · Sistema de suporte ao diagnóstico em saúde da mulher")
    canvas.drawRightString(PAGE_W - MARGIN, MARGIN - 0.95 * cm, f"{doc.page}")
    canvas.restoreState()


def _capa_fundo(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(AZUL)
    canvas.rect(0, PAGE_H - 4.2 * cm, PAGE_W, 4.2 * cm, stroke=0, fill=1)
    canvas.setFillColor(AZUL_CLARO)
    canvas.rect(0, 0, PAGE_W, 1.4 * cm, stroke=0, fill=1)
    canvas.restoreState()


# --------------------------------------------------------------------------- #
# Documento
# --------------------------------------------------------------------------- #
def build(repo: str, video: str, autores: str, turma: str) -> Path:
    st = build_styles()

    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN + 0.4 * cm,
        title="Tech Challenge Fase 1 — Entregável",
        author=autores,
        subject="Sistema inteligente de suporte ao diagnóstico em saúde da mulher",
    )
    frame = Frame(MARGIN, MARGIN + 0.4 * cm, CONTENT_W,
                  PAGE_H - 2 * MARGIN - 0.4 * cm, id="corpo")
    doc.addPageTemplates([
        PageTemplate(id="capa", frames=[frame], onPage=_capa_fundo),
        PageTemplate(id="normal", frames=[frame], onPage=_rodape),
    ])

    S = []  # story

    # ===================================================================== CAPA
    S.append(Spacer(1, 3.4 * cm))
    S.append(p("TECH CHALLENGE — FASE 1", st["titulo_capa"]))
    S.append(p("Sistema inteligente de suporte ao diagnóstico<br/>"
               "e detecção de riscos em saúde da mulher", st["sub_capa"]))
    S.append(Spacer(1, 0.9 * cm))
    S.append(p("<font color='#a83232'><b>Detecção precoce de câncer de mama</b></font><br/>"
               "Machine Learning sobre dados de exame (tabular)<br/>"
               "+ Visão Computacional sobre imagens de ultrassom (CNN)", st["sub_capa"]))
    S.append(Spacer(1, 1.6 * cm))

    ident = [
        ["Item", "Conteúdo"],
        ["Autor(es)", autores],
        ["Turma / Fase", turma],
        ["Repositório Git", f"<link href='{repo}' color='#1b4965'>{repo}</link>"],
        ["Vídeo (YouTube)", f"<link href='{video}' color='#1b4965'>{video}</link>"],
        ["Dataset principal", "Breast Cancer Wisconsin (Diagnostic) — UCI / scikit-learn"],
        ["Dataset EXTRA", "BreastMNIST (ultrassom de mama, derivado do BUSI) — medmnist / Zenodo"],
        ["Stack", "Python 3.11 · scikit-learn · pandas · SHAP · PyTorch · Docker"],
    ]
    S.append(tabela(ident, st, [4.2 * cm, CONTENT_W - 4.2 * cm], align_num=False))
    S.append(Spacer(1, 0.8 * cm))

    if repo == PLACEHOLDER_REPO or video == PLACEHOLDER_VIDEO:
        S.append(p(
            "<b>Atenção:</b> os campos de <b>repositório</b> e/ou <b>vídeo</b> ainda "
            "estão com o valor de exemplo. Regere este PDF com os links reais antes "
            "de entregar:<br/><br/>"
            "<font face='Courier'>python scripts/gerar_entregavel_pdf.py "
            "--repo &lt;URL&gt; --video &lt;URL&gt; --autores \"Nome\"</font>",
            st["destaque"]))

    S.append(NextPageTemplate("normal"))
    S.append(PageBreak())

    # ================================================================== SUMÁRIO
    S.append(p("Sumário", st["h1"]))
    sumario = [
        ["Seção", "Conteúdo"],
        ["1. Visão geral", "O problema, a solução entregue e a premissa clínica"],
        ["2. Dataset", "Bases escolhidas, origem, licença e discussão do problema"],
        ["3. Código-fonte", "Estrutura do projeto e responsabilidade de cada módulo"],
        ["4. Execução", "Instruções locais e via Docker (Dockerfile incluído)"],
        ["5. Relatório técnico", "EDA · pré-processamento · modelos · resultados · explicabilidade · crítica"],
        ["6. EXTRA — Visão Computacional", "CNN em ultrassom, ponto de operação clínico e Grad-CAM"],
        ["7. Provas de correção", "Suíte de testes, com destaque para o teste anti-vazamento"],
        ["8. Galeria de resultados", "Todas as figuras geradas pelo pipeline"],
        ["9. Conformidade", "Mapa item-a-item do enunciado para a entrega"],
        ["10. Vídeo", "Roteiro e o que é demonstrado em cada bloco"],
        ["Anexos", "Dataset, reprodutibilidade e referências"],
    ]
    S.append(tabela(sumario, st, [5.2 * cm, CONTENT_W - 5.2 * cm], align_num=False))

    # ============================================================ 1. VISÃO GERAL
    S.append(p("1. Visão geral da solução", st["h1"]))
    S.append(p(
        "Uma rede de hospitais especializada no atendimento à mulher precisa <b>acelerar a "
        "triagem</b> e <b>apoiar a decisão médica</b> diante de um volume crescente de "
        "pacientes. Nesta Fase 1 o escopo é construir a <b>base de IA</b> do sistema: um "
        "modelo de Machine Learning capaz de analisar dados médicos automaticamente e "
        "sinalizar padrões de risco.", st["corpo"]))
    S.append(p(
        "A solução entregue ataca a <b>detecção precoce de câncer de mama</b> — a tarefa "
        "principal sugerida no enunciado — por <b>duas vias complementares</b>:", st["corpo"]))
    S.extend(bullets([
        "<b>Via tabular (obrigatória).</b> Classificação binária de tumores em malignos vs. "
        "benignos a partir de 30 medidas morfométricas de núcleos celulares, com quatro "
        "algoritmos comparados, validação cruzada, avaliação em holdout e explicabilidade "
        "por feature importance e SHAP.",
        "<b>Via de imagem (EXTRA).</b> Uma Rede Neural Convolucional que diagnostica "
        "diretamente de <b>imagens de ultrassom de mama</b>, com escolha explícita do ponto "
        "de operação clínico e explicabilidade visual por Grad-CAM.",
    ], st))
    S.append(p(
        "<b>Premissa central do projeto:</b> o modelo é um <b>copiloto</b>, nunca um "
        "substituto. Ele entrega uma probabilidade acompanhada de uma explicação; a conduta "
        "é sempre do profissional de saúde. <b>O médico tem a palavra final no diagnóstico.</b>",
        st["nota"]))

    S.append(p("1.1 O que foi entregue", st["h2"]))
    entregue = [
        ["Entregável", "Onde está", "Status"],
        ["Código-fonte completo", "<font face='Courier'>src/</font>, <font face='Courier'>main.py</font>, "
         "<font face='Courier'>main_vision.py</font>, <font face='Courier'>tests/</font>", "Completo"],
        ["README com instruções", "<font face='Courier'>README.md</font>", "Completo"],
        ["Dockerfile", "<font face='Courier'>Dockerfile</font> + <font face='Courier'>.dockerignore</font>", "Completo"],
        ["Dataset", "<font face='Courier'>data/breast_cancer_wisconsin.csv</font> + download automático", "Completo"],
        ["Resultados (gráficos e análises)", "<font face='Courier'>reports/figures/</font> (11 figuras) + "
         "<font face='Courier'>reports/*.csv</font>", "Completo"],
        ["Relatório técnico", "Seção 5 deste PDF + notebooks narrados", "Completo"],
        ["Notebooks de demonstração", "<font face='Courier'>notebooks/</font> (2 notebooks, com saídas salvas)", "Completo"],
        ["Roteiro do vídeo", "Seção 10 deste PDF + <font face='Courier'>docs/ROTEIRO_VIDEO.md</font>", "Completo"],
    ]
    S.append(tabela(entregue, st, [5.0 * cm, 8.6 * cm, CONTENT_W - 13.6 * cm], align_num=False))

    # ================================================================ 2. DATASET
    S.append(PageBreak())
    S.append(p("2. Dataset e discussão do problema", st["h1"]))

    S.append(p("2.1 Base principal — Breast Cancer Wisconsin (Diagnostic)", st["h2"]))
    S.append(p(
        "São <b>569 pacientes</b> e <b>30 features numéricas</b> extraídas por processamento "
        "de imagem de aspirados por agulha fina (PAAF) de massas mamárias. Cada feature "
        "descreve uma propriedade geométrica ou de textura do núcleo celular — raio, textura, "
        "perímetro, área, suavidade, compacidade, concavidade, pontos côncavos, simetria e "
        "dimensão fractal — em três resumos por paciente: <b>média</b>, <b>erro-padrão</b> e "
        "o <b>pior</b> (maior) valor observado. Daí 10 × 3 = 30 colunas.", st["corpo"]))

    ficha = [
        ["Atributo", "Valor"],
        ["Fonte original", "UCI Machine Learning Repository (Wolberg, Street &amp; Mangasarian, 1995)"],
        ["Acesso no projeto", "<font face='Courier'>sklearn.datasets.load_breast_cancer()</font> — "
         "embutida na biblioteca, sem download externo"],
        ["Link Kaggle (mesma base)", "<link href='https://www.kaggle.com/datasets/uciml/breast-cancer-wisconsin-data/data' "
         "color='#1b4965'>kaggle.com/datasets/uciml/breast-cancer-wisconsin-data</link>"],
        ["Cópia versionada", "<font face='Courier'>data/breast_cancer_wisconsin.csv</font> (569 linhas × 31 colunas)"],
        ["Amostras", "569 pacientes"],
        ["Features", "30 numéricas contínuas (nenhuma categórica, nenhum identificador)"],
        ["Alvo", "<font face='Courier'>diagnosis</font> — binário"],
        ["Distribuição", "357 benignos (62,7%) · 212 malignos (37,3%)"],
        ["Valores ausentes", "Nenhum"],
    ]
    S.append(tabela(ficha, st, [4.4 * cm, CONTENT_W - 4.4 * cm], align_num=False))

    S.append(p("2.2 Por que esta base", st["h2"]))
    S.extend(bullets([
        "É a <b>tarefa principal explicitamente sugerida</b> no enunciado do desafio.",
        "É <b>pública, consolidada e livre de dados identificáveis</b> — não há questão ética "
        "de reidentificação de pacientes.",
        "Está <b>embutida no scikit-learn</b>, o que torna o projeto <b>100% reprodutível</b> "
        "em qualquer máquina, sem conta no Kaggle e sem link que possa cair.",
        "O problema é <b>clinicamente real e de alto impacto</b>: o câncer de mama é o câncer "
        "mais incidente em mulheres no Brasil, e a detecção precoce é o principal determinante "
        "de sobrevida.",
    ], st))

    S.append(p("2.3 Decisão de projeto — a convenção do rótulo", st["h2"]))
    S.append(p(
        "O scikit-learn carrega esta base com <font face='Courier'>target 0 = malignant</font> "
        "e <font face='Courier'>1 = benign</font>. Como as métricas binárias do scikit-learn "
        "(precision, recall, F1) são calculadas por padrão sobre a <b>classe 1</b>, manter essa "
        "codificação faria o <i>recall</i> reportado significar “proporção de <b>benignos</b> "
        "detectados” — exatamente o oposto do que interessa clinicamente.", st["corpo"]))
    S.append(p(
        "Por isso o projeto <b>remapeia o alvo para 1 = maligno e 0 = benigno</b> em "
        "<font face='Courier'>src/data_loader.py</font>. Com isso, <b>recall passa a significar "
        "literalmente “proporção de tumores malignos que o sistema detectou”</b> — e todas as "
        "discussões de métrica deste relatório ficam diretamente interpretáveis. Existe um "
        "teste automatizado dedicado a provar que esse remapeamento está correto "
        "(<font face='Courier'>test_remapeamento_do_alvo</font>), porque um erro silencioso "
        "aqui inverteria todas as conclusões.", st["corpo"]))

    S.append(p("2.4 Base do item EXTRA — BreastMNIST (ultrassom)", st["h2"]))
    ficha2 = [
        ["Atributo", "Valor"],
        ["Base", "BreastMNIST, do benchmark MedMNIST v2"],
        ["Origem dos dados", "BUSI — Breast Ultrasound Images Dataset (Al-Dhabyani et al., 2020)"],
        ["Acesso no projeto", "pacote <font face='Courier'>medmnist</font>, download automático do Zenodo "
         "(sem Kaggle)"],
        ["Amostras", "780 imagens de ultrassom em tons de cinza (546 treino / 78 validação / 156 teste)"],
        ["Resolução usada", "64 × 64 px, 1 canal"],
        ["Alvo", "binário — remapeado para <b>1 = maligno</b>, igual ao pipeline tabular"],
    ]
    S.append(tabela(ficha2, st, [4.4 * cm, CONTENT_W - 4.4 * cm], align_num=False))
    S.append(p(
        "A escolha do BreastMNIST no lugar do CBIS-DDSM (sugerido no enunciado) foi deliberada: "
        "o CBIS-DDSM tem dezenas de gigabytes e exige credencial do Kaggle, o que quebraria a "
        "reprodutibilidade de um clone limpo do repositório. O BreastMNIST resolve o <b>mesmo "
        "problema clínico</b> — diagnóstico de câncer de mama a partir de imagem médica — com "
        "download automático e treino em CPU em poucos minutos.", st["corpo"]))

    # ============================================================ 3. CÓDIGO-FONTE
    S.append(PageBreak())
    S.append(p("3. Código-fonte — estrutura do projeto", st["h1"]))
    S.append(p(
        "O projeto é um <b>pacote Python estruturado</b>, não um notebook solto: a lógica vive "
        "em módulos testáveis em <font face='Courier'>src/</font>, os scripts de orquestração "
        "apenas os encadeiam, e os notebooks consomem os mesmos módulos. Isso garante que o "
        "que é demonstrado no notebook é exatamente o que roda em produção.", st["corpo"]))

    S.append(bloco_codigo(
        "Tech_Challenge/\n"
        "|-- main.py                  Pipeline tabular completo (CLI, 7 etapas)\n"
        "|-- main_vision.py           EXTRA: pipeline da CNN de imagem (CLI)\n"
        "|-- Dockerfile               Imagem reprodutivel (CPU)\n"
        "|-- requirements.txt         Dependencias com versoes fixas\n"
        "|-- README.md                Instrucoes de execucao e metodologia\n"
        "|-- src/\n"
        "|   |-- config.py            Semente, caminhos, convencao de rotulo\n"
        "|   |-- data_loader.py       Carga da base + remapeamento do alvo\n"
        "|   |-- preprocessing.py     Limpeza, split estratificado, scaler (sem leakage)\n"
        "|   |-- eda.py               Analise exploratoria e graficos\n"
        "|   |-- modeling.py          4 modelos + validacao cruzada\n"
        "|   |-- evaluation.py        Metricas, matriz de confusao, curvas ROC\n"
        "|   |-- explainability.py    Feature importance + SHAP\n"
        "|   `-- vision.py            EXTRA: CNN, treino, avaliacao e Grad-CAM\n"
        "|-- notebooks/\n"
        "|   |-- tech_challenge_breast_cancer.ipynb   Notebook tabular (com saidas)\n"
        "|   `-- tech_challenge_cnn_imagem.ipynb      EXTRA: notebook da CNN\n"
        "|-- tests/\n"
        "|   |-- test_pipeline.py     Provas de correcao tabular (inclui anti-leakage)\n"
        "|   `-- test_vision.py       Provas de correcao da CNN (inclui remap do rotulo)\n"
        "|-- docs/ROTEIRO_VIDEO.md    Roteiro do video de demonstracao\n"
        "|-- data/                    CSV da base + BreastMNIST em cache\n"
        "|-- models/                  melhor_modelo.joblib + cnn_breastmnist.pt (gerados)\n"
        "`-- reports/\n"
        "    |-- metricas_teste.csv\n"
        "    |-- metricas_validacao_cruzada.csv\n"
        "    `-- figures/             Todos os graficos em PNG (01 a 11)",
        st))

    S.append(p("3.1 Responsabilidade de cada módulo", st["h2"]))
    modulos = [
        ["Módulo", "Responsabilidade", "Ponto-chave"],
        ["<font face='Courier'>config.py</font>",
         "Semente única, caminhos e convenção de rótulo",
         "<font face='Courier'>RANDOM_STATE = 42</font> em um só lugar garante reprodutibilidade"],
        ["<font face='Courier'>data_loader.py</font>",
         "Carrega a base e remapeia o alvo",
         "Inverte o rótulo para 1 = maligno"],
        ["<font face='Courier'>preprocessing.py</font>",
         "Limpeza, imputação, padronização e split",
         "O scaler vive dentro do <font face='Courier'>Pipeline</font> — sem vazamento"],
        ["<font face='Courier'>eda.py</font>",
         "Balanceamento, distribuições, correlação",
         "Detecta pares com |r| ≥ 0,9 (multicolinearidade)"],
        ["<font face='Courier'>modeling.py</font>",
         "Define os 4 modelos e a validação cruzada",
         "<font face='Courier'>class_weight='balanced'</font> trata o desbalanceamento"],
        ["<font face='Courier'>evaluation.py</font>",
         "Métricas, matriz de confusão, curvas ROC",
         "Expõe TN/FP/FN/TP para a discussão clínica"],
        ["<font face='Courier'>explainability.py</font>",
         "Feature importance e SHAP",
         "Detecta automaticamente coeficiente vs. importância de impureza"],
        ["<font face='Courier'>vision.py</font>",
         "CNN, treino, limiar clínico e Grad-CAM",
         "Calibra o limiar na validação, nunca no teste"],
    ]
    S.append(tabela(modulos, st, [3.6 * cm, 5.1 * cm, CONTENT_W - 8.7 * cm], align_num=False))

    # ================================================================ 4. EXECUÇÃO
    S.append(PageBreak())
    S.append(p("4. Como executar", st["h1"]))
    S.append(p("Requisito: <b>Python 3.11</b> (ou apenas Docker).", st["corpo"]))

    S.append(p("4.1 Execução local", st["h2"]))
    S.append(bloco_codigo(
        "# 1. Clonar e entrar no projeto\n"
        f"git clone {url_clone(repo)}\n"
        f"cd {nome_repo(repo)}\n\n"
        "# 2. Ambiente virtual + dependencias\n"
        "python -m venv .venv\n"
        ".venv\\Scripts\\activate          # Windows\n"
        "source .venv/bin/activate        # Linux / macOS\n"
        "pip install -r requirements.txt\n\n"
        "# 3. Pipeline tabular -> figuras 01-07, metricas e o melhor modelo\n"
        "python main.py\n\n"
        "# 4. EXTRA: pipeline da CNN -> baixa o BreastMNIST, treina,\n"
        "#    gera as figuras 08-11 e o modelo cnn_breastmnist.pt (CPU, ~2-3 min)\n"
        "python main_vision.py\n\n"
        "# 5. Provas de correcao\n"
        "python -m pytest -v\n\n"
        "# 6. Notebooks narrados\n"
        "jupyter notebook notebooks/tech_challenge_breast_cancer.ipynb\n"
        "jupyter notebook notebooks/tech_challenge_cnn_imagem.ipynb",
        st))
    S.append(p(
        "As rodas CPU do PyTorch instalam mais rápido pelo índice dedicado: "
        "<font face='Courier'>pip install torch torchvision --index-url "
        "https://download.pytorch.org/whl/cpu</font>.", st["corpo"]))

    S.append(p("4.2 Execução via Docker", st["h2"]))
    S.append(p(
        "O <font face='Courier'>Dockerfile</font> incluído no repositório monta a imagem com "
        "as rodas <b>CPU</b> do PyTorch (sem dependência de GPU/CUDA) e já deixa o pipeline "
        "pronto para rodar. Os volumes trazem as figuras e os modelos gerados de volta ao host.",
        st["corpo"]))
    S.append(bloco_codigo(
        "# Build da imagem\n"
        "docker build -t tech-challenge-fase1 .\n\n"
        "# Pipeline tabular (comando padrao da imagem)\n"
        "docker run --rm -v \"$(pwd)/reports:/app/reports\" \\\n"
        "                -v \"$(pwd)/models:/app/models\" tech-challenge-fase1\n\n"
        "# Pipeline da CNN (EXTRA)\n"
        "docker run --rm -v \"$(pwd)/reports:/app/reports\" \\\n"
        "                -v \"$(pwd)/models:/app/models\" \\\n"
        "                tech-challenge-fase1 python main_vision.py\n\n"
        "# Provas de correcao\n"
        "docker run --rm tech-challenge-fase1 python -m pytest -v\n\n"
        "# Notebooks em http://localhost:8888\n"
        "docker run --rm -p 8888:8888 tech-challenge-fase1 \\\n"
        "  jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root",
        st))

    S.append(p("4.3 Saídas geradas", st["h2"]))
    saidas = [
        ["Arquivo", "Origem", "Conteúdo"],
        ["<font face='Courier'>reports/figures/01-07*.png</font>", "main.py",
         "EDA, matrizes de confusão, curvas ROC, importância de features e SHAP"],
        ["<font face='Courier'>reports/figures/08-11*.png</font>", "main_vision.py",
         "Curvas de treino da CNN, matriz de confusão, amostras e Grad-CAM"],
        ["<font face='Courier'>reports/metricas_teste.csv</font>", "main.py",
         "Métricas dos 4 modelos no conjunto de teste"],
        ["<font face='Courier'>reports/metricas_validacao_cruzada.csv</font>", "main.py",
         "Média e desvio das métricas na validação cruzada de 5 folds"],
        ["<font face='Courier'>models/melhor_modelo.joblib</font>", "main.py",
         "Pipeline treinado do melhor modelo (pré-processador + classificador)"],
        ["<font face='Courier'>models/cnn_breastmnist.pt</font>", "main_vision.py",
         "Pesos da CNN de ultrassom"],
    ]
    S.append(tabela(saidas, st, [5.6 * cm, 2.4 * cm, CONTENT_W - 8.0 * cm], align_num=False))

    # ======================================================= 5. RELATÓRIO TÉCNICO
    S.append(PageBreak())
    S.append(p("5. Relatório técnico", st["h1"]))

    # ---------------------------------------------------------------- 5.1 EDA
    S.append(p("5.1 Discussões da análise exploratória", st["h2"]))

    S.append(p("5.1.1 Balanceamento das classes", st["h3"]))
    S.append(p(
        "A base tem <b>357 casos benignos (62,7%) contra 212 malignos (37,3%)</b>. É um "
        "desbalanceamento <b>moderado</b> — não é o cenário extremo de fraude ou doença rara — "
        "mas já é suficiente para tornar a <b>accuracy uma métrica enganosa</b>: um "
        "classificador degenerado que respondesse “benigno” para toda paciente atingiria "
        "<b>62,7% de acurácia</b> sem detectar um único câncer. Essa constatação, feita logo "
        "na exploração, é o que motiva toda a escolha de métrica discutida na seção 5.4.",
        st["corpo"]))
    S.append(p(
        "O desbalanceamento foi tratado em dois pontos: <b>estratificação</b> no split de "
        "treino/teste e na validação cruzada (para que a proporção de malignos seja idêntica "
        "em todos os conjuntos) e <b>ponderação de classe</b> "
        "(<font face='Courier'>class_weight='balanced'</font>) nos modelos que a suportam — "
        "o que penaliza mais o erro sobre a classe minoritária sem precisar reamostrar dados.",
        st["corpo"]))
    S.extend(figura("01_balanceamento_classes.png",
                    "Figura 1 — Distribuição das classes. O desbalanceamento moderado (63/37) "
                    "é o que invalida a accuracy como métrica isolada.", st, largura=9.5 * cm))

    S.append(p("5.1.2 Escalas e estatísticas descritivas", st["h3"]))
    S.append(p(
        "As 30 features vivem em <b>ordens de grandeza radicalmente diferentes</b>: "
        "<font face='Courier'>mean area</font> varia na casa das centenas a milhares "
        "(≈ 143 a 2 501), enquanto <font face='Courier'>mean smoothness</font> se move entre "
        "0,05 e 0,16. Sem padronização, qualquer algoritmo baseado em distância — o KNN é o "
        "caso óbvio — seria dominado quase inteiramente pelas colunas de área e perímetro, e a "
        "regressão logística teria coeficientes incomparáveis entre si. <b>Essa é a "
        "justificativa empírica direta para o StandardScaler</b> descrito na seção 5.2.",
        st["corpo"]))
    S.append(p(
        "A varredura de valores ausentes retornou <b>zero</b> em todas as 31 colunas, e não há "
        "duplicatas exatas. A base é limpa — o que não elimina a necessidade do tratamento "
        "defensivo descrito adiante.", st["corpo"]))

    S.append(p("5.1.3 Padrão clínico encontrado — o achado central", st["h3"]))
    S.append(p(
        "Comparando as distribuições das seis features mais correlacionadas com o diagnóstico, "
        "emerge um padrão nítido e <b>clinicamente coerente</b>: as classes formam duas "
        "distribuições visivelmente deslocadas, com <b>zona de sobreposição estreita</b>. Em "
        "<font face='Courier'>worst concave points</font>, os casos benignos concentram-se "
        "abaixo de 0,10 e os malignos acima de 0,13; em "
        "<font face='Courier'>worst perimeter</font>, benignos ficam em torno de 85 e malignos "
        "se espalham de 110 a 250.", st["corpo"]))
    S.append(p(
        "<b>Leitura clínica:</b> tumores malignos apresentam <b>núcleos celulares maiores</b> "
        "(raio, perímetro e área elevados) e <b>contornos mais irregulares</b> (concavidade e "
        "pontos côncavos elevados). É exatamente o critério morfológico que um patologista usa "
        "ao avaliar uma lâmina. O modelo, portanto, não vai precisar inventar um padrão "
        "exótico — ele vai aprender o critério que a medicina já reconhece, o que é a melhor "
        "notícia possível para a confiança clínica no sistema.", st["nota"]))
    S.extend(figura("02_distribuicoes_por_classe.png",
                    "Figura 2 — Distribuição das seis features mais preditivas por classe "
                    "(verde = benigno, vermelho = maligno). A separação clara com sobreposição "
                    "estreita é o que explica o alto desempenho obtido.", st))

    S.append(p("5.1.4 Análise de correlação e multicolinearidade", st["h3"]))
    S.append(p(
        "A matriz de correlação de Pearson revela blocos densos de correlação altíssima. O "
        "pipeline identificou <b>21 pares de features com |r| ≥ 0,9</b>. Isso não é ruído nem "
        "erro de dados: é <b>redundância geométrica esperada</b> — raio, perímetro e área de "
        "um núcleo aproximadamente circular são transformações determinísticas umas das outras "
        "(perímetro ≈ 2πr, área ≈ πr²). O mesmo vale entre os blocos “mean” e “worst” da mesma "
        "medida.", st["corpo"]))
    S.append(p("<b>Consequências práticas dessa multicolinearidade:</b>", st["corpo"]))
    S.extend(bullets([
        "<b>Não prejudica</b> o poder preditivo de árvores, Random Forest ou KNN.",
        "<b>Desestabiliza os coeficientes</b> da regressão logística: quando várias colunas "
        "carregam a mesma informação, o peso se divide arbitrariamente entre elas. Por isso "
        "<b>coeficiente linear não é medida confiável de importância</b> nesta base — e é "
        "exatamente por isso que o projeto usa SHAP como segunda lente (ver seção 5.5).",
        "<b>Justifica manter as 30 features</b> em vez de podar as redundantes: como o objetivo "
        "é desempenho preditivo e não inferência causal sobre coeficientes, remover colunas só "
        "traria risco de perder sinal marginal sem ganho prático.",
    ], st))
    S.extend(figura("03_matriz_correlacao.png",
                    "Figura 3 — Matriz de correlação de Pearson das 30 features e do alvo. Os "
                    "blocos vermelhos escuros são a multicolinearidade geométrica descrita "
                    "acima.", st, largura=13.0 * cm))

    # ------------------------------------------------------- 5.2 PRÉ-PROCESSAMENTO
    S.append(PageBreak())
    S.append(p("5.2 Estratégias de pré-processamento", st["h2"]))
    S.append(p(
        "Toda a estratégia foi desenhada em torno de um objetivo inegociável: <b>produzir uma "
        "estimativa honesta de desempenho</b>. Em saúde, um número inflado por vazamento de "
        "dados não é apenas um erro técnico — é uma promessa falsa sobre segurança de "
        "pacientes.", st["corpo"]))

    S.append(p("5.2.1 Limpeza defensiva", st["h3"]))
    S.append(p(
        "<font face='Courier'>clean_data()</font> remove duplicatas exatas e colunas "
        "integralmente vazias. Nesta base específica nenhuma das duas ocorre — a limpeza é "
        "<b>defensiva por design</b>, para que o mesmo pipeline possa ser reaproveitado em "
        "bases mais sujas (o dataset de SOP/PCOS sugerido no enunciado, por exemplo) sem "
        "reescrita.", st["corpo"]))

    S.append(p("5.2.2 Valores ausentes — imputação pela mediana, dentro do pipeline", st["h3"]))
    S.append(p(
        "A imputação usa <font face='Courier'>SimpleImputer(strategy='median')</font>. A "
        "mediana foi escolhida no lugar da média porque várias features são <b>assimétricas à "
        "direita com outliers pesados</b> (área e perímetro dos tumores grandes), e a média "
        "seria arrastada por eles. Criticamente, a imputação <b>não acontece na limpeza</b>: "
        "ela vive dentro do <font face='Courier'>Pipeline</font>, porque a mediana usada para "
        "preencher um valor faltante do teste precisa ser a mediana <b>do treino</b>.",
        st["corpo"]))

    S.append(p("5.2.3 Padronização e a prevenção de vazamento de dados", st["h3"]))
    S.append(p(
        "Esta é a decisão técnica mais importante do projeto. O "
        "<font face='Courier'>StandardScaler</font> (média 0, desvio 1) é obrigatório pelas "
        "razões de escala da seção 5.1.2 — mas <b>o modo como ele é aplicado</b> é o que "
        "separa um resultado válido de um resultado inflado.", st["corpo"]))
    S.append(p(
        "<b>O que o projeto NÃO faz:</b> normalizar o DataFrame inteiro e só depois dividir em "
        "treino e teste. Isso é o erro mais comum em projetos de ML — e é vazamento: a média e "
        "o desvio calculados incluiriam as amostras de teste, de forma que o modelo teria "
        "acesso indireto a informação do conjunto que deveria ser inédito.", st["corpo"]))
    S.append(p(
        "<b>O que o projeto faz:</b> encapsula imputador e scaler em um "
        "<font face='Courier'>ColumnTransformer</font> que, por sua vez, é a primeira etapa de "
        "um <font face='Courier'>Pipeline</font> do scikit-learn junto com o classificador. "
        "Assim, a cada <font face='Courier'>fit</font> — incluindo <b>cada um dos 5 folds da "
        "validação cruzada</b> — as estatísticas são reaprendidas <b>somente na partição de "
        "treino daquele fold</b> e apenas aplicadas à partição de validação.", st["destaque"]))
    S.append(bloco_codigo(
        "numeric_pipeline = Pipeline([\n"
        "    (\"imputer\", SimpleImputer(strategy=\"median\")),\n"
        "    (\"scaler\",  StandardScaler()),\n"
        "])\n"
        "preprocessor = ColumnTransformer([(\"num\", numeric_pipeline, numeric_features)])\n\n"
        "# O classificador entra no MESMO pipeline -> o scaler nunca ve o teste.\n"
        "model = Pipeline([(\"preprocessor\", preprocessor), (\"classifier\", estimator)])",
        st))
    S.append(p(
        "Essa invariante não fica no plano da intenção: existe um teste automatizado "
        "(<font face='Courier'>test_scaler_ajustado_somente_no_treino</font>) que <b>prova</b> "
        "que a média aprendida pelo scaler é idêntica à média do treino e mensuravelmente "
        "diferente da média do dataset completo. Ver seção 7.", st["corpo"]))

    S.append(p("5.2.4 Variáveis categóricas e numéricas", st["h3"]))
    S.append(p(
        "O enunciado pede a conversão de variáveis categóricas e numéricas para formatos "
        "adequados à modelagem. Nesta base, <b>as 30 features são todas numéricas contínuas</b> "
        "e o alvo é binário — não há nenhuma coluna categórica, textual ou de identificação a "
        "converter. O tratamento numérico exigido é justamente a imputação + padronização "
        "descrita acima.", st["corpo"]))
    S.append(p(
        "Ainda assim, o pré-processador foi construído como "
        "<font face='Courier'>ColumnTransformer</font> — e não como um "
        "<font face='Courier'>Pipeline</font> simples — <b>precisamente para deixar o ramo "
        "categórico plugável</b>: acrescentar um "
        "<font face='Courier'>OneHotEncoder</font> para colunas categóricas é uma linha, sem "
        "tocar em nenhum outro módulo. É a escolha arquitetural correta para um sistema que a "
        "rede hospitalar vai estender com prontuários reais (onde haverá sexo, comorbidade, "
        "histórico familiar).", st["corpo"]))

    S.append(p("5.2.5 Separação treino/teste", st["h3"]))
    split_tab = [
        ["Parâmetro", "Valor", "Justificativa"],
        ["Proporção", "80% treino / 20% teste", "455 amostras de treino e 114 de teste — "
         "teste grande o bastante para uma estimativa estável nesta base pequena"],
        ["Estratificação", "<font face='Courier'>stratify=y</font>", "Mantém ≈ 37% de malignos "
         "nos dois conjuntos; sem isso, o teste poderia ficar com proporção distorcida"],
        ["Semente", "<font face='Courier'>random_state=42</font>", "Reprodutibilidade exata; "
         "definida uma única vez em <font face='Courier'>config.py</font>"],
        ["Validação cruzada", "StratifiedKFold, 5 folds", "Roda <b>apenas no treino</b>, para "
         "seleção de modelo; o teste permanece intocado até a avaliação final"],
    ]
    S.append(tabela(split_tab, st, [3.0 * cm, 3.7 * cm, CONTENT_W - 6.7 * cm], align_num=False))

    # ------------------------------------------------------------- 5.3 MODELOS
    S.append(PageBreak())
    S.append(p("5.3 Modelos usados e por quê", st["h2"]))
    S.append(p(
        "O enunciado exige duas ou mais técnicas. O projeto usa <b>quatro</b>, escolhidas "
        "deliberadamente para cobrir <b>famílias algorítmicas distintas</b> — linear, baseada "
        "em regras, baseada em distância e ensemble. Comparar famílias diferentes (em vez de "
        "quatro variações do mesmo algoritmo) é o que permite afirmar algo sobre a natureza do "
        "problema, e não apenas sobre um hiperparâmetro.", st["corpo"]))

    modelos = [
        ["Modelo", "Família", "Por que foi incluído", "Configuração"],
        ["Regressão Logística", "Linear",
         "Baseline forte e <b>diretamente interpretável</b>: fornece probabilidade calibrada e "
         "coeficientes com sinal, o que facilita a conversa clínica. Adequada porque a EDA "
         "mostrou classes quase linearmente separáveis.",
         "<font face='Courier'>max_iter=5000</font>, <font face='Courier'>class_weight='balanced'</font>"],
        ["Árvore de Decisão", "Baseada em regras",
         "Máxima interpretabilidade — a decisão vira um fluxograma legível por um médico. "
         "Serve também como <b>piso de referência</b>: se um modelo complexo não superar uma "
         "árvore rasa, a complexidade não se justifica.",
         "<font face='Courier'>max_depth=4</font> (limita overfitting), "
         "<font face='Courier'>class_weight='balanced'</font>"],
        ["KNN", "Baseada em distância",
         "Não assume forma funcional alguma: classifica por semelhança com pacientes "
         "próximos — uma analogia natural ao raciocínio por casos parecidos. É também o teste "
         "empírico de que a padronização funciona.",
         "<font face='Courier'>n_neighbors=7</font>"],
        ["Random Forest", "Ensemble de árvores",
         "Costuma ser o mais forte em dados tabulares, captura interações não lineares, é "
         "robusto a outliers e fornece importância de features nativa — além de ser o modelo "
         "sobre o qual o SHAP é calculado de forma exata.",
         "<font face='Courier'>n_estimators=300</font>, "
         "<font face='Courier'>class_weight='balanced'</font>"],
    ]
    S.append(tabela(modelos, st, [2.7 * cm, 2.3 * cm, 7.6 * cm, CONTENT_W - 12.6 * cm],
                    align_num=False))

    S.append(p("5.3.1 Protocolo de treino e seleção", st["h3"]))
    S.extend(bullets([
        "Cada modelo é um <font face='Courier'>Pipeline</font> completo "
        "(pré-processador + classificador) — nunca um estimador nu.",
        "<b>Seleção</b> por validação cruzada estratificada de 5 folds <b>no conjunto de "
        "treino</b>, com accuracy, precision, recall, F1 e ROC-AUC.",
        "<b>Avaliação final</b> uma única vez no holdout de teste, que não participou de "
        "nenhuma decisão anterior.",
        "<b>Critério de escolha do campeão:</b> maior <b>recall</b> da classe maligna — a "
        "métrica justificada na seção 5.4.",
    ], st))

    S.append(p("5.3.2 Desempenho na validação cruzada (conjunto de treino)", st["h3"]))
    S.append(tabela_metricas_cv(st))
    S.append(p(
        "Os desvios-padrão baixos (≤ 0,03 na maioria) indicam que o desempenho é <b>estável "
        "entre partições</b> — não é um resultado de sorte de um split específico. Regressão "
        "Logística e Random Forest já se destacam aqui, antecipando o resultado do teste.",
        st["corpo"]))

    # ---------------------------------------------------------- 5.4 RESULTADOS
    S.append(PageBreak())
    S.append(p("5.4 Resultados e interpretação dos dados", st["h2"]))

    S.append(p("5.4.1 A escolha da métrica — o custo assimétrico do erro", st["h3"]))
    S.append(p(
        "Antes de qualquer número, é preciso definir <b>o que conta como sucesso</b>. Neste "
        "problema os dois tipos de erro têm consequências <b>profundamente assimétricas</b>:",
        st["corpo"]))
    custos = [
        ["Tipo de erro", "O que significa clinicamente", "Consequência", "Custo"],
        ["<b><font color='#a83232'>Falso negativo</font></b>",
         "Um tumor <b>maligno</b> é classificado como benigno",
         "A paciente é liberada sem investigação. O câncer segue evoluindo e o tratamento "
         "começa em estágio mais avançado — ou não começa.",
         "<b><font color='#a83232'>Altíssimo — risco à vida</font></b>"],
        ["<font color='#b8860b'>Falso positivo</font>",
         "Um tumor <b>benigno</b> é classificado como maligno",
         "A paciente passa por biópsia e exames adicionais, com ansiedade e custo ao sistema, "
         "até ser descartado.",
         "<font color='#b8860b'>Real, porém muito menor</font>"],
    ]
    S.append(tabela(custos, st, [2.7 * cm, 4.0 * cm, 6.6 * cm, CONTENT_W - 13.3 * cm],
                    align_num=False))
    S.append(p(
        "Disso decorre a decisão metodológica do projeto: <b>a métrica prioritária é o recall "
        "da classe maligna</b> — a fração de cânceres que o sistema efetivamente detecta. F1 e "
        "precision entram como <b>contrapeso</b>, para impedir a degeneração oposta (um modelo "
        "que grita “maligno” para todo mundo teria recall perfeito e seria clinicamente "
        "inútil). A <b>accuracy é reportada mas não decide</b>, pelo motivo já demonstrado na "
        "EDA: 62,7% é o piso trivial nesta base. O <b>ROC-AUC</b> complementa por medir a "
        "qualidade do ranqueamento independentemente do limiar escolhido.", st["nota"]))

    S.append(p("5.4.2 Desempenho no conjunto de teste (114 pacientes)", st["h3"]))
    tab_teste, df_teste = tabela_metricas_teste(st)
    S.append(tab_teste)
    S.append(p("Linha destacada: modelo campeão pelo critério de recall.", st["legenda"]))

    S.append(p("5.4.3 Interpretação — o trade-off entre os dois melhores", st["h3"]))
    S.append(p(
        "O conjunto de teste contém <b>114 pacientes: 72 benignos e 42 malignos</b>. Traduzindo "
        "as métricas em contagens de pacientes reais, que é como a discussão clínica precisa "
        "ser feita:", st["corpo"]))
    comparacao = [
        ["", "Regressão Logística", "Random Forest"],
        ["Malignos detectados (VP)", "<b>40 de 42</b>", "39 de 42"],
        ["<b>Falsos negativos (câncer não detectado)</b>",
         "<b><font color='#2f7d4f'>2</font></b>", "<font color='#a83232'>3</font>"],
        ["Falsos positivos (biópsia desnecessária)",
         "<font color='#b8860b'>1</font>", "<font color='#2f7d4f'>0</font>"],
        ["Accuracy", "0,974", "0,974"],
        ["Recall (maligno)", "<b>0,952</b>", "0,929"],
        ["Precision", "0,976", "<b>1,000</b>"],
        ["ROC-AUC", "0,995", "<b>0,998</b>"],
    ]
    S.append(tabela(comparacao, st, [7.4 * cm, 4.8 * cm, CONTENT_W - 12.2 * cm]))
    S.append(p(
        "Os dois modelos empatam em accuracy (0,974) — e é justamente aí que a accuracy mostra "
        "por que não serve como critério: <b>ela não distingue os dois erros</b>. Descendo ao "
        "nível de paciente, a diferença é nítida e tem uma direção clara:", st["corpo"]))
    S.extend(bullets([
        "O <b>Random Forest</b> tem <b>precision perfeita</b>: nenhum alarme falso. Todo "
        "paciente que ele apontou como maligno era realmente maligno. Em contrapartida, "
        "<b>deixou passar 3 cânceres</b>.",
        "A <b>Regressão Logística</b> deixa passar <b>2 cânceres</b> e gera <b>1 alarme "
        "falso</b>.",
        "<b>O trade-off, em termos concretos:</b> trocar 1 falso negativo por 1 falso positivo "
        "significa trocar <b>um câncer não detectado</b> por <b>uma biópsia desnecessária</b>. "
        "Pelo critério de custo assimétrico estabelecido em 5.4.1, essa troca é claramente "
        "favorável.",
    ], st))
    S.append(p(
        "<b>Modelo escolhido: Regressão Logística.</b> Além do recall superior, ela traz três "
        "vantagens práticas: fornece <b>probabilidades bem calibradas</b> (essencial para "
        "ajustar o limiar de triagem), é o modelo <b>mais simples e auditável</b> dos quatro "
        "(um requisito real em contexto regulatório de saúde) e tem <b>custo computacional "
        "desprezível</b> em inferência.", st["destaque"]))
    S.append(p(
        "Vale registrar a ressalva estatística honesta: com 42 malignos no teste, a diferença "
        "de 1 falso negativo entre os dois modelos <b>não é estatisticamente significativa</b> "
        "— o intervalo de confiança dessas taxas é largo em uma amostra desse tamanho. A "
        "escolha é defensável e coerente com o critério declarado, mas a decisão final entre "
        "os dois exigiria validação em uma base maior.", st["corpo"]))

    S.append(p("5.4.4 Desempenho dos demais modelos", st["h3"]))
    S.extend(bullets([
        "<b>KNN (recall 0,905; AUC 0,982):</b> desempenho respeitável, confirmando que a "
        "padronização funcionou — sem ela, o KNN colapsaria. Fica atrás por não modelar "
        "explicitamente a fronteira de decisão.",
        "<b>Árvore de Decisão (recall 0,881; AUC 0,901):</b> claramente a mais fraca, "
        "especialmente em AUC. Uma única árvore com profundidade 4 produz uma fronteira em "
        "degraus grosseiros, incapaz de acompanhar a separação suave observada na EDA. É "
        "exatamente o contraste que justifica o ensemble: o Random Forest, feito de árvores, "
        "salta de 0,901 para 0,998 de AUC.",
    ], st))

    S.extend(figura("04_matriz_confusao_regressao_logistica.png",
                    "Figura 4 — Matriz de confusão do modelo campeão (Regressão Logística). "
                    "O quadrante inferior esquerdo — 2 malignos classificados como benignos — "
                    "é o erro que o projeto prioriza minimizar.", st, largura=10.0 * cm))
    S.extend(figura("04_matriz_confusao_random_forest.png",
                    "Figura 5 — Matriz de confusão do Random Forest: nenhum falso positivo, "
                    "mas 3 falsos negativos.", st, largura=10.0 * cm))
    S.extend(figura("05_curvas_roc.png",
                    "Figura 6 — Curvas ROC dos quatro modelos. Regressão Logística, Random "
                    "Forest e KNN colam no canto superior esquerdo; a Árvore de Decisão é "
                    "visivelmente inferior (AUC 0,901).", st, largura=11.5 * cm))

    # ---------------------------------------------------- 5.5 EXPLICABILIDADE
    S.append(PageBreak())
    S.append(p("5.5 Explicabilidade — por que o modelo decidiu assim", st["h2"]))
    S.append(p(
        "Em saúde, um modelo que acerta mas não explica é inutilizável: nenhum profissional "
        "assume responsabilidade sobre uma recomendação opaca, e nenhum órgão regulador "
        "aprovaria. O projeto usa <b>duas técnicas complementares</b>, exatamente como pede o "
        "enunciado.", st["corpo"]))

    S.append(p("5.5.1 Feature importance — e uma armadilha honesta", st["h3"]))
    S.append(p(
        "Para a Regressão Logística, a importância global é o <b>valor absoluto dos "
        "coeficientes</b> — comparável entre features porque todas estão padronizadas. O topo "
        "traz <font face='Courier'>worst texture</font>, "
        "<font face='Courier'>radius error</font> e "
        "<font face='Courier'>worst symmetry</font>.", st["corpo"]))
    S.append(p(
        "<b>Esse resultado precisa ser lido com cuidado — e a leitura ingênua estaria errada.</b> "
        "Ele <b>não</b> significa que raio, área e perímetro sejam irrelevantes (a EDA mostrou "
        "que são as features mais correlacionadas com o diagnóstico). É a "
        "<b>multicolinearidade</b> diagnosticada na seção 5.1.4 agindo: quando 21 pares de "
        "features carregam informação quase idêntica, o modelo linear <b>reparte o peso entre "
        "elas</b> e nenhuma sobressai isoladamente; sobrevivem no topo justamente as features "
        "<b>menos redundantes</b>, que contribuem com sinal próprio. <b>Coeficiente linear sob "
        "multicolinearidade não é uma medida confiável de importância</b> — e é precisamente "
        "por isso que o SHAP não é um extra decorativo neste projeto, mas a lente necessária.",
        st["destaque"]))
    S.extend(figura("06_feature_importance.png",
                    "Figura 7 — Importância global por magnitude dos coeficientes (Regressão "
                    "Logística). O ranking reflete a multicolinearidade da base, não a "
                    "irrelevância das medidas de tamanho.", st, largura=11.0 * cm))

    S.append(p("5.5.2 SHAP — a explicação que resiste à multicolinearidade", st["h3"]))
    S.append(p(
        "O SHAP (SHapley Additive exPlanations) tem base em teoria dos jogos: atribui a cada "
        "feature a <b>contribuição marginal média</b> para a previsão, considerando todas as "
        "ordens possíveis de inclusão. Isso o torna robusto à redundância e — mais importante — "
        "permite explicar <b>uma previsão individual</b>: “por que <i>esta</i> paciente foi "
        "classificada como maligno?”. É a forma de explicação que efetivamente serve ao médico "
        "à beira do leito. Foi calculado com <font face='Courier'>TreeExplainer</font> sobre o "
        "Random Forest, onde a atribuição é exata.", st["corpo"]))
    S.append(p("<b>O que o gráfico SHAP mostra:</b>", st["corpo"]))
    S.extend(bullets([
        "As features de maior impacto são <font face='Courier'>worst area</font>, "
        "<font face='Courier'>worst perimeter</font>, "
        "<font face='Courier'>worst concave points</font>, "
        "<font face='Courier'>mean concave points</font> e "
        "<font face='Courier'>worst radius</font> — <b>convergindo com a EDA</b> e corrigindo a "
        "leitura enviesada dos coeficientes lineares.",
        "A <b>direção</b> é inequívoca: pontos vermelhos (valores altos dessas medidas) caem "
        "todos do lado positivo do eixo, <b>empurrando a previsão para “maligno”</b>; pontos "
        "azuis (valores baixos) empurram para “benigno”.",
        "A separação é <b>limpa e monotônica</b>, sem a mistura desordenada que denunciaria o "
        "modelo se apoiando em artefato ou ruído.",
    ], st))
    S.append(p(
        "<b>Conclusão de explicabilidade:</b> o modelo aprendeu que <b>núcleos celulares "
        "maiores e de contorno mais irregular indicam malignidade</b> — o mesmo critério "
        "morfológico da patologia clínica. Não é uma correlação espúria de dataset. Essa "
        "convergência entre o que o modelo usa e o que a medicina reconhece é o principal "
        "argumento a favor de confiar nele como ferramenta de apoio.", st["nota"]))
    S.extend(figura("07_shap_summary.png",
                    "Figura 8 — SHAP summary plot (Random Forest). Cada ponto é uma paciente; "
                    "a cor é o valor da feature e a posição horizontal é o empurrão na previsão. "
                    "Valores altos (vermelho) de área, perímetro e pontos côncavos empurram "
                    "consistentemente para “maligno”.", st, largura=12.5 * cm))

    # --------------------------------------------------- 5.6 DISCUSSÃO CRÍTICA
    S.append(PageBreak())
    S.append(p("5.6 Discussão crítica — o modelo pode ser usado na prática?", st["h2"]))
    S.append(p(
        "<b>Resposta curta: sim, como ferramenta de apoio à decisão — e em nenhuma hipótese "
        "como decisor autônomo.</b>", st["destaque"]))

    S.append(p("5.6.1 Como o sistema entraria no fluxo de atendimento", st["h3"]))
    usos = [
        ["Uso", "Como funciona", "Ganho para a rede hospitalar"],
        ["<b>Priorização de fila</b>",
         "O sistema pontua os casos que chegam e sinaliza os de alto risco, que sobem na fila "
         "de leitura do especialista.",
         "Reduz o tempo até o diagnóstico nos casos em que o tempo mais importa — o objetivo de "
         "triagem declarado no desafio."],
        ["<b>Segunda opinião / rede de segurança</b>",
         "O modelo roda em paralelo ao laudo humano e emite um alerta apenas quando diverge, "
         "convidando a uma revisão.",
         "Reduz a chance de um caso maligno passar por desatenção, sem adicionar trabalho aos "
         "casos concordantes."],
        ["<b>Ponto de operação ajustável</b>",
         "Em triagem, opera-se com limiar mais baixo, favorecendo recall; em confirmação, com "
         "limiar mais alto.",
         "A mesma ferramenta serve a duas etapas do fluxo com perfis de erro diferentes."],
    ]
    S.append(tabela(usos, st, [3.9 * cm, 6.4 * cm, CONTENT_W - 10.3 * cm], align_num=False))
    S.append(p(
        "Em todos os cenários, a saída entregue é <b>probabilidade + explicação</b> (as "
        "features que mais pesaram naquele caso, via SHAP), nunca um veredito isolado. "
        "<b>A conduta é do profissional; o médico tem a palavra final.</b>", st["corpo"]))

    S.append(p("5.6.2 Limitações — leitura honesta", st["h3"]))
    S.extend(bullets([
        "<b>Base pequena e de fonte única.</b> 569 pacientes de uma única instituição, coletados "
        "nos anos 1990. Não há garantia de que o desempenho se mantenha em outra população, "
        "outro equipamento ou outro protocolo de coleta.",
        "<b>As features já foram extraídas por especialistas.</b> O modelo recebe medidas "
        "morfométricas prontas, calculadas a partir de lâminas de PAAF por um profissional. "
        "<b>Ele não substitui o exame</b> — ele opera <i>depois</i> dele. O item EXTRA de visão "
        "computacional é justamente a tentativa de encurtar essa dependência.",
        "<b>O teste tem 114 pacientes.</b> Diferenças de 1 a 2 erros entre modelos estão dentro "
        "da margem de incerteza amostral, como registrado em 5.4.3.",
        "<b>Não há informação demográfica.</b> A base não traz idade, etnia ou condição "
        "socioeconômica — <b>é impossível auditar viés entre subgrupos</b>, o que é uma lacuna "
        "séria para um sistema de saúde que atende população diversa.",
        "<b>Não é um dispositivo médico certificado.</b> Uso clínico real exigiria validação "
        "externa e prospectiva, aprovação regulatória (ANVISA), rastreabilidade de versão de "
        "modelo e monitoramento contínuo de <i>drift</i> e de viés.",
        "<b>Risco de excesso de confiança automática.</b> Um sistema que acerta 97% das vezes "
        "induz o profissional a relaxar a checagem — por isso a interface deve sempre expor a "
        "incerteza e a explicação, e nunca apenas o rótulo.",
    ], st))

    S.append(p("5.6.3 Próximos passos", st["h3"]))
    S.extend(bullets([
        "Validação externa em base independente e, idealmente, prospectiva.",
        "Coleta de variáveis demográficas para auditoria de viés entre subgrupos.",
        "Calibração explícita do limiar de decisão junto ao corpo clínico, com curva de "
        "custo-benefício definida pelos próprios médicos.",
        "Evolução do item de imagem (transfer learning, maior resolução, mais dados) para "
        "reduzir a dependência da extração manual de features.",
        "Ampliação do escopo para os outros riscos citados no desafio — SOP e detecção de "
        "sinais de violência doméstica em prontuários (NLP) — reaproveitando a arquitetura "
        "modular já construída.",
    ], st))

    # ============================================================== 6. EXTRA CNN
    S.append(PageBreak())
    S.append(p("6. EXTRA — Visão Computacional: CNN em imagens de ultrassom", st["h1"]))
    S.append(p(
        "O enunciado oferece como item extra o diagnóstico a partir de dados de imagem com "
        "redes neurais convolucionais. O projeto entrega esse pipeline completo — com treino, "
        "avaliação, escolha de ponto de operação e explicabilidade visual.", st["corpo"]))

    S.append(p("6.1 Arquitetura e treino", st["h2"]))
    arq = [
        ["Aspecto", "Escolha", "Justificativa"],
        ["Arquitetura", "3 blocos Conv→BatchNorm→ReLU→MaxPool + "
         "AdaptiveAvgPool + Dropout + Linear", "≈ 24 mil parâmetros: capacidade suficiente "
         "para 546 imagens de treino sem memorizar o conjunto"],
        ["Entrada", "64 × 64 px, 1 canal", "Compromisso entre detalhe e custo; o "
         "<font face='Courier'>AdaptiveAvgPool</font> aceita outras resoluções sem mudar código"],
        ["Aumentação", "flip horizontal + rotação de ±10°", "Amplia artificialmente um "
         "conjunto muito pequeno, com transformações plausíveis em ultrassom"],
        ["Desbalanceamento", "perda ponderada com expoente 0,5 sobre os pesos balanceados",
         "Balanceamento total superprevê a minoria; a raiz suaviza e equilibra recall e precision"],
        ["Seleção de época", "melhor F1 de validação (checkpoint restaurado)",
         "Early stopping implícito — evita entregar o modelo da última época por acaso"],
        ["Hardware", "CPU, ≈ 2–3 minutos", "Reprodutível em qualquer máquina, sem GPU"],
    ]
    S.append(tabela(arq, st, [3.0 * cm, 5.6 * cm, CONTENT_W - 8.6 * cm], align_num=False))
    S.extend(figura("08_cnn_treino.png",
                    "Figura 9 — Curvas de treino. À esquerda, a perda cai de forma consistente "
                    "em treino e validação. À direita, recall e F1 de validação oscilam bastante "
                    "entre épocas — consequência direta do conjunto de validação minúsculo "
                    "(78 imagens), o que é exatamente o motivo de selecionar o melhor "
                    "checkpoint em vez da última época.", st, largura=15.0 * cm))

    S.append(p("6.2 Resultados e a escolha do ponto de operação", st["h2"]))
    S.append(p(
        "A CNN produz uma <b>probabilidade</b>, e o limiar que a converte em decisão é uma "
        "<b>escolha clínica, não estatística</b>. O projeto reporta dois pontos de operação — "
        "e o limiar clínico foi calibrado <b>no conjunto de validação, nunca no teste</b>, para "
        "não contaminar a estimativa final.", st["corpo"]))
    cnn_tab = [
        ["Ponto de operação", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC",
         "Falsos negativos"],
        ["Limiar padrão (0,50)", "0,853", "0,771", "0,643", "0,701", "0,854",
         "<font color='#a83232'>15 de 42</font>"],
        ["<b>Ponto clínico (0,29)</b>", "0,718", "0,485", "<b>0,786</b>", "0,600", "0,854",
         "<b><font color='#2f7d4f'>9 de 42</font></b>"],
    ]
    S.append(tabela(cnn_tab, st,
                    [3.6 * cm, 2.0 * cm, 2.1 * cm, 1.9 * cm, 1.6 * cm, 2.0 * cm,
                     CONTENT_W - 13.2 * cm]))
    S.append(p(
        "Baixar o limiar de 0,50 para 0,29 <b>reduz de 15 para 9 os cânceres não "
        "detectados</b> em 156 imagens de teste, ao custo de mais alarmes falsos (precision cai "
        "de 0,771 para 0,485). É a mesma discussão de custo assimétrico da seção 5.4.1, agora "
        "aplicada à triagem por imagem — e em triagem essa é a troca correta. Note que o "
        "<b>ROC-AUC não muda</b> (0,854): ele mede a qualidade do ranqueamento, que independe "
        "do limiar. O limiar apenas escolhe <b>onde</b> na curva ROC o sistema vai operar.",
        st["corpo"]))
    S.extend(figura("09_cnn_matriz_confusao.png",
                    "Figura 10 — Matriz de confusão da CNN no ponto de operação clínico: 33 dos "
                    "42 malignos detectados, 9 falsos negativos, 35 falsos positivos.",
                    st, largura=9.5 * cm))
    S.extend(figura("10_cnn_amostras.png",
                    "Figura 11 — Amostras do conjunto de teste com rótulo real e previsto "
                    "(verde = acerto). As imagens são pequenas, ruidosas e de baixo contraste — "
                    "o que ajuda a dimensionar a dificuldade da tarefa.", st, largura=14.0 * cm))

    S.append(p("6.3 Explicabilidade visual — Grad-CAM", st["h2"]))
    S.append(p(
        "O Grad-CAM é o análogo visual do SHAP: ele usa os gradientes da classe “maligno” em "
        "relação à última camada convolucional para produzir um mapa de calor das regiões que "
        "mais pesaram na decisão. É o que permite <b>auditar</b> a rede antes de confiar nela.",
        st["corpo"]))
    S.append(p(
        "<b>Leitura crítica e honesta:</b> em vários exemplos o mapa de calor aparece "
        "<b>difuso pela textura do tecido</b>, e não concentrado sobre o nódulo. Isso é um "
        "sinal legítimo de alerta — sugere que a rede está se apoiando em textura global e "
        "ruído de <i>speckle</i> em vez da lesão em si, o que é consistente com o AUC modesto "
        "de 0,85. <b>E esse é precisamente o valor do Grad-CAM:</b> sem ele, o número de "
        "accuracy sozinho poderia passar uma confiança que a evidência visual não sustenta.",
        st["destaque"]))
    S.extend(figura("11_cnn_gradcam.png",
                    "Figura 12 — Grad-CAM. Linha superior: imagem original de ultrassom. Linha "
                    "inferior: o mapa de calor sobreposto (vermelho = maior influência na "
                    "decisão “maligno”).", st, largura=CONTENT_W))

    S.append(p("6.4 Leitura crítica do item EXTRA", st["h2"]))
    S.append(p(
        "O modelo de imagem é <b>honestamente mais fraco</b> que o tabular: AUC de 0,854 contra "
        "0,995. Isso não é um defeito de implementação — é a consequência esperada de um "
        "problema muito mais difícil:", st["corpo"]))
    S.extend(bullets([
        "O modelo tabular recebe <b>features que especialistas já extraíram</b> das lâminas; a "
        "CNN precisa <b>descobrir os padrões direto dos pixels</b>.",
        "São <b>546 imagens de treino</b> contra 455 amostras tabulares — mas o espaço de "
        "entrada é de 4 096 pixels em vez de 30 medidas curadas.",
        "As imagens são de <b>baixa resolução</b> (o BreastMNIST é derivado por redimensionamento) "
        "e ultrassom é uma modalidade intrinsecamente ruidosa.",
        "O valor de AUC ≈ 0,85 está <b>dentro do que a literatura reporta</b> para o "
        "BreastMNIST — não é um resultado anômalo.",
    ], st))
    S.append(p(
        "O item EXTRA vale, portanto, como <b>prova de conceito e base de evolução</b>, não "
        "como sistema pronto. O caminho de melhoria é conhecido: <b>transfer learning</b> "
        "(ResNet/EfficientNet pré-treinadas), imagens em resolução original, mais dados e "
        "validação multi-institucional.", st["corpo"]))

    # ================================================== 7. PROVAS DE CORREÇÃO
    S.append(PageBreak())
    S.append(p("7. Provas de correção — a suíte de testes", st["h1"]))
    S.append(p(
        "Os resultados apresentados só valem se o encanamento de dados estiver correto. A "
        "suíte de testes existe para <b>provar as invariantes</b> das quais todos os números "
        "dependem — não para “ter testes”.", st["corpo"]))

    testes = [
        ["Grupo", "O que é provado", "Por que importa"],
        ["Integridade dos dados",
         "569 × 31; alvo binário; 212 malignos e 357 benignos; nenhum ausente",
         "Detecta troca silenciosa de base ou corrupção do CSV"],
        ["<b>Remapeamento do rótulo</b>",
         "1 = maligno em ambos os pipelines (tabular e CNN)",
         "<b>Se estivesse invertido, todo o recall discutido estaria de cabeça para baixo</b> — "
         "e o erro seria invisível, pois as métricas continuariam “boas”"],
        ["Split",
         "Proporção de malignos preservada; zero sobreposição entre treino e teste",
         "Garante que o teste é realmente inédito"],
        ["<b>Anti-vazamento (o mais importante)</b>",
         "A média aprendida pelo <font face='Courier'>StandardScaler</font> é idêntica à média "
         "do <b>treino</b> e mensuravelmente diferente da do dataset completo",
         "<b>Se este teste falhar, todos os números de desempenho são inflados e inválidos</b>"],
        ["Modelagem",
         "Todos os modelos preveem apenas rótulos válidos; mesma semente produz previsões "
         "idênticas",
         "Reprodutibilidade verificável, não prometida"],
        ["Avaliação",
         "Métricas dentro de [0,1]; TN+FP+FN+TP igual ao tamanho do teste",
         "Impede erro aritmético silencioso na matriz de confusão"],
        ["Explicabilidade",
         "A importância cobre exatamente as 30 features, sem perda nem duplicação",
         "Garante que o alinhamento nome-de-feature ↔ peso está correto"],
        ["CNN",
         "Saída binária; aceita 28/64/128 px; o limiar controla as predições nos dois "
         "extremos; Grad-CAM com shape correto e normalizado",
         "Testes herméticos, sem download nem treino — rodam em segundos"],
    ]
    S.append(tabela(testes, st, [3.7 * cm, 6.3 * cm, CONTENT_W - 10.0 * cm], align_num=False))
    S.append(Spacer(1, 0.35 * cm))
    S.append(bloco_codigo("python -m pytest -v", st))

    S.append(p("7.1 Execução verificada de ponta a ponta", st["h2"]))
    S.append(p(
        "A entrega foi validada em ambiente limpo (venv novo, "
        "<font face='Courier'>pip install -r requirements.txt</font> sem conflitos, "
        "Python 3.11 no Windows):", st["corpo"]))
    S.extend(bullets([
        "<b>19 de 19 testes passam</b> (12 do pipeline tabular + 7 da CNN), incluindo o teste "
        "anti-vazamento e o teste de remapeamento do rótulo.",
        "<b><font face='Courier'>python main.py</font> executa por completo</b> e reproduz "
        "exatamente as métricas relatadas: matriz de confusão do modelo campeão com "
        "<b>71 VN · 1 FP · 2 FN · 40 VP</b>.",
        "<b><font face='Courier'>python main_vision.py</font> executa por completo</b> e "
        "reproduz o resultado da CNN de forma determinística: limiar clínico 0,29, matriz de "
        "confusão <b>[[79, 35], [9, 33]]</b> e ROC-AUC 0,854.",
        "Todas as <b>11 figuras</b> e os <b>2 CSVs</b> de métricas são regerados do zero pelos "
        "dois comandos — nenhum resultado deste PDF é digitado à mão.",
    ], st))

    # ============================================== 8. GALERIA DE RESULTADOS
    S.append(PageBreak())
    S.append(p("8. Resultados obtidos — galeria completa de figuras", st["h1"]))
    S.append(p(
        "Todas as figuras abaixo são geradas automaticamente pelo pipeline e gravadas em "
        "<font face='Courier'>reports/figures/</font>. As principais já foram discutidas nas "
        "seções 5 e 6; esta seção reúne as que faltavam para o registro completo.", st["corpo"]))

    S.extend(figura("04_matriz_confusao_knn.png",
                    "Figura 13 — Matriz de confusão do KNN (k = 7): 38 dos 42 malignos "
                    "detectados, 4 falsos negativos.", st, largura=9.5 * cm))
    S.extend(figura("04_matriz_confusao_arvore_de_decisao.png",
                    "Figura 14 — Matriz de confusão da Árvore de Decisão "
                    "(profundidade 4) — o modelo mais fraco do conjunto, com 5 falsos negativos "
                    "e 3 falsos positivos.", st, largura=9.5 * cm))

    S.append(p("8.1 Índice das figuras e onde cada uma é discutida", st["h2"]))
    indice = [
        ["Arquivo", "Conteúdo", "Discussão"],
        ["<font face='Courier'>01_balanceamento_classes.png</font>", "Distribuição das classes", "§5.1.1"],
        ["<font face='Courier'>02_distribuicoes_por_classe.png</font>", "Distribuições por classe (top 6 features)", "§5.1.3"],
        ["<font face='Courier'>03_matriz_correlacao.png</font>", "Matriz de correlação de Pearson", "§5.1.4"],
        ["<font face='Courier'>04_matriz_confusao_*.png</font>", "Matriz de confusão dos 4 modelos", "§5.4.3 e §8"],
        ["<font face='Courier'>05_curvas_roc.png</font>", "Curvas ROC comparativas", "§5.4.3"],
        ["<font face='Courier'>06_feature_importance.png</font>", "Importância global (coeficientes)", "§5.5.1"],
        ["<font face='Courier'>07_shap_summary.png</font>", "SHAP summary plot", "§5.5.2"],
        ["<font face='Courier'>08_cnn_treino.png</font>", "Curvas de treino da CNN", "§6.1"],
        ["<font face='Courier'>09_cnn_matriz_confusao.png</font>", "Matriz de confusão da CNN", "§6.2"],
        ["<font face='Courier'>10_cnn_amostras.png</font>", "Previsões em amostras de teste", "§6.2"],
        ["<font face='Courier'>11_cnn_gradcam.png</font>", "Grad-CAM da CNN", "§6.3"],
    ]
    S.append(tabela(indice, st, [6.4 * cm, 7.4 * cm, CONTENT_W - 13.8 * cm], align_num=False))

    # ============================================================ 9. CONFORMIDADE
    S.append(PageBreak())
    S.append(p("9. Conformidade com o enunciado", st["h1"]))
    S.append(p(
        "Mapa item-a-item entre as exigências do desafio e a entrega correspondente.", st["corpo"]))

    conf = [
        ["Exigência do enunciado", "Onde está atendido"],
        ["<b>Dados e Modelos</b>", ""],
        ["Escolher dataset público de saúde/segurança da mulher e discutir o problema",
         "§2 deste PDF · <font face='Courier'>README §1–2</font> · notebook §1"],
        ["<b>Exploração de dados</b>", ""],
        ["Carregar a base e explorar suas características",
         "§5.1 · <font face='Courier'>src/data_loader.py</font>, <font face='Courier'>src/eda.py</font> · notebook §2–3"],
        ["Estatísticas descritivas e distribuições, com discussão",
         "§5.1.2–5.1.3 · Figuras 1 e 2 · notebook §3.2–3.4"],
        ["Identificar padrões de saúde e segurança feminina",
         "§5.1.3 (padrão morfológico maligno) · notebook §3.4"],
        ["<b>Pré-processamento</b>", ""],
        ["Limpeza, valores ausentes e inconsistentes",
         "§5.2.1–5.2.2 · <font face='Courier'>src/preprocessing.py</font>"],
        ["Pipeline de pré-processamento em Python",
         "§5.2.3 · <font face='Courier'>ColumnTransformer</font> + <font face='Courier'>Pipeline</font>"],
        ["Variáveis categóricas e numéricas em formato adequado",
         "§5.2.4 — base 100% numérica; ramo categórico já plugável no <font face='Courier'>ColumnTransformer</font>"],
        ["Análise de correlação",
         "§5.1.4 · Figura 3 · <font face='Courier'>eda.highly_correlated_pairs()</font>"],
        ["<b>Modelagem</b>", ""],
        ["Duas ou mais técnicas de classificação",
         "§5.3 — <b>quatro</b>: Regressão Logística, Árvore de Decisão, KNN e Random Forest"],
        ["Separação clara entre treino e teste",
         "§5.2.5 — split estratificado 80/20 + CV de 5 folds só no treino"],
        ["<b>Treinamento e avaliação</b>", ""],
        ["Treinar com o conjunto de treinamento", "§5.3.1 · <font face='Courier'>main.py</font> etapa 4"],
        ["Avaliar no teste com accuracy, recall e F1", "§5.4.2 · <font face='Courier'>reports/metricas_teste.csv</font>"],
        ["Discutir a escolha da métrica considerando o problema",
         "§5.4.1 — custo assimétrico do erro, recall como prioridade"],
        ["Interpretação com feature importance e SHAP",
         "§5.5 · Figuras 7 e 8 · <font face='Courier'>src/explainability.py</font>"],
        ["Discussão crítica: pode ser usado na prática? Como?",
         "§5.6 — usos, limitações e próximos passos"],
        ["O médico sempre tem a palavra final",
         "§1 (premissa) e §5.6.1 — reafirmado ao longo de todo o documento"],
        ["<b>EXTRA — Visão Computacional</b>", ""],
        ["Diagnóstico com dados de imagem usando CNN",
         "§6 · <font face='Courier'>src/vision.py</font>, <font face='Courier'>main_vision.py</font>, notebook da CNN"],
        ["<b>Código e organização</b>", ""],
        ["Projeto Python estruturado e documentado",
         "§3 — pacote modular com docstrings, tipagem e testes"],
        ["Notebook Jupyter ou scripts para demonstração",
         "2 notebooks com saídas salvas + 2 scripts CLI"],
        ["<b>Entregáveis da Fase 1</b>", ""],
        ["Arquivo PDF com link do repositório Git", "Este documento — capa"],
        ["Código-fonte completo", "Repositório (§3)"],
        ["README.md com instruções de execução", "<font face='Courier'>README.md</font> · §4"],
        ["Dockerfile (se usar docker)", "<font face='Courier'>Dockerfile</font> + <font face='Courier'>.dockerignore</font> · §4.2"],
        ["Dataset (ou link para download)", "§2 — CSV versionado + download automático"],
        ["Resultados obtidos (prints, gráficos e análises)", "§5, §6 e §8 — 11 figuras + 2 CSVs de métricas"],
        ["Relatório técnico (EDA, pré-processamento, modelos, resultados)", "§5 completo"],
        ["Vídeo de demonstração de até 15 min", "§10 — roteiro; link na capa"],
    ]
    S.append(tabela(conf, st, [9.2 * cm, CONTENT_W - 9.2 * cm], align_num=False))

    # ==================================================================== 10. VÍDEO
    S.append(PageBreak())
    S.append(p("10. Vídeo de demonstração", st["h1"]))
    S.append(p(
        f"<b>Link:</b> <link href='{video}' color='#1b4965'>{video}</link><br/>"
        "<b>Duração:</b> até 15 minutos (alvo: 11–13 min) · <b>Visibilidade:</b> público ou não listado",
        st["corpo"]))
    S.append(p(
        "O roteiro completo, com falas sugeridas e checklist de gravação, está em "
        "<font face='Courier'>docs/ROTEIRO_VIDEO.md</font> no repositório. Resumo do que é "
        "demonstrado:", st["corpo"]))

    roteiro = [
        ["Tempo", "Bloco", "O que é mostrado na tela"],
        ["0:00–0:50", "Abertura e problema",
         "Contexto do desafio e a premissa do copiloto clínico"],
        ["0:50–2:00", "Dataset e discussão",
         "<font face='Courier'>README §2</font>, o CSV e o bloco de convenção de rótulo em "
         "<font face='Courier'>config.py</font>"],
        ["2:00–3:00", "Arquitetura do projeto",
         "Árvore de arquivos: <font face='Courier'>src/</font>, notebooks, testes, Dockerfile"],
        ["3:00–4:30", "Análise exploratória",
         "Figuras 01, 02 e 03 — balanceamento, distribuições por classe e multicolinearidade"],
        ["4:30–5:30", "Pré-processamento",
         "<font face='Courier'>preprocessing.py</font> e <font face='Courier'>modeling.py</font> — "
         "o scaler dentro do <font face='Courier'>Pipeline</font> (anti-vazamento)"],
        ["5:30–7:30", "<b>Pipeline rodando ao vivo</b>",
         "<font face='Courier'>python main.py</font> no terminal, narrando as 7 etapas e a "
         "matriz de confusão detalhada"],
        ["7:30–9:00", "<b>Resultados e métrica</b>",
         "Tabela de métricas, matriz de confusão do campeão e curvas ROC; discussão do custo "
         "assimétrico"],
        ["9:00–10:15", "<b>Explicabilidade</b>",
         "Figuras 06 e 07 — coeficientes sob multicolinearidade e o SHAP que corrige a leitura"],
        ["10:15–12:00", "EXTRA — CNN",
         "Notebook da CNN, os dois pontos de operação e o Grad-CAM com leitura crítica"],
        ["12:00–12:45", "Provas de correção",
         "<font face='Courier'>python -m pytest -v</font>, com destaque para o teste anti-vazamento"],
        ["12:45–13:30", "<b>Discussão crítica</b>",
         "<font face='Courier'>README §7</font> — uso prático, limitações e a palavra final do médico"],
    ]
    S.append(tabela(roteiro, st, [2.2 * cm, 3.4 * cm, CONTENT_W - 5.6 * cm], align_num=False))
    S.append(p(
        "<b>Antes de gravar:</b> rode <font face='Courier'>python main.py</font> e "
        "<font face='Courier'>python main_vision.py</font> uma vez, para que as figuras estejam "
        "prontas e o BreastMNIST já esteja em cache — o download do dataset não deve aparecer "
        "no vídeo.", st["nota"]))

    # ==================================================================== ANEXOS
    S.append(PageBreak())
    S.append(p("Anexo A — Dataset e reprodutibilidade", st["h1"]))
    anexo = [
        ["Item", "Detalhe"],
        ["Base principal", "Breast Cancer Wisconsin (Diagnostic) — 569 × 30"],
        ["Como obter", "Automático via <font face='Courier'>sklearn.datasets.load_breast_cancer()</font>; "
         "cópia em <font face='Courier'>data/breast_cancer_wisconsin.csv</font>"],
        ["Link público", "<link href='https://www.kaggle.com/datasets/uciml/breast-cancer-wisconsin-data/data' "
         "color='#1b4965'>kaggle.com/datasets/uciml/breast-cancer-wisconsin-data</link> · "
         "<link href='https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic' "
         "color='#1b4965'>UCI ML Repository</link>"],
        ["Base EXTRA", "BreastMNIST (MedMNIST v2), 780 imagens de ultrassom"],
        ["Como obter", "Automático via pacote <font face='Courier'>medmnist</font> (download do Zenodo)"],
        ["Link público", "<link href='https://medmnist.com/' color='#1b4965'>medmnist.com</link> · "
         "<link href='https://zenodo.org/records/10519652' color='#1b4965'>Zenodo</link>"],
        ["Semente", "<font face='Courier'>RANDOM_STATE = 42</font>, definida em "
         "<font face='Courier'>src/config.py</font> e usada em split, CV, modelos e treino da CNN"],
        ["Ambiente", "Python 3.11; versões fixas em <font face='Courier'>requirements.txt</font>; "
         "imagem Docker disponível"],
        ["Observação", "Pequenas variações numéricas podem ocorrer entre versões de biblioteca; "
         "no mesmo ambiente os resultados são determinísticos"],
    ]
    S.append(tabela(anexo, st, [3.6 * cm, CONTENT_W - 3.6 * cm], align_num=False))

    S.append(p("Anexo B — Referências", st["h1"]))
    S.extend(bullets([
        "Wolberg, W. H., Street, W. N. &amp; Mangasarian, O. L. (1995). "
        "<i>Breast Cancer Wisconsin (Diagnostic) Data Set</i>. UCI Machine Learning Repository.",
        "Yang, J. et al. (2023). <i>MedMNIST v2: A large-scale lightweight benchmark for 2D and "
        "3D biomedical image classification</i>. Scientific Data, 10(1).",
        "Al-Dhabyani, W., Gomaa, M., Khaled, H. &amp; Fahmy, A. (2020). <i>Dataset of breast "
        "ultrasound images</i>. Data in Brief, 28.",
        "Lundberg, S. M. &amp; Lee, S.-I. (2017). <i>A unified approach to interpreting model "
        "predictions</i>. NeurIPS.",
        "Selvaraju, R. R. et al. (2017). <i>Grad-CAM: Visual explanations from deep networks via "
        "gradient-based localization</i>. ICCV.",
        "Pedregosa, F. et al. (2011). <i>Scikit-learn: Machine learning in Python</i>. JMLR, 12.",
    ], st))

    S.append(Spacer(1, 0.8 * cm))
    S.append(p(
        "<b>Declaração de uso responsável.</b> Este projeto é um trabalho acadêmico. O sistema "
        "descrito <b>não é um dispositivo médico certificado</b> e não deve ser utilizado para "
        "decisão clínica sem validação externa, aprovação regulatória e supervisão profissional. "
        "Toda saída do modelo é uma sugestão acompanhada de explicação — <b>a decisão "
        "diagnóstica é sempre do médico</b>.", st["nota"]))

    doc.build(S)
    return OUTPUT


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="Gera o PDF entregável do Tech Challenge Fase 1.")
    ap.add_argument("--repo", default=PLACEHOLDER_REPO, help="URL do repositório Git")
    ap.add_argument("--video", default=PLACEHOLDER_VIDEO, help="URL do vídeo no YouTube")
    ap.add_argument("--autores", default="[preencher: nome do(s) integrante(s)]",
                    help="Nome do(s) autor(es)")
    ap.add_argument("--turma", default="IADT — Fase 1", help="Turma / fase")
    args = ap.parse_args()

    caminho = build(args.repo, args.video, args.autores, args.turma)
    tamanho = caminho.stat().st_size / 1024
    print(f"PDF gerado: {caminho}  ({tamanho:.0f} KB)")
    if args.repo == PLACEHOLDER_REPO or args.video == PLACEHOLDER_VIDEO:
        print("AVISO: repositorio e/ou video ainda estao com o valor de exemplo.")
        print("       Regere com --repo <URL> --video <URL> --autores \"Nome\".")


if __name__ == "__main__":
    main()
