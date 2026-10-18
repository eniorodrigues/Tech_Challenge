"""
Mapa de fundo (basemap) para as figuras estáticas, sem dependências pesadas.

Baixa os *tiles* padrão do OpenStreetMap na projeção Web Mercator, costura
com Pillow, **clareia** a imagem (para as rotas coloridas se destacarem sobre
o mapa) e devolve a imagem + uma função que converte (lat, lon) em pixel.

Política de uso dos tiles do OSM respeitada: User-Agent identificado, poucos
tiles (uma área, uma vez) e cache local em ``.cache/tiles`` — a mesma área
nunca é baixada de novo.

Sem internet, devolve ``None`` e os mapas são desenhados sobre fundo liso.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from ..config import CACHE_DIR

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_SIZE = 256
ATTRIBUTION = "© OpenStreetMap contributors"
CLAREAMENTO = 0.45   # 0 = mapa original, 1 = branco
USER_AGENT = "MedRoute-TechChallenge/2.0 (projeto educacional FIAP)"


def _lonlat_to_px(lon: float, lat: float, z: int) -> tuple[float, float]:
    n = 2 ** z * TILE_SIZE
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n
    return x, y


@dataclass
class Basemap:
    image: Image.Image
    zoom: int
    origin_px: tuple[float, float]   # pixel global do canto superior esquerdo

    def project(self) -> Callable[[float, float], tuple[float, float]]:
        ox, oy = self.origin_px

        def f(lat: float, lon: float) -> tuple[float, float]:
            x, y = _lonlat_to_px(lon, lat, self.zoom)
            return x - ox, y - oy

        return f


def _baixar_tile(z: int, x: int, y: int, timeout: float = 15.0) -> Image.Image | None:
    destino = CACHE_DIR / "tiles" / f"{z}_{x}_{y}.png"
    if destino.exists():
        try:
            return Image.open(destino).convert("RGB")
        except OSError:
            destino.unlink(missing_ok=True)
    try:
        import httpx

        url = TILE_URL.format(z=z, x=x, y=y)
        r = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.content)
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def build_basemap(
    lats: list[float], lons: list[float], margin: float = 0.12, zoom: int | None = None,
    max_tiles: int = 42,
) -> Basemap | None:
    """Monta o basemap que cobre os pontos (com margem relativa)."""
    la0, la1 = min(lats), max(lats)
    lo0, lo1 = min(lons), max(lons)
    dla, dlo = (la1 - la0) or 0.01, (lo1 - lo0) or 0.01
    la0, la1 = la0 - dla * margin, la1 + dla * margin
    lo0, lo1 = lo0 - dlo * margin, lo1 + dlo * margin

    if zoom is None:
        zoom = 12
        for z in range(14, 9, -1):
            x0, y0 = _lonlat_to_px(lo0, la1, z)
            x1, y1 = _lonlat_to_px(lo1, la0, z)
            n_tiles = (int(x1 // TILE_SIZE) - int(x0 // TILE_SIZE) + 1) * \
                      (int(y1 // TILE_SIZE) - int(y0 // TILE_SIZE) + 1)
            if n_tiles <= max_tiles and (x1 - x0) <= 2600:
                zoom = z
                break

    x0, y0 = _lonlat_to_px(lo0, la1, zoom)
    x1, y1 = _lonlat_to_px(lo1, la0, zoom)
    tx0, ty0 = int(x0 // TILE_SIZE), int(y0 // TILE_SIZE)
    tx1, ty1 = int(x1 // TILE_SIZE), int(y1 // TILE_SIZE)

    mosaico = Image.new("RGB", ((tx1 - tx0 + 1) * TILE_SIZE, (ty1 - ty0 + 1) * TILE_SIZE),
                        "#f2f2f0")
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            tile = _baixar_tile(zoom, tx, ty)
            if tile is None:
                return None
            if tile.size != (TILE_SIZE, TILE_SIZE):
                tile = tile.resize((TILE_SIZE, TILE_SIZE))
            mosaico.paste(tile, ((tx - tx0) * TILE_SIZE, (ty - ty0) * TILE_SIZE))

    recorte = (int(x0 - tx0 * TILE_SIZE), int(y0 - ty0 * TILE_SIZE),
               int(x1 - tx0 * TILE_SIZE), int(y1 - ty0 * TILE_SIZE))
    imagem = mosaico.crop(recorte)
    # Clareia e dessatura de leve: o mapa vira contexto, as rotas são a informação.
    from PIL import ImageEnhance

    imagem = ImageEnhance.Color(imagem).enhance(0.55)
    imagem = Image.blend(imagem, Image.new("RGB", imagem.size, "#ffffff"), CLAREAMENTO)
    return Basemap(image=imagem, zoom=zoom, origin_px=(int(x0), int(y0)))


def cache_dir() -> Path:
    return CACHE_DIR / "tiles"
