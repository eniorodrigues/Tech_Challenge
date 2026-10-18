"""
Quadros-chave da evolução do algoritmo genético para o vídeo.

Roda um GA **puro** (sem sementes heurísticas e sem busca local) partindo de
uma população aleatória, e desenha cada melhoria do melhor indivíduo: rotas
no mapa à esquerda, curva de convergência e números à direita.

    python scripts/video/evolucao.py [--recapturar]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from medroute.ga import GAConfig, GeneticAlgorithm  # noqa: E402
from medroute.plan import RoutePlan  # noqa: E402
from medroute.problem import Problem  # noqa: E402
from medroute.scenario import default_scenario  # noqa: E402
from medroute.viz import style  # noqa: E402
from medroute.viz.static_map import draw_routes_on_ax  # noqa: E402
from medroute.viz.tiles import build_basemap  # noqa: E402
from roteiro import EVOLUCAO_DIR  # noqa: E402

GERACOES = 250


def _escolher(snapshots, maximo: int = 22):
    """Até ``maximo`` melhorias, mais densas no início (onde tudo muda)."""
    if len(snapshots) <= maximo:
        return snapshots
    idx = sorted({min(len(snapshots) - 1, int(round((len(snapshots) - 1) * (k / (maximo - 1)) ** 1.6)))
                  for k in range(maximo)})
    return [snapshots[i] for i in idx]


def gerar_quadros(recapturar: bool = False) -> list[Path]:
    EVOLUCAO_DIR.mkdir(parents=True, exist_ok=True)
    existentes = sorted(EVOLUCAO_DIR.glob("q_*.png"))
    if existentes and not recapturar:
        print(f"  [cache] {len(existentes)} quadros da evolução")
        return existentes
    for f in existentes:
        f.unlink()

    sc = default_scenario()
    prob = Problem(sc)
    cfg = GAConfig(generations=GERACOES, seed=7, heuristic_seeds=False, local_search=False,
                   final_polish=False, patience=None)
    res = GeneticAlgorithm(prob, cfg).run()
    hist = [h.best for h in res.history]
    plano = RoutePlan.from_evaluation(prob, res.evaluation, "GA")
    dep = sc.depot
    base = build_basemap([dep.lat] + [d.lat for d in sc.deliveries],
                         [dep.lon] + [d.lon for d in sc.deliveries])
    style.apply_style()
    saidas = []
    for n, snap in enumerate(_escolher(res.snapshots)):
        ev = prob.evaluate(snap.routes)
        ids = [[sc.deliveries[i - 1].id for i in r] for r in snap.routes]
        fig = plt.figure(figsize=(16, 9))
        ax = fig.add_axes((0.01, 0.03, 0.60, 0.86))
        draw_routes_on_ax(ax, plano, base, routes_override=ids, show_late=False, marker_scale=0.9)
        fig.text(0.012, 0.955, "Evolução do melhor indivíduo — GA partindo de população aleatória",
                 fontsize=19, weight="bold", color=style.INK)
        fig.text(0.012, 0.915, "sem sementes heurísticas e sem busca local · semente 7",
                 fontsize=11.5, color=style.INK_2)
        axc = fig.add_axes((0.67, 0.42, 0.31, 0.44))
        g = snap.generation
        axc.plot(range(len(hist)), hist, color=style.DEEMPHASIS, linewidth=1.5)
        axc.plot(range(g + 1), hist[:g + 1], color=style.ACCENT, linewidth=2.4)
        axc.scatter([g], [hist[g]], s=60, color=style.ACCENT, edgecolors="white", zorder=5)
        axc.set_yscale("log")
        axc.set_xlabel("geração")
        axc.set_ylabel("melhor fitness (log)")
        axc.set_title("Convergência", fontsize=13)
        viavel = ev.feasible
        linhas = [("geração", f"{g}"), ("fitness", f"{snap.fitness:,.0f}".replace(",", ".")),
                  ("distância", f"{ev.distance_km:.1f} km".replace(".", ",")),
                  ("violações", f"{ev.n_violations}"),
                  ("viável", "sim" if viavel else "não")]
        y = 0.32
        for rot, val in linhas:
            fig.text(0.67, y, rot, fontsize=15, color=style.INK_2)
            fig.text(0.98, y, val, fontsize=22, weight="bold", ha="right",
                     color=(style.STATUS_GOOD if (rot == "viável" and viavel) else style.INK))
            y -= 0.058
        destino = EVOLUCAO_DIR / f"q_{n:02d}.png"
        fig.savefig(destino, dpi=120)
        plt.close(fig)
        saidas.append(destino)
        print(f"  quadro {n:02d}: geração {g:3d}  fitness {snap.fitness:9.1f}  "
              f"violações {ev.n_violations}", flush=True)
    _ = math  # (mantido para ajustes de curva)
    return saidas


if __name__ == "__main__":  # pragma: no cover
    import argparse

    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--recapturar", action="store_true")
    gerar_quadros(ap.parse_args().recapturar)
