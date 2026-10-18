"""Caminhos e constantes compartilhadas pelo projeto."""

from __future__ import annotations

from pathlib import Path

# fase2/src/medroute/config.py -> parents[2] == fase2/
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

DATA_DIR: Path = PROJECT_ROOT / "data"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"
FIGURES_DIR: Path = REPORTS_DIR / "figures"
MAPS_DIR: Path = REPORTS_DIR / "maps"
LLM_OUTPUT_DIR: Path = REPORTS_DIR / "llm"
CACHE_DIR: Path = PROJECT_ROOT / ".cache"

DEFAULT_SCENARIO_FILE: Path = DATA_DIR / "cenario_padrao.json"

# Semente global: toda execução padrão é reprodutível.
RANDOM_SEED: int = 42


def ensure_dirs() -> None:
    """Cria as pastas de saída (idempotente)."""
    for pasta in (DATA_DIR, FIGURES_DIR, MAPS_DIR, LLM_OUTPUT_DIR, CACHE_DIR):
        pasta.mkdir(parents=True, exist_ok=True)
