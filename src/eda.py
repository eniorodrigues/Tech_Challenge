"""
Análise exploratória de dados (EDA).

Funções de visualização reutilizáveis pelo ``main.py`` e pelo notebook:
distribuição das classes, estatísticas descritivas, distribuições por classe
e matriz de correlação. Todas retornam a figura para permitir exibição no
notebook ou salvamento em disco.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from . import config

sns.set_theme(style="whitegrid")


def class_balance(df: pd.DataFrame) -> pd.Series:
    """Contagem de amostras por classe (com rótulos legíveis)."""
    counts = df[config.TARGET_COLUMN].map(config.CLASS_NAMES).value_counts()
    return counts


def plot_class_balance(df: pd.DataFrame, save_path: Path | None = None):
    """Gráfico de barras do balanceamento das classes."""
    counts = class_balance(df)
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.barplot(x=counts.index, y=counts.values, ax=ax, palette=["#4c9f70", "#c0392b"])
    ax.set_title("Distribuição das classes (diagnóstico)")
    ax.set_ylabel("Nº de pacientes")
    ax.set_xlabel("")
    for i, v in enumerate(counts.values):
        ax.text(i, v + 3, str(v), ha="center", fontweight="bold")
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def plot_feature_distributions(
    df: pd.DataFrame,
    features: list[str],
    save_path: Path | None = None,
):
    """Histogramas comparando benigno vs. maligno para features escolhidas."""
    n = len(features)
    ncols = 3
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
    axes = axes.flatten()

    df_plot = df.copy()
    df_plot["classe"] = df_plot[config.TARGET_COLUMN].map(config.CLASS_NAMES)

    for ax, feature in zip(axes, features):
        sns.histplot(
            data=df_plot,
            x=feature,
            hue="classe",
            kde=True,
            ax=ax,
            palette={"benigno": "#4c9f70", "maligno": "#c0392b"},
            alpha=0.55,
        )
        ax.set_title(feature)
        ax.set_xlabel("")

    for ax in axes[n:]:
        ax.set_visible(False)

    fig.suptitle("Distribuição de features por classe", fontsize=14, y=1.01)
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Matriz de correlação de Pearson entre todas as variáveis numéricas."""
    return df.corr(numeric_only=True)


def plot_correlation_heatmap(df: pd.DataFrame, save_path: Path | None = None):
    """Heatmap da matriz de correlação (inclui o alvo)."""
    corr = correlation_matrix(df)
    fig, ax = plt.subplots(figsize=(14, 12))
    sns.heatmap(
        corr,
        cmap="coolwarm",
        center=0,
        square=True,
        linewidths=0.3,
        cbar_kws={"shrink": 0.6},
        ax=ax,
    )
    ax.set_title("Matriz de correlação (Pearson)", fontsize=14)
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def top_target_correlations(df: pd.DataFrame, n: int = 10) -> pd.Series:
    """Features mais correlacionadas com o diagnóstico (em valor absoluto)."""
    corr = correlation_matrix(df)[config.TARGET_COLUMN].drop(config.TARGET_COLUMN)
    return corr.reindex(corr.abs().sort_values(ascending=False).index).head(n)


def highly_correlated_pairs(df: pd.DataFrame, threshold: float = 0.9) -> pd.DataFrame:
    """Pares de features com |correlação| acima do limiar (multicolinearidade)."""
    corr = correlation_matrix(df).drop(
        index=config.TARGET_COLUMN, columns=config.TARGET_COLUMN
    )
    pairs = []
    cols = corr.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if abs(r) >= threshold:
                pairs.append((cols[i], cols[j], round(r, 3)))
    return pd.DataFrame(pairs, columns=["feature_a", "feature_b", "correlacao"]).sort_values(
        "correlacao", key=lambda s: s.abs(), ascending=False
    )
