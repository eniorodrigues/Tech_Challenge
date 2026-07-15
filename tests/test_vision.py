"""
Provas de correção do pipeline de Visão Computacional (CNN).

São testes rápidos e herméticos (sem download nem treino): usam um modelo
não-treinado e dados sintéticos apenas para verificar as invariantes de
"encanamento" — com destaque para o **remapeamento do rótulo**, o ponto de
cruzamento de dados mais sensível: se o maligno não virar a classe positiva,
todas as métricas de recall ficam invertidas e sem sentido clínico.
"""

from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from src import vision


def _synthetic_loader(n: int = 20, size: int = 64) -> DataLoader:
    """DataLoader sintético com as duas classes garantidamente presentes."""
    g = torch.Generator().manual_seed(0)
    x = torch.randn(n, 1, size, size, generator=g)
    y = torch.tensor([0, 1] * (n // 2)).view(-1, 1)  # metade de cada classe
    return DataLoader(TensorDataset(x, y), batch_size=8)


# --------------------------------------------------------------------------- #
# Data-crossing: remapeamento do rótulo (maligno -> classe positiva)
# --------------------------------------------------------------------------- #
def test_remapeia_maligno_para_positivo():
    """No BreastMNIST cru 0=maligno; deve virar 1 (positivo). E 1 (não-maligno) -> 0."""
    assert vision._target_transform(np.array([0])) == 1
    assert vision._target_transform(np.array([1])) == 0
    assert vision.POSITIVE_IS_MALIGNANT == 1
    assert vision.CLASS_NAMES[1] == "maligno"


# --------------------------------------------------------------------------- #
# Arquitetura da CNN
# --------------------------------------------------------------------------- #
def test_cnn_saida_binaria():
    model = vision.BreastCNN()
    out = model(torch.randn(4, 1, 64, 64))
    assert out.shape == (4, 2)


def test_cnn_aceita_varias_resolucoes():
    """Graças ao AdaptiveAvgPool, a CNN aceita diferentes tamanhos de imagem."""
    model = vision.BreastCNN()
    for size in (28, 64, 128):
        out = model(torch.randn(2, 1, size, size))
        assert out.shape == (2, 2)


# --------------------------------------------------------------------------- #
# Avaliação e limiar
# --------------------------------------------------------------------------- #
def test_metricas_no_intervalo_valido():
    model = vision.BreastCNN()
    loader = _synthetic_loader()
    res = vision.evaluate(model, loader)
    for m in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        assert 0.0 <= res[m] <= 1.0
    assert res["confusion_matrix"].sum() == 20


def test_limiar_controla_predicoes():
    """Limiar 0 -> tudo classificado como maligno; limiar > 1 -> nada."""
    model = vision.BreastCNN()
    loader = _synthetic_loader()
    tudo_positivo = vision.evaluate(model, loader, threshold=0.0)
    nada_positivo = vision.evaluate(model, loader, threshold=1.0001)
    assert tudo_positivo["y_pred"].sum() == 20
    assert nada_positivo["y_pred"].sum() == 0


def test_select_threshold_valido():
    model = vision.BreastCNN()
    loader = _synthetic_loader()
    thr = vision.select_threshold_for_recall(model, loader, target_recall=0.9)
    assert 0.0 <= thr <= 1.0


# --------------------------------------------------------------------------- #
# Explicabilidade — Grad-CAM
# --------------------------------------------------------------------------- #
def test_gradcam_shape_e_intervalo():
    """O heatmap deve ter o tamanho da imagem e estar normalizado em [0, 1]."""
    model = vision.BreastCNN()
    cam = vision.GradCAM(model)
    heat = cam.generate(torch.randn(1, 1, 64, 64), target_class=vision.POSITIVE_IS_MALIGNANT)
    assert heat.shape == (64, 64)
    assert heat.min() >= 0.0 and heat.max() <= 1.0 + 1e-6
