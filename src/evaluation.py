"""
Avaliação dos modelos no conjunto de teste.

Métricas reportadas: accuracy, precision, recall, F1 e ROC-AUC.

Por que o RECALL da classe maligna é a métrica prioritária:
    Um falso negativo (dizer que um tumor maligno é benigno) pode atrasar o
    tratamento e custar a vida da paciente. Um falso positivo (classificar um
    tumor benigno como maligno) gera exames adicionais e ansiedade, mas é
    clinicamente muito menos grave. Logo, preferimos um modelo com recall alto
    para 'maligno', usando F1/precision como contrapeso para não gerar alarmes
    em excesso. Accuracy sozinha é enganosa em base desbalanceada.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from . import config


def _positive_scores(model, x_test) -> np.ndarray:
    """Retorna a probabilidade/escore da classe positiva (maligno)."""
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x_test)[:, 1]
    # Fallback para modelos sem predict_proba.
    return model.decision_function(x_test)


def evaluate_model(model, x_test, y_test) -> dict[str, float]:
    """Calcula as métricas de um modelo no conjunto de teste."""
    y_pred = model.predict(x_test)
    y_score = _positive_scores(model, x_test)

    return {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_score),
    }


def evaluate_all(models: dict, x_test, y_test) -> pd.DataFrame:
    """Avalia todos os modelos e retorna um DataFrame ordenado por recall."""
    rows = []
    for name, model in models.items():
        metrics = evaluate_model(model, x_test, y_test)
        metrics["modelo"] = name
        rows.append(metrics)
    df = pd.DataFrame(rows).set_index("modelo")
    return df.sort_values("recall", ascending=False)


def plot_confusion_matrix(
    model, x_test, y_test, title: str, save_path: Path | None = None
):
    """Plota (e opcionalmente salva) a matriz de confusão de um modelo."""
    y_pred = model.predict(x_test)
    cm = confusion_matrix(y_test, y_pred, labels=[config.NEGATIVE_LABEL, config.POSITIVE_LABEL])
    display_labels = [config.CLASS_NAMES[config.NEGATIVE_LABEL], config.CLASS_NAMES[config.POSITIVE_LABEL]]

    fig, ax = plt.subplots(figsize=(5, 4))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=display_labels)
    disp.plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title(f"Matriz de Confusão — {title}")
    ax.set_xlabel("Previsto")
    ax.set_ylabel("Real")
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def plot_roc_curves(models: dict, x_test, y_test, save_path: Path | None = None):
    """Plota a curva ROC de todos os modelos em um único gráfico."""
    fig, ax = plt.subplots(figsize=(6, 5))
    for name, model in models.items():
        y_score = _positive_scores(model, x_test)
        fpr, tpr, _ = roc_curve(y_test, y_score)
        auc = roc_auc_score(y_test, y_score)
        ax.plot(fpr, tpr, label=f"{name} (AUC = {auc:.3f})")

    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Aleatório")
    ax.set_xlabel("Taxa de Falso Positivo")
    ax.set_ylabel("Taxa de Verdadeiro Positivo (Recall)")
    ax.set_title("Curvas ROC — comparação de modelos")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()

    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def confusion_breakdown(model, x_test, y_test) -> dict[str, int]:
    """Retorna TN, FP, FN, TP explicitamente (útil para discussão clínica)."""
    y_pred = model.predict(x_test)
    cm = confusion_matrix(y_test, y_pred, labels=[config.NEGATIVE_LABEL, config.POSITIVE_LABEL])
    tn, fp, fn, tp = cm.ravel()
    return {
        "verdadeiro_negativo": int(tn),
        "falso_positivo": int(fp),
        "falso_negativo": int(fn),  # maligno classificado como benigno (o pior caso)
        "verdadeiro_positivo": int(tp),
    }
