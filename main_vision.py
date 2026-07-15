"""
EXTRA — Pipeline de Visão Computacional (CNN em ultrassom de mama).

Executa de ponta a ponta:
    1. Download e preparação do BreastMNIST (ultrassom, via medmnist)
    2. Construção e treino da CNN (com perda ponderada p/ desbalanceamento)
    3. Avaliação no teste (accuracy, precision, recall, F1, ROC-AUC)
    4. Explicabilidade com Grad-CAM
    5. Persistência do modelo e das figuras

Uso:
    python main_vision.py

Treina em CPU em poucos minutos (dataset pequeno). Todas as figuras vão para
reports/figures/ e o modelo para models/.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

from src import config, vision


def _section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main(epochs: int = 40, image_size: int = 64) -> None:
    config.ensure_dirs()
    vision.set_seed()

    # ----------------------------------------------------------------- 1. Dados
    _section("1. DOWNLOAD E PREPARAÇÃO DO BREASTMNIST (ultrassom de mama)")
    data = vision.load_breastmnist(image_size=image_size, batch_size=32)
    print(f"Resolução das imagens: {image_size}x{image_size} (1 canal, tons de cinza)")
    print(f"Batches -> treino: {len(data.train_loader)} | val: {len(data.val_loader)} | teste: {len(data.test_loader)}")
    import numpy as np

    counts = np.bincount(data.train_labels, minlength=2)
    print(f"Treino por classe -> não-maligno: {counts[0]} | maligno: {counts[1]}")
    print(f"Pesos de classe na perda: {data.class_weights.tolist()}")

    # ------------------------------------------------------------------- 2. CNN
    _section("2. TREINO DA CNN")
    model = vision.BreastCNN()
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Parâmetros treináveis: {n_params:,}")
    history = vision.train_model(model, data, epochs=epochs)

    vision.plot_training_history(
        history, save_path=config.FIGURES_DIR / "08_cnn_treino.png"
    )

    # ------------------------------------------------------------- 3. Avaliação
    _section("3. AVALIAÇÃO NO CONJUNTO DE TESTE")

    print("Ponto de operação PADRÃO (limiar 0.50):")
    default_res = vision.evaluate(model, data.test_loader, threshold=0.5)
    for metric in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        print(f"  {metric:10s}: {default_res[metric]:.4f}")

    # Calibra o limiar na VALIDAÇÃO (nunca no teste) para priorizar recall.
    clinical_threshold = vision.select_threshold_for_recall(
        model, data.val_loader, target_recall=0.90
    )
    print(
        f"\nPonto de operação CLÍNICO (limiar {clinical_threshold:.2f}, "
        "calibrado na validação para recall alto):"
    )
    results = vision.evaluate(model, data.test_loader, threshold=clinical_threshold)
    for metric in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        print(f"  {metric:10s}: {results[metric]:.4f}")

    print("\nMatriz de confusão no ponto clínico [linhas=real, colunas=previsto] (0=não-maligno, 1=maligno):")
    print(results["confusion_matrix"])
    print(
        f"  -> {results['falsos_negativos']} falso(s) negativo(s) no ponto clínico "
        f"(vs. {default_res['falsos_negativos']} no limiar padrão): "
        "priorizar recall reduz os cânceres que passam despercebidos."
    )

    vision.plot_confusion_matrix(
        results["confusion_matrix"], save_path=config.FIGURES_DIR / "09_cnn_matriz_confusao.png"
    )
    vision.plot_sample_predictions(
        model, data.test_loader, save_path=config.FIGURES_DIR / "10_cnn_amostras.png"
    )

    # ------------------------------------------------------- 4. Explicabilidade
    _section("4. EXPLICABILIDADE — GRAD-CAM")
    vision.plot_gradcam_grid(
        model, data.test_loader, save_path=config.FIGURES_DIR / "11_cnn_gradcam.png"
    )
    print("Grad-CAM salvo: heatmaps destacando as regiões que a CNN usou.")

    # ----------------------------------------------------------- 5. Persistência
    _section("5. PERSISTÊNCIA")
    model_path = vision.save_model(model)
    print(f"Modelo salvo em: {model_path.relative_to(config.PROJECT_ROOT)}")
    print("Figuras salvas em: reports/figures/ (08 a 11)")

    plt.close("all")
    _section("PIPELINE DE VISÃO CONCLUÍDO")


if __name__ == "__main__":
    main()
