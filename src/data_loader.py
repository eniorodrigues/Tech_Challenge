"""
Carregamento da base de dados.

Fonte: Breast Cancer Wisconsin (Diagnostic), disponível diretamente no
scikit-learn (`sklearn.datasets.load_breast_cancer`). É a base sugerida no
desafio como tarefa principal e não depende de download externo/Kaggle, o
que torna o projeto reprodutível em qualquer máquina.

Referência original:
    Wolberg, W. H., Street, W. N., & Mangasarian, O. L. (1995).
    Breast Cancer Wisconsin (Diagnostic) Data Set. UCI ML Repository.
"""

from __future__ import annotations

import pandas as pd
from sklearn.datasets import load_breast_cancer

from . import config


def load_dataframe(save_csv: bool = True) -> pd.DataFrame:
    """Carrega o dataset como um DataFrame já com o alvo remapeado.

    O alvo é gravado na coluna ``config.TARGET_COLUMN`` (``diagnosis``) usando
    a convenção clínica do projeto: 1 = maligno, 0 = benigno (ver
    ``config.py`` para a justificativa).

    Parameters
    ----------
    save_csv:
        Se ``True``, persiste uma cópia em ``data/`` para inspeção/uso externo.

    Returns
    -------
    pandas.DataFrame
        Colunas de features + a coluna de diagnóstico.
    """
    bunch = load_breast_cancer(as_frame=True)
    df = bunch.frame.copy()

    # No sklearn, 'target' == 0 é maligno e == 1 é benigno. Invertendo para a
    # convenção do projeto (1 = maligno = classe positiva de interesse).
    original_target = df.pop("target")
    df[config.TARGET_COLUMN] = (original_target == 0).astype(int)

    if save_csv:
        config.ensure_dirs()
        df.to_csv(config.RAW_DATA_CSV, index=False)

    return df


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Lista as colunas de features (tudo menos o alvo)."""
    return [c for c in df.columns if c != config.TARGET_COLUMN]


def split_features_target(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Separa o DataFrame em X (features) e y (alvo)."""
    y = df[config.TARGET_COLUMN]
    x = df[feature_columns(df)]
    return x, y


if __name__ == "__main__":
    frame = load_dataframe()
    print(f"Shape: {frame.shape}")
    print(f"Colunas de alvo balanceamento:\n{frame[config.TARGET_COLUMN].value_counts()}")
    print(f"CSV salvo em: {config.RAW_DATA_CSV}")
