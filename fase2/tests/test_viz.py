"""Visualizações (sem baixar mapa de fundo)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from medroute.viz import plots, static_map
from medroute.viz.folium_map import build_route_map, save_route_map


def test_mapa_interativo_tem_todos_os_veiculos_e_paradas(plano_padrao, tmp_path):
    ga, _ = plano_padrao
    html = build_route_map(ga).get_root().render()
    for r in ga.routes:
        if r.used:
            assert r.vehicle_name in html
            for s in r.stops:
                assert s.delivery_id in html
    caminho = save_route_map(ga, tmp_path / "mapa.html")
    assert caminho.stat().st_size > 20_000


def test_mapa_estatico_sem_basemap(plano_padrao, tmp_path):
    ga, _ = plano_padrao
    static_map.plot_route_map(ga, tmp_path / "mapa.png", basemap=False)
    static_map.plot_vehicle_facets(ga, tmp_path / "facetas.png", basemap=False)
    assert (tmp_path / "mapa.png").stat().st_size > 30_000
    plt.close("all")


def test_graficos_de_analise(plano_padrao, problema_padrao, tmp_path):
    from medroute.ga import GAConfig, GeneticAlgorithm

    ga, atual = plano_padrao
    res = GeneticAlgorithm(problema_padrao, GAConfig(generations=15, seed=1)).run()
    plots.plot_convergence(res.history_dicts, tmp_path / "conv.png")
    plots.plot_gantt(ga, tmp_path / "gantt.png")
    plots.plot_utilization(ga, tmp_path / "util.png")
    df = pd.DataFrame([
        {"metodo": "GA", "km": 250, "no_prazo_pct": 97, "violacoes": 0, "fitness": 500},
        {"metodo": "Outro", "km": 300, "no_prazo_pct": 60, "violacoes": 1, "fitness": 9000},
    ])
    plots.plot_methods_comparison(df, "GA", tmp_path / "comp.png")
    plots.plot_fitness_distribution(
        pd.DataFrame({"config": ["a", "a", "b"], "fitness": [500, 510, 600]}), tmp_path / "abl.png")
    plots.plot_convergence_compare({"x": [[10, 5, 3], [9, 6, 2]]}, tmp_path / "cc.png")
    for nome in ("conv", "gantt", "util", "comp", "abl", "cc"):
        assert (tmp_path / f"{nome}.png").exists()
    plt.close("all")
