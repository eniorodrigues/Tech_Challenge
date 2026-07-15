"""
Pré-processamento e preparação dos dados.

Pontos-chave de projeto:

* **Sem vazamento de dados (data leakage):** a padronização (StandardScaler)
  é sempre encapsulada dentro de um ``Pipeline`` do scikit-learn. Assim, a
  média e o desvio usados na normalização são aprendidos SOMENTE no conjunto
  de treino a cada fold/ajuste, nunca no teste. Isso é o que garante uma
  estimativa honesta de desempenho.

* **Split estratificado:** como as classes são desbalanceadas (~37% maligno),
  o split de treino/teste preserva a proporção das classes.

* **Limpeza defensiva:** o Breast Cancer Wisconsin não tem valores ausentes,
  mas o código trata NaN mesmo assim para servir de pipeline reutilizável
  em bases mais "sujas" (ex.: PCOS).
"""

from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config


def missing_report(df: pd.DataFrame) -> pd.DataFrame:
    """Relatório de valores ausentes por coluna (contagem e percentual)."""
    total = df.isna().sum()
    pct = (total / len(df) * 100).round(2)
    report = pd.DataFrame({"ausentes": total, "percentual": pct})
    return report[report["ausentes"] > 0].sort_values("ausentes", ascending=False)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Limpeza básica: remove duplicatas exatas e colunas totalmente vazias.

    A imputação de valores ausentes NÃO é feita aqui — ela vive dentro do
    pipeline de modelagem (``build_preprocessor``) para evitar vazamento.
    """
    cleaned = df.drop_duplicates().copy()
    cleaned = cleaned.dropna(axis=1, how="all")
    return cleaned


def build_preprocessor(numeric_features: list[str]) -> ColumnTransformer:
    """Constrói o transformador de features numéricas.

    Imputa valores ausentes pela mediana (robusta a outliers) e padroniza
    para média 0 e desvio 1. Retorna um ``ColumnTransformer`` para poder ser
    estendido com features categóricas no futuro (ex.: outros datasets).
    """
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        transformers=[("num", numeric_pipeline, numeric_features)],
        remainder="drop",
    )


def split_data(
    x: pd.DataFrame,
    y: pd.Series,
    test_size: float = config.TEST_SIZE,
    random_state: int = config.RANDOM_STATE,
):
    """Split estratificado treino/teste.

    Returns
    -------
    (X_train, X_test, y_train, y_test)
    """
    return train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )
