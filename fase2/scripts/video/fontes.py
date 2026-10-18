"""Fontes do vídeo com fallback (Windows → Matplotlib → bitmap)."""

from __future__ import annotations

import functools
from pathlib import Path

from PIL import ImageFont


def _dir_fontes_matplotlib() -> Path:
    try:
        import matplotlib

        return Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    except Exception:  # pragma: no cover
        return Path("/nonexistent")


_WIN = Path("C:/Windows/Fonts")
_MPL = _dir_fontes_matplotlib()

CANDIDATAS = {
    "sans": [_WIN / "segoeui.ttf", _WIN / "arial.ttf", _MPL / "DejaVuSans.ttf"],
    "sans_bold": [_WIN / "segoeuib.ttf", _WIN / "arialbd.ttf", _MPL / "DejaVuSans-Bold.ttf"],
    "sans_semibold": [_WIN / "seguisb.ttf", _WIN / "segoeuib.ttf", _MPL / "DejaVuSans-Bold.ttf"],
    "sans_italic": [_WIN / "segoeuii.ttf", _WIN / "ariali.ttf", _MPL / "DejaVuSans-Oblique.ttf"],
    "mono": [_WIN / "consola.ttf", _MPL / "DejaVuSansMono.ttf"],
    "mono_bold": [_WIN / "consolab.ttf", _MPL / "DejaVuSansMono-Bold.ttf"],
    "simbolos": [_WIN / "seguisym.ttf", _MPL / "DejaVuSans.ttf"],
}


@functools.lru_cache(maxsize=512)
def fonte(familia: str, tamanho: int) -> ImageFont.FreeTypeFont:
    for caminho in CANDIDATAS[familia]:
        try:
            if caminho.exists():
                return ImageFont.truetype(str(caminho), int(tamanho))
        except Exception:
            continue
    return ImageFont.load_default(size=int(tamanho))
