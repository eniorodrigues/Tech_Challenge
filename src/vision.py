"""
EXTRA — Visão Computacional: diagnóstico por imagem com CNN.

Classifica imagens de **ultrassom de mama** como malignas vs. não-malignas
usando uma Rede Neural Convolucional (CNN) em PyTorch.

Base de dados: **BreastMNIST** (pacote ``medmnist``), derivada do dataset
BUSI (Breast Ultrasound Images) — 780 imagens de ultrassom em tons de cinza.
É baixada automaticamente do Zenodo (sem necessidade de Kaggle), o que mantém
o projeto reprodutível.

Convenção clínica (igual à do modelo tabular): a classe positiva é o
**maligno**. No BreastMNIST o rótulo cru é ``0=maligno`` e ``1=normal/benigno``,
então REMAPEAMOS para ``1=maligno`` e ``0=não-maligno``. Assim, "recall"
significa de novo "proporção de casos malignos detectados" — a métrica que
mais importa, pois um falso negativo (deixar passar um câncer) é o pior erro.

Explicabilidade: usamos **Grad-CAM**, que destaca as regiões da imagem que
mais pesaram na decisão da CNN — o análogo visual do SHAP, essencial para o
médico entender e confiar na recomendação.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision import transforms

from . import config

# BreastMNIST cru: 0 = maligno, 1 = normal/benigno. Positivo clínico = maligno.
POSITIVE_IS_MALIGNANT = 1
CLASS_NAMES = {0: "nao-maligno", 1: "maligno"}


def set_seed(seed: int = config.RANDOM_STATE) -> None:
    """Fixa as sementes para tornar o treino reprodutível (CPU)."""
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


# --------------------------------------------------------------------------- #
# 1. Dados
# --------------------------------------------------------------------------- #
def _target_transform(y: np.ndarray) -> int:
    """Remapeia o rótulo cru (0=maligno) para a convenção 1=maligno."""
    return int(1 - int(y[0]))


def build_transforms(image_size: int, train: bool):
    """Transforms de imagem. No treino há aumentação leve (flip/rotação)."""
    base = [
        transforms.ToTensor(),                    # [0,1], shape (1, H, W)
        transforms.Normalize(mean=[0.5], std=[0.5]),  # -> [-1, 1]
    ]
    if train:
        aug = [
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=10),
        ]
        return transforms.Compose(aug + base)
    return transforms.Compose(base)


@dataclass
class DataBundle:
    train_loader: DataLoader
    val_loader: DataLoader
    test_loader: DataLoader
    class_weights: torch.Tensor
    image_size: int
    train_labels: np.ndarray = field(repr=False)


def load_breastmnist(
    image_size: int = 64,
    batch_size: int = 32,
    data_root: Path | None = None,
    weight_power: float = 0.5,
) -> DataBundle:
    """Baixa e prepara o BreastMNIST em DataLoaders do PyTorch.

    Os pesos de classe são calculados a partir do desbalanceamento do treino e
    usados na função de perda para não penalizar a classe maligna (minoritária).
    ``weight_power`` suaviza esses pesos: 1.0 = balanceamento total (agressivo,
    tende a superprever a minoria), 0.5 = raiz quadrada (mais suave, melhor
    equilíbrio entre recall e precisão). Os pesos são normalizados para média 1.
    """
    from medmnist import BreastMNIST

    if data_root is None:
        data_root = config.DATA_DIR / "breastmnist"
    data_root.mkdir(parents=True, exist_ok=True)

    common = dict(
        download=True,
        size=image_size,
        as_rgb=False,
        root=str(data_root),
        target_transform=_target_transform,
    )
    train_ds = BreastMNIST(split="train", transform=build_transforms(image_size, True), **common)
    val_ds = BreastMNIST(split="val", transform=build_transforms(image_size, False), **common)
    test_ds = BreastMNIST(split="test", transform=build_transforms(image_size, False), **common)

    generator = torch.Generator().manual_seed(config.RANDOM_STATE)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, generator=generator)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    # Rótulos de treino já remapeados (1 = maligno) para pesos de classe.
    train_labels = np.array([_target_transform(y) for y in train_ds.labels])
    counts = np.bincount(train_labels, minlength=2).astype(float)
    balanced = counts.sum() / (2.0 * np.maximum(counts, 1.0))
    weights = balanced ** weight_power        # suaviza o peso da minoria
    weights = weights / weights.mean()        # normaliza para média 1
    class_weights = torch.tensor(weights, dtype=torch.float32)

    return DataBundle(
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        class_weights=class_weights,
        image_size=image_size,
        train_labels=train_labels,
    )


# --------------------------------------------------------------------------- #
# 2. Arquitetura da CNN
# --------------------------------------------------------------------------- #
class BreastCNN(nn.Module):
    """CNN compacta para ultrassom em tons de cinza.

    Três blocos convolucionais (Conv -> BatchNorm -> ReLU -> MaxPool) que
    extraem padrões locais (bordas, texturas, formas dos nódulos), seguidos de
    um classificador denso. Pequena o bastante para treinar em CPU em minutos,
    mas com capacidade suficiente para este problema.
    """

    def __init__(self, num_classes: int = 2):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )
        # Camada convolucional final = alvo do Grad-CAM.
        self.last_conv_channels = 64
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        return self.classifier(x)


# --------------------------------------------------------------------------- #
# 3. Treino
# --------------------------------------------------------------------------- #
@dataclass
class TrainingHistory:
    train_loss: list[float] = field(default_factory=list)
    val_loss: list[float] = field(default_factory=list)
    val_recall: list[float] = field(default_factory=list)
    val_f1: list[float] = field(default_factory=list)


def _epoch_pass(model, loader, criterion, optimizer=None) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    """Uma passada por um DataLoader. Se ``optimizer`` for dado, treina."""
    is_train = optimizer is not None
    model.train(is_train)

    total_loss, n = 0.0, 0
    all_true, all_pred, all_prob = [], [], []

    context = torch.enable_grad() if is_train else torch.no_grad()
    with context:
        for images, targets in loader:
            targets = targets.long().view(-1)
            if is_train:
                optimizer.zero_grad()
            logits = model(images)
            loss = criterion(logits, targets)
            if is_train:
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * images.size(0)
            n += images.size(0)
            probs = F.softmax(logits, dim=1)[:, POSITIVE_IS_MALIGNANT]
            all_true.append(targets.numpy())
            all_pred.append(logits.argmax(1).numpy())
            all_prob.append(probs.detach().numpy())

    return (
        total_loss / n,
        np.concatenate(all_true),
        np.concatenate(all_pred),
        np.concatenate(all_prob),
    )


def train_model(
    model: nn.Module,
    data: DataBundle,
    epochs: int = 30,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    verbose: bool = True,
) -> TrainingHistory:
    """Treina a CNN com perda ponderada (compensa o desbalanceamento).

    Guarda o melhor estado do modelo segundo o F1 de validação (early-stopping
    implícito por seleção do melhor checkpoint).
    """
    from sklearn.metrics import f1_score, recall_score

    criterion = nn.CrossEntropyLoss(weight=data.class_weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    history = TrainingHistory()
    best_f1, best_state = -1.0, None

    for epoch in range(1, epochs + 1):
        train_loss, *_ = _epoch_pass(model, data.train_loader, criterion, optimizer)
        val_loss, y_true, y_pred, _ = _epoch_pass(model, data.val_loader, criterion)

        recall = recall_score(y_true, y_pred, pos_label=POSITIVE_IS_MALIGNANT, zero_division=0)
        f1 = f1_score(y_true, y_pred, pos_label=POSITIVE_IS_MALIGNANT, zero_division=0)

        history.train_loss.append(train_loss)
        history.val_loss.append(val_loss)
        history.val_recall.append(recall)
        history.val_f1.append(f1)

        if f1 > best_f1:
            best_f1 = f1
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

        if verbose:
            print(
                f"Época {epoch:02d}/{epochs} | perda treino {train_loss:.4f} | "
                f"perda val {val_loss:.4f} | recall val {recall:.3f} | F1 val {f1:.3f}"
            )

    if best_state is not None:
        model.load_state_dict(best_state)
        if verbose:
            print(f"\nMelhor F1 de validação: {best_f1:.3f} (checkpoint restaurado).")
    return history


# --------------------------------------------------------------------------- #
# 4. Avaliação
# --------------------------------------------------------------------------- #
def evaluate(model: nn.Module, loader: DataLoader, threshold: float = 0.5) -> dict:
    """Avalia a CNN em um DataLoader e retorna métricas + vetores de predição.

    ``threshold`` é o limiar sobre a probabilidade de 'maligno': a amostra é
    classificada como maligna se ``prob >= threshold``. O padrão é 0.5, mas em
    triagem clínica costuma-se baixá-lo para aumentar o recall (ver
    ``select_threshold_for_recall``).
    """
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    criterion = nn.CrossEntropyLoss()
    _, y_true, _, y_prob = _epoch_pass(model, loader, criterion)
    y_pred = (y_prob >= threshold).astype(int)

    cm = confusion_matrix(y_true, y_pred, labels=[0, POSITIVE_IS_MALIGNANT])
    tn, fp, fn, tp = cm.ravel()

    return {
        "threshold": threshold,
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, pos_label=POSITIVE_IS_MALIGNANT, zero_division=0),
        "recall": recall_score(y_true, y_pred, pos_label=POSITIVE_IS_MALIGNANT, zero_division=0),
        "f1": f1_score(y_true, y_pred, pos_label=POSITIVE_IS_MALIGNANT, zero_division=0),
        "roc_auc": roc_auc_score(y_true, y_prob),
        "confusion_matrix": cm,
        "falsos_negativos": int(fn),
        "y_true": y_true,
        "y_pred": y_pred,
        "y_prob": y_prob,
    }


def select_threshold_for_recall(
    model: nn.Module, loader: DataLoader, target_recall: float = 0.90
) -> float:
    """Escolhe, no conjunto dado (idealmente validação), o maior limiar que
    atinge ``target_recall`` para 'maligno' — maximizando a precisão sob essa
    restrição. É a forma correta de fixar o ponto de operação clínico sem
    espiar o conjunto de teste.
    """
    from sklearn.metrics import precision_score, recall_score

    criterion = nn.CrossEntropyLoss()
    _, y_true, _, y_prob = _epoch_pass(model, loader, criterion)

    best_threshold, best_precision = 0.5, -1.0
    for thr in np.unique(np.concatenate([y_prob, [0.5]])):
        pred = (y_prob >= thr).astype(int)
        rec = recall_score(y_true, pred, pos_label=POSITIVE_IS_MALIGNANT, zero_division=0)
        if rec >= target_recall:
            prec = precision_score(y_true, pred, pos_label=POSITIVE_IS_MALIGNANT, zero_division=0)
            if prec >= best_precision:
                best_precision, best_threshold = prec, float(thr)
    return best_threshold


# --------------------------------------------------------------------------- #
# 5. Explicabilidade — Grad-CAM
# --------------------------------------------------------------------------- #
class GradCAM:
    """Grad-CAM sobre a última camada convolucional da CNN.

    Registra hooks para capturar as ativações e os gradientes do mapa de
    features alvo, e produz um heatmap indicando as regiões que mais
    contribuíram para a classe escolhida.
    """

    def __init__(self, model: BreastCNN):
        self.model = model
        self.activations = None
        self.gradients = None
        # Última Conv2d dentro de model.features.
        target_layer = [m for m in model.features if isinstance(m, nn.Conv2d)][-1]
        target_layer.register_forward_hook(self._save_activation)
        target_layer.register_full_backward_hook(self._save_gradient)

    def _save_activation(self, module, inp, out):
        self.activations = out.detach()

    def _save_gradient(self, module, grad_in, grad_out):
        self.gradients = grad_out[0].detach()

    def generate(self, image: torch.Tensor, target_class: int = POSITIVE_IS_MALIGNANT) -> np.ndarray:
        """Gera o heatmap Grad-CAM para uma única imagem (shape (1,1,H,W))."""
        self.model.eval()
        self.model.zero_grad()
        logits = self.model(image)
        score = logits[0, target_class]
        score.backward()

        # Peso de cada canal = média espacial do gradiente (importância global).
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = F.relu((weights * self.activations).sum(dim=1, keepdim=True))
        cam = F.interpolate(cam, size=image.shape[2:], mode="bilinear", align_corners=False)
        cam = cam.squeeze().numpy()
        # Normaliza para [0, 1].
        cam = cam - cam.min()
        if cam.max() > 0:
            cam = cam / cam.max()
        return cam


def save_model(model: nn.Module, path: Path | None = None) -> Path:
    """Serializa os pesos da CNN."""
    if path is None:
        path = config.MODELS_DIR / "cnn_breastmnist.pt"
    config.ensure_dirs()
    torch.save(model.state_dict(), path)
    return path


# --------------------------------------------------------------------------- #
# 6. Visualizações
# --------------------------------------------------------------------------- #
def _denormalize(image: torch.Tensor) -> np.ndarray:
    """Desfaz a normalização [-1,1] -> [0,1] para exibição."""
    img = image.squeeze().numpy()
    return np.clip(img * 0.5 + 0.5, 0, 1)


def plot_training_history(history: TrainingHistory, save_path: Path | None = None):
    """Curvas de perda (treino/val) e de recall/F1 de validação por época."""
    import matplotlib.pyplot as plt

    epochs = range(1, len(history.train_loss) + 1)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    ax1.plot(epochs, history.train_loss, label="treino", marker="o", ms=3)
    ax1.plot(epochs, history.val_loss, label="validação", marker="o", ms=3)
    ax1.set_title("Perda por época")
    ax1.set_xlabel("época")
    ax1.set_ylabel("perda")
    ax1.legend()

    ax2.plot(epochs, history.val_recall, label="recall (maligno)", marker="o", ms=3, color="#c0392b")
    ax2.plot(epochs, history.val_f1, label="F1 (maligno)", marker="o", ms=3, color="#2a7ab9")
    ax2.set_title("Métricas de validação por época")
    ax2.set_xlabel("época")
    ax2.set_ylabel("score")
    ax2.set_ylim(0, 1.02)
    ax2.legend()

    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def plot_confusion_matrix(cm: np.ndarray, save_path: Path | None = None):
    """Matriz de confusão da CNN (rótulos legíveis)."""
    import matplotlib.pyplot as plt
    from sklearn.metrics import ConfusionMatrixDisplay

    labels = [CLASS_NAMES[0], CLASS_NAMES[POSITIVE_IS_MALIGNANT]]
    fig, ax = plt.subplots(figsize=(5, 4))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)
    disp.plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("Matriz de Confusão — CNN (ultrassom)")
    ax.set_xlabel("Previsto")
    ax.set_ylabel("Real")
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def plot_sample_predictions(model, loader, n: int = 8, save_path: Path | None = None):
    """Mostra n imagens de teste com rótulo real x previsto (verde=acerto)."""
    import matplotlib.pyplot as plt

    model.eval()
    images, targets = next(iter(loader))
    with torch.no_grad():
        probs = F.softmax(model(images), dim=1)[:, POSITIVE_IS_MALIGNANT]
        preds = model(images).argmax(1)

    n = min(n, images.size(0))
    ncols = 4
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(3 * ncols, 3 * nrows))
    axes = np.array(axes).flatten()

    for i in range(n):
        ax = axes[i]
        ax.imshow(_denormalize(images[i]), cmap="gray")
        real = int(targets[i].view(-1)[0])
        pred = int(preds[i])
        cor = "green" if real == pred else "red"
        ax.set_title(
            f"real: {CLASS_NAMES[real]}\nprev: {CLASS_NAMES[pred]} ({probs[i]:.2f})",
            color=cor,
            fontsize=9,
        )
        ax.axis("off")
    for ax in axes[n:]:
        ax.axis("off")

    fig.suptitle("Amostras de teste — previsões da CNN", y=1.02)
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig


def plot_gradcam_grid(model, loader, n: int = 6, save_path: Path | None = None):
    """Sobrepõe o heatmap Grad-CAM a n imagens (regiões que a CNN olhou)."""
    import matplotlib.pyplot as plt

    cam_generator = GradCAM(model)
    images, targets = next(iter(loader))
    n = min(n, images.size(0))

    fig, axes = plt.subplots(2, n, figsize=(2.6 * n, 5.4))
    for i in range(n):
        img = images[i : i + 1]
        heatmap = cam_generator.generate(img, target_class=POSITIVE_IS_MALIGNANT)
        base = _denormalize(images[i])
        real = int(targets[i].view(-1)[0])

        axes[0, i].imshow(base, cmap="gray")
        axes[0, i].set_title(f"real: {CLASS_NAMES[real]}", fontsize=9)
        axes[0, i].axis("off")

        axes[1, i].imshow(base, cmap="gray")
        axes[1, i].imshow(heatmap, cmap="jet", alpha=0.5)
        axes[1, i].set_title("Grad-CAM", fontsize=9)
        axes[1, i].axis("off")

    fig.suptitle("Grad-CAM — regiões que a CNN usou para decidir 'maligno'", y=1.01)
    fig.tight_layout()
    if save_path is not None:
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    return fig
