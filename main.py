"""
Pipeline completo do Tech Challenge - Fase 1.

Executa de ponta a ponta:
    1. Carregamento dos dados
    2. Análise exploratória (gera figuras em reports/figures)
    3. Pré-processamento e split treino/teste
    4. Análise de correlação
    5. Modelagem (4 técnicas) + validação cruzada
    6. Avaliação no teste (accuracy, precision, recall, F1, ROC-AUC)
    7. Explicabilidade (feature importance + SHAP)
    8. Persistência do melhor modelo

Uso:
    python main.py

Todas as saídas (figuras, métricas, modelo) são gravadas em disco e um
resumo é impresso no terminal.
"""

from __future__ import annotations

import unicodedata
import warnings

import matplotlib

matplotlib.use("Agg")  # backend headless: gera arquivos sem abrir janelas
import matplotlib.pyplot as plt

import joblib
import pandas as pd

from src import config, data_loader, eda, evaluation, explainability, modeling
from src.preprocessing import (
    clean_data,
    missing_report,
    split_data,
)

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 30)


def _slug(text: str) -> str:
    """Converte um nome de modelo em um slug ASCII seguro para arquivos."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower().replace(" ", "_")


def _section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main() -> None:
    config.ensure_dirs()

    # ------------------------------------------------------------------ 1. Dados
    _section("1. CARREGAMENTO DOS DADOS")
    df = data_loader.load_dataframe(save_csv=True)
    df = clean_data(df)
    print(f"Dimensões: {df.shape[0]} pacientes x {df.shape[1] - 1} features")
    print(f"CSV salvo em: {config.RAW_DATA_CSV.relative_to(config.PROJECT_ROOT)}")

    # -------------------------------------------------------------------- 2. EDA
    _section("2. ANÁLISE EXPLORATÓRIA")
    print("Balanceamento das classes:")
    print(eda.class_balance(df).to_string())

    missing = missing_report(df)
    print(f"\nValores ausentes: {'nenhum' if missing.empty else ''}")
    if not missing.empty:
        print(missing.to_string())

    print("\nEstatísticas descritivas (5 primeiras features):")
    features = data_loader.feature_columns(df)
    print(df[features[:5]].describe().round(3).to_string())

    top_corr = eda.top_target_correlations(df, n=10)
    print("\nFeatures mais correlacionadas com o diagnóstico:")
    print(top_corr.round(3).to_string())

    # Figuras de EDA
    eda.plot_class_balance(df, save_path=config.FIGURES_DIR / "01_balanceamento_classes.png")
    eda.plot_feature_distributions(
        df,
        features=[f for f in top_corr.index[:6]],
        save_path=config.FIGURES_DIR / "02_distribuicoes_por_classe.png",
    )
    eda.plot_correlation_heatmap(df, save_path=config.FIGURES_DIR / "03_matriz_correlacao.png")

    corr_pairs = eda.highly_correlated_pairs(df, threshold=0.9)
    print(f"\nPares de features com |correlação| >= 0.9 (multicolinearidade): {len(corr_pairs)}")
    print(corr_pairs.head(10).to_string(index=False))

    # -------------------------------------------------- 3. Split treino/teste
    _section("3. PRÉ-PROCESSAMENTO E SPLIT TREINO/TESTE")
    x, y = data_loader.split_features_target(df)
    x_train, x_test, y_train, y_test = split_data(x, y)
    print(f"Treino: {x_train.shape[0]} amostras | Teste: {x_test.shape[0]} amostras")
    print("Proporção de maligno mantida (estratificação):")
    print(f"  treino: {y_train.mean():.3f} | teste: {y_test.mean():.3f}")
    print("A padronização vive DENTRO do pipeline -> sem vazamento de dados.")

    # ----------------------------------------------------------- 4. Modelagem
    _section("4. MODELAGEM E VALIDAÇÃO CRUZADA (treino)")
    numeric_features = data_loader.feature_columns(df)
    models = modeling.build_models(numeric_features)
    cv_results = modeling.cross_validate_models(models, x_train, y_train)
    print("Média (desvio) das métricas na validação cruzada estratificada:")
    print(cv_results.round(4).to_string())

    models = modeling.fit_models(models, x_train, y_train)

    # ----------------------------------------------------------- 5. Avaliação
    _section("5. AVALIAÇÃO NO CONJUNTO DE TESTE")
    test_results = evaluation.evaluate_all(models, x_test, y_test)
    print(test_results.round(4).to_string())

    best_name = test_results.index[0]
    best_model = models[best_name]
    print(f"\nMelhor modelo por recall (maligno): {best_name}")

    breakdown = evaluation.confusion_breakdown(best_model, x_test, y_test)
    print("Matriz de confusão detalhada do melhor modelo:")
    for k, v in breakdown.items():
        print(f"  {k}: {v}")
    print(
        f"  -> {breakdown['falso_negativo']} falso(s) negativo(s): "
        "tumores malignos que passariam despercebidos (o erro mais grave)."
    )

    # Figuras de avaliação
    for name, model in models.items():
        evaluation.plot_confusion_matrix(
            model, x_test, y_test, title=name,
            save_path=config.FIGURES_DIR / f"04_matriz_confusao_{_slug(name)}.png",
        )
    evaluation.plot_roc_curves(
        models, x_test, y_test, save_path=config.FIGURES_DIR / "05_curvas_roc.png"
    )

    # ------------------------------------------------------- 6. Explicabilidade
    _section("6. EXPLICABILIDADE")
    fi = explainability.feature_importance(best_model, numeric_features)
    print(f"Top 10 features mais importantes ({best_name}):")
    print(fi.head(10).to_string(index=False))

    explainability.plot_feature_importance(
        best_model, numeric_features, title=best_name,
        save_path=config.FIGURES_DIR / "06_feature_importance.png",
    )

    # SHAP só funciona direto para modelos de árvore; usa o Random Forest.
    if "Random Forest" in models:
        try:
            explainability.plot_shap_summary(
                models["Random Forest"],
                x_train,
                x_test,
                numeric_features,
                save_path=config.FIGURES_DIR / "07_shap_summary.png",
            )
            print("SHAP summary plot salvo (Random Forest).")
        except Exception as exc:  # pragma: no cover - robustez
            print(f"Não foi possível gerar o SHAP: {exc}")

    # ------------------------------------------------------ 7. Persistir modelo
    _section("7. PERSISTÊNCIA")
    model_path = config.MODELS_DIR / "melhor_modelo.joblib"
    joblib.dump(best_model, model_path)
    test_results.to_csv(config.REPORTS_DIR / "metricas_teste.csv")
    cv_results.to_csv(config.REPORTS_DIR / "metricas_validacao_cruzada.csv")
    print(f"Modelo salvo em: {model_path.relative_to(config.PROJECT_ROOT)}")
    print(f"Métricas salvas em: reports/metricas_teste.csv")
    print(f"Figuras salvas em: reports/figures/")

    plt.close("all")
    _section("PIPELINE CONCLUÍDO")


if __name__ == "__main__":
    main()
