"""
Visualizador ao vivo em pygame — a janela do ``tsp.py`` do código base,
evoluída para o VRP.

O original desenhava, a cada geração, o gráfico de fitness (Matplotlib
convertido com ``tostring_rgb``, que não existe mais no Matplotlib ≥ 3.10) e
a melhor rota em azul. Aqui:

* o gráfico de convergência é desenhado direto com pygame (mais rápido e
  sem depender de API removida do Matplotlib);
* cada veículo tem sua cor, as paradas mostram a prioridade (tamanho) e a
  central aparece como um quadrado;
* o laço evolutivo é o motor completo do MedRoute (``GeneticAlgorithm``),
  ligado por *callback* — tecla **Q** ou fechar a janela interrompe.

Uso::

    python main.py visualizar --geracoes 300
    python -m medroute.viz.pygame_viewer --frames saida/   # grava PNGs (sem janela)
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from ..ga import GAConfig, GeneticAlgorithm
from ..problem import Problem
from ..scenario import default_scenario
from . import style

LARGURA, ALTURA = 1280, 720
PAINEL = 470          # largura do gráfico à esquerda (o base usava 450)
FPS = 30


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def run_viewer(generations: int = 300, seed: int = 42, frames_dir: str | Path | None = None,
               headless: bool = False) -> int:
    if headless or frames_dir:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    sc = default_scenario()
    prob = Problem(sc)
    pygame.init()
    tela = pygame.display.set_mode((LARGURA, ALTURA))
    pygame.display.set_caption("MedRoute — algoritmo genético ao vivo (evolução do código base)")
    relogio = pygame.time.Clock()
    fonte = pygame.font.SysFont("Segoe UI", 17)
    fonte_titulo = pygame.font.SysFont("Segoe UI", 22, bold=True)

    # Projeção simples lat/lon → tela no painel da direita, mantendo proporção.
    pts = [(sc.depot.lat, sc.depot.lon)] + [(d.lat, d.lon) for d in sc.deliveries]
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    kx = math.cos(math.radians(sum(lats) / len(lats)))
    w_area, h_area = LARGURA - PAINEL - 40, ALTURA - 90
    esc = min(w_area / ((max(lons) - min(lons)) * kx), h_area / (max(lats) - min(lats)))

    def xy(i: int) -> tuple[int, int]:
        lat, lon = pts[i]
        x = PAINEL + 20 + (lon - min(lons)) * kx * esc
        y = 70 + (max(lats) - lat) * esc
        return int(x), int(y)

    historico: list[float] = []
    destino = Path(frames_dir) if frames_dir else None
    if destino:
        destino.mkdir(parents=True, exist_ok=True)

    def desenhar(st, rotas) -> bool:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_q):
                return False
        historico.append(st.best)
        tela.fill(_hex(style.SURFACE))

        # --- gráfico de convergência (log10 do melhor fitness)
        x0, y0, x1, y1 = 60, 90, PAINEL - 20, ALTURA - 70
        pygame.draw.line(tela, _hex(style.AXIS), (x0, y1), (x1, y1), 1)
        pygame.draw.line(tela, _hex(style.AXIS), (x0, y0), (x0, y1), 1)
        logs = [math.log10(max(v, 1.0)) for v in historico]
        lo, hi = min(logs), max(logs) + 1e-9
        n = max(len(logs) - 1, 1)
        linha = [(x0 + (x1 - x0) * i / max(n, generations - 1),
                  y1 - (y1 - y0) * (v - lo) / (hi - lo)) for i, v in enumerate(logs)]
        if len(linha) > 1:
            pygame.draw.lines(tela, _hex(style.ACCENT), False, linha, 2)
        tela.blit(fonte_titulo.render("Convergência (log do melhor fitness)", True,
                                      _hex(style.INK)), (20, 30))
        tela.blit(fonte.render("geração", True, _hex(style.INK_2)), ((x0 + x1) // 2 - 30, y1 + 12))

        # --- rotas
        for v, rota in enumerate(rotas):
            if not rota:
                continue
            cor = _hex(style.vehicle_color(v))
            caminho = [xy(0)] + [xy(i) for i in rota] + [xy(0)]
            pygame.draw.lines(tela, cor, False, caminho, 3)
            for i in rota:
                raio = {3: 8, 2: 6, 1: 5}[int(prob.priority[i])]
                pygame.draw.circle(tela, (255, 255, 255), xy(i), raio + 2)
                pygame.draw.circle(tela, cor, xy(i), raio)
        cx, cy = xy(0)
        pygame.draw.rect(tela, _hex(style.INK), (cx - 9, cy - 9, 18, 18))

        info = (f"geração {st.generation}   fitness {st.best:,.1f}   {st.best_distance_km:.1f} km   "
                f"viável: {'sim' if st.best_feasible else 'não'}   [Q] sair")
        tela.blit(fonte_titulo.render("MedRoute — rotas do melhor indivíduo", True, _hex(style.INK)),
                  (PAINEL + 20, 20))
        tela.blit(fonte.render(info, True, _hex(style.INK_2)), (PAINEL + 20, ALTURA - 32))
        pygame.display.flip()
        if destino:
            pygame.image.save(tela, str(destino / f"{st.generation:04d}.png"))
        else:
            relogio.tick(FPS)
        return True

    cfg = GAConfig(generations=generations, seed=seed, patience=None)
    GeneticAlgorithm(prob, cfg, callback=desenhar).run()

    if not (headless or destino):
        esperando = True
        while esperando:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_q):
                    esperando = False
            relogio.tick(10)
    pygame.quit()
    return 0


if __name__ == "__main__":  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--geracoes", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--frames", help="pasta para salvar um PNG por geração (sem janela)")
    a = ap.parse_args()
    raise SystemExit(run_viewer(a.geracoes, a.seed, a.frames))
