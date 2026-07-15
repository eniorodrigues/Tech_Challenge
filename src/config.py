"""
Configuração central do projeto.

Concentra caminhos, semente de aleatoriedade e convenções de rotulagem
para que todos os módulos (e o notebook) usem exatamente os mesmos valores.
Isso é o que garante que os resultados sejam reprodutíveis: mudar a semente
em um único lugar re-executa todo o pipeline de forma consistente.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Reprodutibilidade
# ---------------------------------------------------------------------------
# Semente única usada em split de treino/teste, validação cruzada e modelos.
RANDOM_STATE: int = 42

# Proporção do conjunto reservada para teste (holdout).
TEST_SIZE: float = 0.20

# Número de folds na validação cruzada estratificada.
CV_FOLDS: int = 5

# ---------------------------------------------------------------------------
# Convenção de rotulagem (decisão clínica importante)
# ---------------------------------------------------------------------------
# O scikit-learn carrega o Breast Cancer Wisconsin com:
#   target 0 -> 'malignant'  (maligno)
#   target 1 -> 'benign'     (benigno)
#
# Para o problema clínico, a classe de interesse ("positiva") é o tumor
# MALIGNO: é o caso em que um erro custa caro. Por isso REMAPEAMOS os rótulos
# para que 1 = maligno e 0 = benigno. Assim, "recall" passa a significar
# diretamente "proporção de tumores malignos que o modelo conseguiu detectar",
# que é a métrica que realmente importa aqui.
POSITIVE_LABEL: int = 1          # maligno
NEGATIVE_LABEL: int = 0          # benigno
TARGET_COLUMN: str = "diagnosis"
CLASS_NAMES: dict[int, str] = {0: "benigno", 1: "maligno"}

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
DATA_DIR: Path = PROJECT_ROOT / "data"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"
FIGURES_DIR: Path = REPORTS_DIR / "figures"
MODELS_DIR: Path = PROJECT_ROOT / "models"

RAW_DATA_CSV: Path = DATA_DIR / "breast_cancer_wisconsin.csv"


def ensure_dirs() -> None:
    """Cria as pastas de saída se ainda não existirem."""
    for directory in (DATA_DIR, REPORTS_DIR, FIGURES_DIR, MODELS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
