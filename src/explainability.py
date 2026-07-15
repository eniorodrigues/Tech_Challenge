"""
Explicabilidade do modelo.

Duas técnicas complementares, como pede o desafio:

* **Feature importance** — importância global das features.
    - Para modelos de árvore/ensemble: importância por redução de impureza.
    - Para a Regressão Logística: magnitude dos coeficientes (features já
      padronizadas, então os coeficientes são comparáveis entre si).

* **SHAP (SHapley Additive exPlanations)** — atribui a cada feature uma
  contribuição para cada previsão individual, com base sólida em teoria dos
  jogos. Permite explicar tanto o modelo como um todo quanto casos isolados
  (por que ESTA paciente foi classificada como maligno?). Isso é essencial em
  saúde, onde o médico precisa entender e confiar na recomendação.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline


def feature_importance(model: Pipeline, feature_names: list[str]) -> pd.DataFrame:
    """Importância global das features para um pipeline treinado.

    Detecta automaticamente se o estimador final expõe
    ``feature_importances_`` (árvores/ensembles) ou ``coef_`` (modelos
    lineares) e retorna um DataFrame ordenado.
    """
    classifier = model.named_steps["classifier"]

    if hasattr(classifier, "feature_importances_"):
        importances = classifier.feature_importances_
        tipo = "importancia_impureza"
    elif hasattr(classifier, "coef_"):
        importances = np.abs(classifier.coef_[0])
        tipo = "abs_coeficiente"
    else:
        raise ValueError(
            f"O estimador {type(classifier).__name__} não expõe importância de features."
        )

    df = pd.DataFrame({"feature": feature_names, tipo: importances})
    return df.sort_values(tipo, ascending=False).reset_index(drop=True)


def plot_feature_importance(
    model: Pipeline,
    feature_names: list[str],
    title: str,
    top_n: int = 15,
    save_path: Path | None = None,
):
    """Gráfico de barras horizontal com as ``top_n`` features mais importantes."""
    df = feature_importance(model, feature_names).head(top_n)
    value_col = df.columns[1]

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.barh(df["feature"][::-1], df[value_col][::-1], color="#2a7ab9")
    ax.set_xlabel(value_col.replace("_", " "))
    ax.set_title(f"Importância das features — {title}")
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def compute_shap_values(model: Pipeline, x_train, x_sample):
    """Calcula valores SHAP para um modelo de árvore/ensemble.

    O pré-processador do pipeline é aplicado antes de explicar o classificador.
    Usa ``TreeExplainer``, eficiente e exato para modelos baseados em árvore
    (como o Random Forest usado no projeto).

    Returns
    -------
    (shap_values_classe_positiva, x_sample_transformado)
    """
    preprocessor = model.named_steps["preprocessor"]
    classifier = model.named_steps["classifier"]

    x_sample_trans = preprocessor.transform(x_sample)

    explainer = shap.TreeExplainer(classifier)
    shap_values = explainer.shap_values(x_sample_trans)

    # Em classificação binária, shap_values pode vir como lista [classe0, classe1]
    # ou como array (n, features, classes). Normalizamos para a classe positiva.
    if isinstance(shap_values, list):
        shap_pos = shap_values[1]
    elif np.ndim(shap_values) == 3:
        shap_pos = shap_values[:, :, 1]
    else:
        shap_pos = shap_values

    return shap_pos, x_sample_trans


def plot_shap_summary(
    model: Pipeline,
    x_train,
    x_sample,
    feature_names: list[str],
    save_path: Path | None = None,
):
    """Gera o summary plot do SHAP (impacto global das features)."""
    shap_pos, x_sample_trans = compute_shap_values(model, x_train, x_sample)

    fig = plt.figure()
    shap.summary_plot(
        shap_pos,
        x_sample_trans,
        feature_names=feature_names,
        show=False,
        plot_size=(8, 6),
    )
    if save_path is not None:
        plt.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig
