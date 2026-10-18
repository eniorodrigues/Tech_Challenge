"""
Gera os diagramas de arquitetura em PNG (relatório, PDF e vídeo).

    python scripts/gerar_diagramas.py

Saídas em ``reports/figures/00*_*.png``. As versões em Mermaid (renderizadas
pelo GitHub) estão em ``docs/ARQUITETURA.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from medroute.config import FIGURES_DIR  # noqa: E402
from medroute.viz import style  # noqa: E402

FUNDO_CAIXA = "#ffffff"
BORDA = "#d6d5cf"
DESTAQUE_FUNDO = "#eaf2fc"
DESTAQUE_BORDA = "#86b6ef"
SETA = "#898781"


def _tela(titulo: str, subtitulo: str = ""):
    style.apply_style()
    fig = plt.figure(figsize=(16, 9))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")
    ax.text(0.45, 8.5, titulo, fontsize=21, weight="bold", color=style.INK, va="center")
    if subtitulo:
        ax.text(0.45, 8.05, subtitulo, fontsize=12, color=style.INK_2, va="center")
    return fig, ax


def caixa(ax, x, y, w, h, titulo, corpo="", destaque=False, tam=11.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                facecolor=DESTAQUE_FUNDO if destaque else FUNDO_CAIXA,
                                edgecolor=DESTAQUE_BORDA if destaque else BORDA, linewidth=1.4))
    if corpo:
        ax.text(x + w / 2, y + h - 0.28, titulo, ha="center", va="top", fontsize=tam,
                weight="bold", color=style.INK)
        ax.text(x + w / 2, y + h - 0.68, corpo, ha="center", va="top", fontsize=tam - 2,
                color=style.INK_2, linespacing=1.35)
    else:
        ax.text(x + w / 2, y + h / 2, titulo, ha="center", va="center", fontsize=tam,
                weight="bold", color=style.INK)
    return (x, y, w, h)


def seta(ax, a, b, de="r", para="l", texto="", curva=0.0):
    def ponto(c, lado):
        x, y, w, h = c
        return {"r": (x + w, y + h / 2), "l": (x, y + h / 2), "t": (x + w / 2, y + h),
                "b": (x + w / 2, y)}[lado]

    p0, p1 = ponto(a, de), ponto(b, para)
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=14, color=SETA,
                                 linewidth=1.4, connectionstyle=f"arc3,rad={curva}",
                                 shrinkA=4, shrinkB=4))
    if texto:
        ax.text((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 + 0.12, texto, ha="center",
                fontsize=8.5, color=style.MUTED)


def grupo(ax, x, y, w, h, rotulo):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.18",
                                facecolor="#f4f4f1", edgecolor="none"))
    ax.text(x + 0.18, y + h - 0.22, rotulo.upper(), fontsize=9.5, weight="bold",
            color=style.MUTED, va="top")


# ---------------------------------------------------------------------------
def arquitetura(destino: Path) -> None:
    fig, ax = _tela("MedRoute — arquitetura da solução",
                    "Do cenário do dia ao plano de rotas, aos mapas e aos textos gerados pela LLM")
    grupo(ax, 0.3, 0.45, 3.3, 7.2, "Entrada")
    grupo(ax, 3.9, 0.45, 4.3, 7.2, "Otimização")
    grupo(ax, 8.5, 0.45, 2.9, 7.2, "Plano")
    grupo(ax, 11.7, 0.45, 4.0, 7.2, "Saídas e interfaces")

    c1 = caixa(ax, 0.5, 5.2, 2.9, 1.9, "Cenário do dia",
               "entregas · frota · depósito\nscenario.py · JSON\n(sintético, São Paulo)")
    c2 = caixa(ax, 0.5, 2.95, 2.9, 1.9, "Regras de negócio",
               "prioridade e SLA\njanelas · jornada\ncadeia fria · controlados")
    c3 = caixa(ax, 0.5, 0.7, 2.9, 1.9, "Distâncias",
               "haversine × 1,35\n(tortuosidade urbana)\ngeo.py")

    p = caixa(ax, 4.15, 5.35, 3.8, 1.75, "Problem + fitness",
              "km + prioridade + atraso\n+ penalidades · problem.py", destaque=True)
    g = caixa(ax, 4.15, 2.95, 3.8, 2.05, "Algoritmo genético",
              "permutação + separadores\nOX · PMX · ERX · BCRC\nmutações · 2-opt · imigrantes", destaque=True)
    b = caixa(ax, 4.15, 0.7, 3.8, 1.9, "Comparativo",
              "vizinho · Clarke-Wright · sweep\nsimulated annealing · OR-Tools\nTSP do código base")

    plano = caixa(ax, 8.7, 4.2, 2.5, 2.4, "RoutePlan",
                  "rotas e horários\nkm · R$ · horas\nCO2 · SLA · ocupação\nplan.py", destaque=True)
    semana = caixa(ax, 8.7, 1.4, 2.5, 1.9, "Semana simulada",
                   "5 dias · atual x GA\noperations.py")

    v = caixa(ax, 11.9, 5.35, 3.6, 1.75, "Visualização",
              "mapa folium (HTML) · PNG OSM\nGantt · convergência · viz/")
    l = caixa(ax, 11.9, 2.95, 3.6, 2.05, "LLM (OpenRouter)",
              "contexto JSON → prompt → Nemotron\nguardrails (nota de fidelidade)\ncache · fallback · modo offline",
              destaque=True)
    i = caixa(ax, 11.9, 0.7, 3.6, 1.9, "Interfaces",
              "CLI main.py · API FastAPI\npainel Streamlit · notebook\npygame (código base)")

    for c in (c1, c2, c3):
        seta(ax, c, p, curva=0.0)
    seta(ax, p, g, "b", "t")
    seta(ax, g, plano, "r", "l")
    seta(ax, b, plano, "r", "l")
    seta(ax, plano, v, "r", "l")
    seta(ax, plano, l, "r", "l")
    seta(ax, plano, i, "r", "l")
    seta(ax, semana, l, "r", "l")
    fig.savefig(destino, dpi=120)
    plt.close(fig)


def cromossomo(destino: Path) -> None:
    fig, ax = _tela("Representação genética — permutação com separadores",
                    "N entregas + (K − 1) separadores; o segmento k é a rota do veículo k. "
                    "Com K = 1, é exatamente o cromossomo do TSP do código base.")
    genes = [3, 6, 1, "|", 5, 2, "|", 7, 4]
    rotulos = ["E03", "E06", "E01", "sep.", "E05", "E02", "sep.", "E07", "E04"]
    cores = [0, 0, 0, None, 1, 1, None, 2, 2]
    x0, y0, w = 1.4, 5.0, 1.38
    ax.text(x0, 6.85, "Cromossomo", fontsize=13, weight="bold", color=style.INK)
    for j, (gene, rot, cor) in enumerate(zip(genes, rotulos, cores)):
        x = x0 + j * w
        if cor is None:
            ax.add_patch(FancyBboxPatch((x + 0.5, y0 - 0.1), 0.18, 1.5,
                                        boxstyle="round,pad=0.01,rounding_size=0.05",
                                        facecolor=style.INK, edgecolor="none"))
            ax.text(x + 0.59, y0 - 0.45, "separador", ha="center", fontsize=9, color=style.INK_2)
            continue
        c = style.vehicle_color(cor)
        ax.add_patch(FancyBboxPatch((x + 0.1, y0), w - 0.2, 1.3,
                                    boxstyle="round,pad=0.02,rounding_size=0.12",
                                    facecolor=c, edgecolor="white", linewidth=2))
        ax.text(x + w / 2, y0 + 0.78, str(gene), ha="center", va="center", fontsize=20,
                weight="bold", color="white" if cor != 3 else style.INK)
        ax.text(x + w / 2, y0 + 0.3, rot, ha="center", va="center", fontsize=10,
                color="white" if cor != 3 else style.INK)
    ax.text(x0, 3.6, "Decodificação", fontsize=13, weight="bold", color=style.INK)
    rotas = [("V1 · Van Refrigerada 01", "Central → E03 → E06 → E01 → Central", 0),
             ("V2 · Van 02 (cofre)", "Central → E05 → E02 → Central", 1),
             ("V3 · Van Elétrica 03", "Central → E07 → E04 → Central", 2)]
    for k, (veic, rota, cor) in enumerate(rotas):
        y = 2.95 - k * 0.72
        ax.add_patch(FancyBboxPatch((x0, y - 0.18), 0.5, 0.36, boxstyle="round,pad=0.01,rounding_size=0.06",
                                    facecolor=style.vehicle_color(cor), edgecolor="none"))
        ax.text(x0 + 0.75, y, veic, fontsize=12.5, weight="bold", color=style.INK, va="center")
        ax.text(x0 + 4.6, y, rota, fontsize=12.5, color=style.INK_2, va="center")
    ax.text(x0, 0.55, "Por que assim: toda permutação é uma solução completa (cada entrega aparece uma vez); "
            "os operadores de permutação valem sem adaptação;\no GA decide quantas entregas cada veículo faz movendo "
            "separadores; inverter um trecho com separador troca as caudas de duas rotas (2-opt*).",
            fontsize=11, color=style.INK_2, va="bottom")
    fig.savefig(destino, dpi=120)
    plt.close(fig)


def ciclo_ga(destino: Path) -> None:
    fig, ax = _tela("Ciclo do algoritmo genético do MedRoute",
                    "A espinha dorsal do tsp.py do código base, com cada peça trocada por uma versão mais forte")
    passos = [
        ("População inicial", "aleatória + heurísticas\n(vizinho, sweep, economias)"),
        ("Avaliação (fitness)", "km + prioridade + atraso\n+ penalidades (cache)"),
        ("Seleção", "torneio k=3\n(roleta/ranking/truncamento)"),
        ("Crossover", "OX · PMX · ERX · BCRC\n(portfólio por sorteio)"),
        ("Mutação", "swap · inversão · inserção\nscramble · prioridade · reparo"),
        ("Nova geração", "elitismo (2) + anti-duplicata\nimigrantes se estagnar"),
    ]
    caixas = []
    xs = [0.5, 3.1, 5.7, 8.3, 10.9, 13.5]
    for (t, c), x in zip(passos, xs):
        caixas.append(caixa(ax, x, 4.6, 2.3, 1.9, t, c, destaque=t in ("Crossover", "Mutação")))
    for a, b in zip(caixas, caixas[1:]):
        seta(ax, a, b)
    ls = caixa(ax, 8.3, 1.6, 4.9, 1.7, "Busca local (memético)",
               "2-opt no melhor a cada 10 gerações; relocate + troca\nentre rotas a cada 50 e no polimento final")
    fim = caixa(ax, 13.5, 1.6, 2.3, 1.7, "Parada", "paciência (250)\nlimite de gerações\nou de tempo")
    seta(ax, caixas[-1], caixas[1], "t", "t", texto="próxima geração", curva=0.25)
    seta(ax, caixas[1], ls, "b", "l", curva=0.2)
    seta(ax, ls, fim, "r", "l")
    ax.text(0.5, 0.75, "Correções em relação ao código base: o crossover recombinava o pai com ele mesmo; "
            "a mutação só trocava vizinhos; não havia restrições,\nheurística de inicialização nem busca local.",
            fontsize=11, color=style.INK_2)
    fig.savefig(destino, dpi=120)
    plt.close(fig)


def fluxo_llm(destino: Path) -> None:
    fig, ax = _tela("Integração com a LLM — do plano ao texto conferido",
                    "A LLM não calcula nada: recebe números prontos, redige, e cada resposta é auditada contra os dados")
    a = caixa(ax, 0.4, 4.7, 2.6, 2.0, "Plano + KPIs", "RoutePlan\nachados medidos\nsimulações 'e se'")
    b = caixa(ax, 3.4, 4.7, 2.7, 2.0, "Contexto JSON", "compacto, chaves pt-BR\nsó dados necessários\n(context.py)")
    c = caixa(ax, 6.5, 4.7, 2.8, 2.0, "Prompt", "system: papel + regras\n<dados>…</dados>\nesqueleto + 1 exemplo", destaque=True)
    d = caixa(ax, 9.7, 4.7, 2.8, 2.0, "OpenRouter", "Nemotron 3 Ultra (free)\nfallback de modelos\ncache em disco")
    e = caixa(ax, 12.9, 4.7, 2.7, 2.0, "Guardrails", "paradas · ordem · horários\nIDs · números · requisitos\nnota 0–100", destaque=True)
    for x, y in ((a, b), (b, c), (c, d), (d, e)):
        seta(ax, x, y)
    off = caixa(ax, 9.7, 1.9, 2.8, 1.8, "Modo offline", "sem chave, sem rede\nou cota esgotada\n→ templates")
    out = caixa(ax, 12.9, 1.9, 2.7, 1.8, "Produtos", "instruções · relatórios\nsugestões · chat")
    seta(ax, d, off, "b", "t", texto="falha / 429")
    seta(ax, off, out, "r", "l")
    seta(ax, e, out, "b", "t")
    ax.text(0.4, 2.95, "Temperatura por tarefa", fontsize=12, weight="bold", color=style.INK)
    ax.text(0.4, 2.55, "0,2 — instruções e respostas factuais\n0,4 — relatórios e sugestões",
            fontsize=11, color=style.INK_2, va="top", linespacing=1.5)
    ax.text(0.4, 1.35, "Versão do prompt registrada em cada resposta;\n"
            "a avaliação automática pegou um erro real na v1 → regra nova na v2.",
            fontsize=11, color=style.INK_2, va="top", linespacing=1.5)
    fig.savefig(destino, dpi=120)
    plt.close(fig)


def main() -> int:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    arquitetura(FIGURES_DIR / "00_arquitetura.png")
    cromossomo(FIGURES_DIR / "00b_cromossomo.png")
    ciclo_ga(FIGURES_DIR / "00c_ciclo_ga.png")
    fluxo_llm(FIGURES_DIR / "00d_fluxo_llm.png")
    for f in sorted(FIGURES_DIR.glob("00*.png")):
        print(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
