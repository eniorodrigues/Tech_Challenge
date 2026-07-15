"""
Modelagem: definição, treino e validação cruzada dos classificadores.

São usadas quatro técnicas (o desafio pede duas ou mais), escolhidas para
cobrir famílias diferentes de algoritmos e permitir comparação:

* **Regressão Logística** — modelo linear, interpretável, forte baseline.
* **Árvore de Decisão** — não-linear, interpretável por regras.
* **KNN** — baseado em distância/vizinhança, sensível à escala (daí a
  padronização ser essencial).
* **Random Forest** — ensemble de árvores, costuma dar o melhor desempenho e
  fornece importância de features.

Cada modelo é um ``Pipeline`` (pré-processador + estimador). Isso mantém a
padronização acoplada ao estimador e evita vazamento de dados na validação
cruzada.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from . import config
from .preprocessing import build_preprocessor


def build_models(numeric_features: list[str]) -> dict[str, Pipeline]:
    """Cria o dicionário {nome: pipeline} com os quatro classificadores.

    ``class_weight='balanced'`` é usado onde disponível para compensar o
    desbalanceamento de classes sem precisar reamostrar os dados.
    """
    preprocessor = build_preprocessor(numeric_features)

    estimators = {
        "Regressão Logística": LogisticRegression(
            max_iter=5000,
            class_weight="balanced",
            random_state=config.RANDOM_STATE,
        ),
        "Árvore de Decisão": DecisionTreeClassifier(
            max_depth=4,
            class_weight="balanced",
            random_state=config.RANDOM_STATE,
        ),
        "KNN": KNeighborsClassifier(n_neighbors=7),
        "Random Forest": RandomForestClassifier(
            n_estimators=300,
            class_weight="balanced",
            random_state=config.RANDOM_STATE,
        ),
    }

    # Recria o preprocessor por modelo (um ColumnTransformer não deve ser
    # compartilhado entre pipelines distintos após o fit).
    return {
        name: Pipeline(
            steps=[
                ("preprocessor", build_preprocessor(numeric_features)),
                ("classifier", estimator),
            ]
        )
        for name, estimator in estimators.items()
    }


def cross_validate_models(
    models: dict[str, Pipeline],
    x_train: pd.DataFrame,
    y_train: pd.Series,
) -> pd.DataFrame:
    """Validação cruzada estratificada no conjunto de treino.

    Retorna um DataFrame com a média e o desvio-padrão das principais métricas
    por modelo. O foco é o recall da classe maligna, mas todas são reportadas.
    """
    cv = StratifiedKFold(
        n_splits=config.CV_FOLDS,
        shuffle=True,
        random_state=config.RANDOM_STATE,
    )
    scoring = {
        "accuracy": "accuracy",
        "precision": "precision",
        "recall": "recall",
        "f1": "f1",
        "roc_auc": "roc_auc",
    }

    rows = []
    for name, model in models.items():
        results = cross_validate(
            model, x_train, y_train, cv=cv, scoring=scoring, n_jobs=-1
        )
        row = {"modelo": name}
        for metric in scoring:
            scores = results[f"test_{metric}"]
            row[f"{metric}_media"] = scores.mean()
            row[f"{metric}_desvio"] = scores.std()
        rows.append(row)

    return pd.DataFrame(rows).set_index("modelo").sort_values(
        "recall_media", ascending=False
    )


def fit_models(
    models: dict[str, Pipeline],
    x_train: pd.DataFrame,
    y_train: pd.Series,
) -> dict[str, Pipeline]:
    """Ajusta todos os modelos no conjunto de treino completo."""
    for model in models.values():
        model.fit(x_train, y_train)
    return models
