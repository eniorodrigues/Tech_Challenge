"""
Provas de correção do pipeline de dados e modelagem.

Estes testes existem para garantir as invariantes que sustentam a validade
científica do resultado — especialmente a AUSÊNCIA DE VAZAMENTO DE DADOS
(data leakage), que é o erro mais comum e mais grave em fluxos de cruzamento
e transformação de dados. Se um destes testes falha, os números de desempenho
relatados não são confiáveis.

Rodar:
    python -m pytest -v
"""

from __future__ import annotations

import numpy as np
import pytest

from src import config, data_loader, evaluation, explainability, modeling
from src.preprocessing import build_preprocessor, clean_data, split_data


@pytest.fixture(scope="module")
def df():
    return clean_data(data_loader.load_dataframe(save_csv=False))


@pytest.fixture(scope="module")
def split(df):
    x, y = data_loader.split_features_target(df)
    return split_data(x, y)


# --------------------------------------------------------------------------- #
# 1. Integridade dos dados
# --------------------------------------------------------------------------- #
def test_shape_esperado(df):
    """A base deve ter 569 pacientes e 30 features + 1 coluna de alvo."""
    assert df.shape == (569, 31)


def test_remapeamento_do_alvo(df):
    """Prova que o alvo foi remapeado corretamente: 1=maligno, 0=benigno.

    No dataset original o câncer maligno é a classe minoritária (212 casos).
    Se o remapeamento estivesse invertido, teríamos 357 'malignos'.
    """
    contagem = df[config.TARGET_COLUMN].value_counts()
    assert contagem[config.POSITIVE_LABEL] == 212  # maligno
    assert contagem[config.NEGATIVE_LABEL] == 357  # benigno


def test_sem_valores_ausentes(df):
    """O Breast Cancer Wisconsin não deve conter valores ausentes."""
    assert df.isna().sum().sum() == 0


def test_alvo_binario(df):
    """O alvo só pode conter 0 e 1."""
    assert set(df[config.TARGET_COLUMN].unique()) == {0, 1}


# --------------------------------------------------------------------------- #
# 2. Split estratificado
# --------------------------------------------------------------------------- #
def test_split_preserva_proporcao(split):
    """A estratificação deve manter a proporção de maligno entre treino/teste."""
    x_train, x_test, y_train, y_test = split
    assert abs(y_train.mean() - y_test.mean()) < 0.02


def test_split_sem_sobreposicao(split):
    """Nenhuma amostra pode estar simultaneamente em treino e teste."""
    x_train, x_test, _, _ = split
    indices_comuns = set(x_train.index) & set(x_test.index)
    assert len(indices_comuns) == 0


# --------------------------------------------------------------------------- #
# 3. PROVA DE AUSÊNCIA DE VAZAMENTO DE DADOS (o teste mais importante)
# --------------------------------------------------------------------------- #
def test_scaler_ajustado_somente_no_treino(split, df):
    """Prova que o StandardScaler aprende as estatísticas APENAS do treino.

    Ajustamos o pré-processador no conjunto de treino e verificamos que a
    média aprendida bate com a média do treino — e NÃO com a média do dataset
    completo (que incluiria o teste). Se batesse com a média completa, haveria
    vazamento de dados do teste para o treino.
    """
    x_train, x_test, _, _ = split
    features = data_loader.feature_columns(df)

    preprocessor = build_preprocessor(features)
    preprocessor.fit(x_train)

    scaler = preprocessor.named_transformers_["num"].named_steps["scaler"]
    media_aprendida = scaler.mean_

    media_treino = x_train[features].mean().to_numpy()
    media_completa = df[features].mean().to_numpy()

    # A média aprendida deve ser idêntica à do treino...
    np.testing.assert_allclose(media_aprendida, media_treino, rtol=1e-6)
    # ...e mensuravelmente diferente da média do dataset completo.
    assert not np.allclose(media_aprendida, media_completa, rtol=1e-6)


# --------------------------------------------------------------------------- #
# 4. Modelagem
# --------------------------------------------------------------------------- #
def test_pipelines_preveem_rotulos_validos(split, df):
    """Todo modelo treinado deve prever apenas rótulos válidos (0/1)."""
    x_train, x_test, y_train, y_test = split
    features = data_loader.feature_columns(df)
    models = modeling.fit_models(modeling.build_models(features), x_train, y_train)

    for nome, model in models.items():
        preds = model.predict(x_test)
        assert set(np.unique(preds)).issubset({0, 1}), f"{nome} previu rótulo inválido"


def test_reprodutibilidade(split, df):
    """Mesma semente -> mesmas previsões (resultado determinístico)."""
    x_train, x_test, y_train, _ = split
    features = data_loader.feature_columns(df)

    m1 = modeling.fit_models(modeling.build_models(features), x_train, y_train)
    m2 = modeling.fit_models(modeling.build_models(features), x_train, y_train)

    for nome in m1:
        np.testing.assert_array_equal(
            m1[nome].predict(x_test), m2[nome].predict(x_test)
        )


# --------------------------------------------------------------------------- #
# 5. Avaliação e explicabilidade
# --------------------------------------------------------------------------- #
def test_metricas_no_intervalo_valido(split, df):
    """Todas as métricas devem estar no intervalo [0, 1]."""
    x_train, x_test, y_train, y_test = split
    features = data_loader.feature_columns(df)
    models = modeling.fit_models(modeling.build_models(features), x_train, y_train)

    resultados = evaluation.evaluate_all(models, x_test, y_test)
    assert ((resultados >= 0) & (resultados <= 1)).all().all()


def test_feature_importance_cobre_todas_as_features(split, df):
    """A importância de features deve retornar exatamente 30 features."""
    x_train, x_test, y_train, _ = split
    features = data_loader.feature_columns(df)
    models = modeling.fit_models(modeling.build_models(features), x_train, y_train)

    fi = explainability.feature_importance(models["Random Forest"], features)
    assert len(fi) == len(features)
    assert set(fi["feature"]) == set(features)


def test_confusion_breakdown_soma_total(split, df):
    """TN + FP + FN + TP deve igualar o tamanho do conjunto de teste."""
    x_train, x_test, y_train, y_test = split
    features = data_loader.feature_columns(df)
    models = modeling.fit_models(modeling.build_models(features), x_train, y_train)

    breakdown = evaluation.confusion_breakdown(models["Random Forest"], x_test, y_test)
    assert sum(breakdown.values()) == len(y_test)
