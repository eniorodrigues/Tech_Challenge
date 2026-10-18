"""
Geometria: distância entre pontos geográficos.

O código base calculava distância **euclidiana em pixels** entre cidades
desenhadas na tela. Aqui os pontos são coordenadas reais (latitude/longitude),
então usamos a fórmula de **haversine** (distância sobre a esfera) e
multiplicamos por um **fator de tortuosidade** (*circuity factor*): a malha
viária obriga o veículo a andar mais do que a linha reta. Para áreas urbanas,
a literatura reporta fatores entre 1,2 e 1,4 (Ballou et al., 2002; Boscoe et
al., 2012) — usamos 1,35 para São Paulo.

A matriz é calculada uma única vez por instância e vetorizada em NumPy.
"""

from __future__ import annotations

import math

import numpy as np

EARTH_RADIUS_KM = 6371.0088  # raio médio da Terra (IUGG)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em linha reta (grande círculo) entre dois pontos, em km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def distance_matrix_km(coords: np.ndarray | list[tuple[float, float]],
                       circuity: float = 1.0) -> np.ndarray:
    """Matriz NxN de distâncias (km) entre pontos ``(lat, lon)``.

    Parameters
    ----------
    coords:
        Array ``(N, 2)`` com latitude e longitude em graus.
    circuity:
        Fator multiplicativo para estimar a distância por ruas.
    """
    c = np.radians(np.asarray(coords, dtype=float))
    lat = c[:, 0][:, None]
    lon = c[:, 1][:, None]
    dphi = lat.T - lat
    dlmb = lon.T - lon
    a = np.sin(dphi / 2) ** 2 + np.cos(lat) * np.cos(lat.T) * np.sin(dlmb / 2) ** 2
    d = 2 * EARTH_RADIUS_KM * np.arcsin(np.minimum(1.0, np.sqrt(a)))
    np.fill_diagonal(d, 0.0)
    return d * float(circuity)


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Azimute (0–360°) do ponto 1 para o ponto 2 — usado pela heurística *sweep*."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0
