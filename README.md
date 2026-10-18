> **Fase 2 (Projeto 2 — otimização de rotas de medicamentos e insumos com algoritmo genético + LLM):** veja [`fase2/README.md`](fase2/README.md). Tudo da Fase 2 fica na pasta `fase2/`, com ambiente, testes e documentação próprios.

# Tech Challenge — Fase 1
## Sistema inteligente de suporte ao diagnóstico em saúde da mulher

Solução de **Machine Learning** para apoiar profissionais de saúde na
**detecção precoce de risco de câncer de mama**, classificando tumores como
**malignos** ou **benignos** a partir de dados de exame.

O projeto entrega a base de IA pedida na Fase 1: exploração dos dados,
pré-processamento sem vazamento, modelagem com múltiplas técnicas, avaliação
com métricas adequadas ao contexto clínico e explicabilidade (feature
importance + SHAP), tudo reprodutível de ponta a ponta.

Inclui ainda o item **EXTRA de Visão Computacional**: uma **CNN** que
diagnostica a partir de **imagens de ultrassom de mama**, com explicabilidade
via **Grad-CAM**. Veja a [seção 9](#9-extra--visão-computacional-cnn-em-imagens).

---

## 1. O problema

Redes de atendimento à mulher lidam com volume crescente de pacientes e
precisam **acelerar a triagem** e **apoiar a decisão médica** para não deixar
passar casos de risco. Aqui atacamos a **classificação binária** de tumores de
mama, priorizando a detecção dos casos malignos — onde um erro custa mais caro.

> **Premissa central:** o modelo é um **copiloto**. O médico tem sempre a
> palavra final no diagnóstico.

## 2. A base de dados

**Breast Cancer Wisconsin (Diagnostic)** — 569 pacientes, 30 features numéricas
extraídas de imagens de aspirados por agulha fina (PAAF) de massas mamárias.
Cada feature descreve um núcleo celular (raio, textura, perímetro, área,
concavidade, etc.) em três resumos: média, erro-padrão e "pior" valor.

- Fonte: UCI ML Repository / embutida em `sklearn.datasets.load_breast_cancer`.
- Escolhida por ser a **tarefa principal sugerida** no enunciado, pública e sem
  dependência de download externo → **100% reprodutível**.
- Distribuição: 357 benignos (63%) / 212 malignos (37%) — desbalanceamento
  moderado, tratado com estratificação e `class_weight='balanced'`.

**Convenção de rótulo (decisão clínica):** remapeamos para `1 = maligno`
(classe positiva de interesse) e `0 = benigno`, para que *recall* signifique
diretamente "proporção de malignos detectados".

## 3. Estrutura do projeto

```
Tech_Challenge/
├── main.py                     # Pipeline tabular completo (CLI)
├── main_vision.py              # EXTRA: pipeline da CNN de imagem (CLI)
├── Dockerfile                  # Imagem reprodutível (CPU) — ver seção 4.1
├── requirements.txt
├── README.md
├── src/                        # Módulos reutilizáveis
│   ├── config.py               # Semente, caminhos, convenção de rótulo
│   ├── data_loader.py          # Carga da base + remapeamento do alvo
│   ├── preprocessing.py        # Limpeza, split estratificado, scaler (sem leakage)
│   ├── eda.py                  # Análise exploratória e gráficos
│   ├── modeling.py             # 4 modelos + validação cruzada
│   ├── evaluation.py           # Métricas, matriz de confusão, ROC
│   ├── explainability.py       # Feature importance + SHAP
│   └── vision.py               # EXTRA: CNN, treino, avaliação e Grad-CAM
├── notebooks/
│   ├── tech_challenge_breast_cancer.ipynb   # Notebook tabular (com saídas)
│   └── tech_challenge_cnn_imagem.ipynb      # EXTRA: notebook da CNN (com saídas)
├── tests/
│   ├── test_pipeline.py        # Provas de correção tabular (inclui anti-leakage)
│   └── test_vision.py          # Provas de correção da CNN (inclui remap do rótulo)
├── docs/
│   └── ROTEIRO_VIDEO.md        # Roteiro do vídeo de demonstração
├── scripts/
│   └── gerar_entregavel_pdf.py # Gera o PDF entregável da Fase 1
├── data/                       # CSV da base + BreastMNIST (imagens) em cache
├── models/                     # melhor_modelo.joblib + cnn_breastmnist.pt
└── reports/
    ├── metricas_teste.csv
    ├── metricas_validacao_cruzada.csv
    └── figures/                # Todos os gráficos em PNG (01–11)
```

## 4. Como executar

Requer **Python 3.11**.

```bash
# 1. Ambiente virtual + dependências
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # Linux/Mac
pip install -r requirements.txt

# 2. Rodar o pipeline tabular (gera figuras 01–07, métricas e o modelo)
python main.py

# 3. EXTRA: rodar o pipeline da CNN de imagem (baixa o BreastMNIST, treina,
#    gera figuras 08–11 e o modelo cnn_breastmnist.pt). Treina em CPU (~2-3 min).
python main_vision.py

# 4. Rodar as provas de correção (tabular + visão)
python -m pytest -v

# 5. Abrir os notebooks narrados
jupyter notebook notebooks/tech_challenge_breast_cancer.ipynb
jupyter notebook notebooks/tech_challenge_cnn_imagem.ipynb
```

> A CNN exige `torch`, `torchvision` e `medmnist` (ver `requirements.txt`). O
> `medmnist` baixa o dataset de ultrassom automaticamente do Zenodo na primeira
> execução — não precisa de Kaggle.

> Dica: com [uv](https://docs.astral.sh/uv/) é mais rápido —
> `uv venv --python 3.11 .venv` e `uv pip install -r requirements.txt`.

### 4.1 Execução via Docker

O `Dockerfile` monta a imagem já com as rodas **CPU** do PyTorch (sem
dependência de GPU/CUDA). Os volumes trazem figuras e modelos de volta ao host.

```bash
# Build
docker build -t tech-challenge-fase1 .

# Pipeline tabular (comando padrão da imagem)
docker run --rm -v "$(pwd)/reports:/app/reports" -v "$(pwd)/models:/app/models" tech-challenge-fase1

# Pipeline da CNN (EXTRA)
docker run --rm -v "$(pwd)/reports:/app/reports" -v "$(pwd)/models:/app/models" \
  tech-challenge-fase1 python main_vision.py

# Provas de correção
docker run --rm tech-challenge-fase1 python -m pytest -v

# Notebooks em http://localhost:8888
docker run --rm -p 8888:8888 tech-challenge-fase1 \
  jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```

### 4.2 Gerar o PDF entregável

```bash
python scripts/gerar_entregavel_pdf.py --repo <URL_DO_REPO> --video <URL_DO_VIDEO> --autores "Seu Nome"
```

Gera `Tech_Challenge_Fase1_Entregavel.pdf` na raiz, consolidando relatório
técnico, resultados, figuras e roteiro do vídeo. As tabelas de métricas são
lidas de `reports/*.csv`, então rode `main.py` antes.

## 5. Metodologia e decisões técnicas

| Etapa | O que foi feito |
|---|---|
| **Exploração** | Balanceamento, estatísticas descritivas, distribuições por classe, matriz de correlação e identificação de multicolinearidade. |
| **Pré-processamento** | Limpeza defensiva (duplicatas/vazios), imputação por mediana e padronização **dentro do `Pipeline`** (sem vazamento), split estratificado 80/20. |
| **Correlação** | Pearson; identificadas as features mais preditivas e 21 pares redundantes (\|r\| ≥ 0,9). |
| **Modelagem** | 4 técnicas: Regressão Logística, Árvore de Decisão, KNN e Random Forest. |
| **Validação** | Validação cruzada estratificada (5 folds) no treino + holdout de teste. |
| **Avaliação** | accuracy, precision, **recall**, F1 e ROC-AUC + matriz de confusão. |
| **Explicabilidade** | Importância de features + SHAP (contribuição por paciente). |

### Por que RECALL é a métrica prioritária

O custo dos erros é **assimétrico**:

- **Falso negativo** (dizer que um tumor maligno é benigno): atrasa o
  tratamento, risco à vida. **Custo altíssimo.**
- **Falso positivo** (dizer que um benigno é maligno): gera biópsia e
  ansiedade. **Custo real, porém muito menor.**

Por isso priorizamos o **recall da classe maligna** (minimizar falsos
negativos), com F1/precision como contrapeso. **Accuracy sozinha engana** em
base desbalanceada: chutar sempre "benigno" já daria 63%.

## 6. Resultados

Desempenho no **conjunto de teste** (114 pacientes, holdout estratificado):

| Modelo | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
| **Regressão Logística** | 0,974 | 0,976 | **0,952** | 0,964 | 0,995 |
| Random Forest | 0,974 | 1,000 | 0,929 | 0,963 | 0,998 |
| KNN | 0,956 | 0,974 | 0,905 | 0,938 | 0,983 |
| Árvore de Decisão | 0,930 | 0,925 | 0,881 | 0,902 | 0,901 |

A **Regressão Logística** foi o melhor modelo pelo critério de recall: detectou
40 dos 42 tumores malignos do teste (**apenas 2 falsos negativos**), com 1 falso
positivo. O Random Forest não teve falsos positivos (precision 1,0) mas deixou
passar mais um maligno — o trade-off é discutido no notebook.

> Os números exatos podem variar por versão de biblioteca, mas a semente fixa
> (`RANDOM_STATE = 42`) garante reprodutibilidade no mesmo ambiente.

### Explicabilidade

As duas técnicas contam histórias complementares — e a diferença entre elas é
instrutiva:

- **Coeficientes da Regressão Logística** (fig. 06): no topo aparecem
  `worst texture`, `radius error` e `worst symmetry`. Isso **não** significa que
  raio e área sejam irrelevantes: é a **multicolinearidade** (21 pares com
  |r| ≥ 0,9) repartindo o peso entre features redundantes. Coeficiente linear
  sob multicolinearidade não é medida confiável de importância.
- **SHAP** (fig. 07), calculado sobre o Random Forest: as features de maior
  impacto são `worst area`, `worst perimeter`, `worst concave points`,
  `mean concave points` e `worst radius` — **convergindo com a EDA** e
  corrigindo a leitura enviesada dos coeficientes. Valores altos dessas medidas
  empurram consistentemente a previsão para "maligno".

A leitura final é **clinicamente coerente**: tumores malignos têm núcleos
maiores e contornos mais irregulares. O modelo aprendeu o critério que a
patologia já reconhece, o que aumenta a confiança para uso clínico assistido.

## 7. O modelo pode ser usado na prática?

**Sim, como ferramenta de apoio — nunca de decisão autônoma.**

- **Uso recomendado:** priorização de fila (sinalizar alto risco para revisão
  rápida) e segunda opinião / rede de segurança (alertar divergências).
- **O médico decide.** O sistema entrega probabilidade + explicação; a conduta é
  do profissional. Em triagem, opera-se com limiar que favorece o recall.
- **Limitações honestas:** base pequena e de fonte única; features já extraídas
  por especialistas (não substitui o exame); não é dispositivo médico
  certificado; uso real exigiria validação externa/prospectiva, aprovação
  regulatória e monitoramento de viés entre subgrupos.

## 8. Provas de correção (testes)

`tests/test_pipeline.py` cobre as invariantes que sustentam a validade dos
resultados, com destaque para o **teste anti-vazamento de dados**: prova que o
`StandardScaler` aprende as estatísticas **apenas do treino** e não do dataset
completo. Se esse teste falha, os números de desempenho não são confiáveis.

`tests/test_vision.py` faz o mesmo para o pipeline da CNN, com destaque para o
**teste de remapeamento do rótulo** — se o maligno não fosse a classe positiva,
todo o recall discutido estaria invertido.

**Os 19 testes passam** (12 tabulares + 7 de visão):

```bash
python -m pytest -v
```

## 9. EXTRA — Visão Computacional (CNN em imagens)

Além do modelo tabular, entregamos um pipeline de **Deep Learning** que
diagnostica a partir de **imagens de ultrassom de mama**.

- **Dataset:** **BreastMNIST** (pacote `medmnist`), derivado do **BUSI** — 780
  imagens de ultrassom, baixadas automaticamente do Zenodo (**sem Kaggle**).
- **Modelo:** CNN compacta em PyTorch (3 blocos convolucionais + classificador
  denso, ~24 mil parâmetros), treinável em **CPU em poucos minutos**.
- **Mesma convenção clínica:** `1 = maligno`; foco em **recall**.
- **Explicabilidade:** **Grad-CAM** — destaca as regiões da imagem que a CNN
  usou para decidir (o análogo visual do SHAP).
- Código em [`src/vision.py`](src/vision.py), orquestração em
  [`main_vision.py`](main_vision.py), narrativa em
  [`notebooks/tech_challenge_cnn_imagem.ipynb`](notebooks/tech_challenge_cnn_imagem.ipynb).

### Resultados no teste (156 imagens) e a escolha do ponto de operação

Como a CNN gera uma probabilidade, o **limiar de decisão** é escolhido conforme
a prioridade clínica (calibrado na **validação**, nunca no teste):

| Ponto de operação | Accuracy | Precision | Recall | F1 | ROC-AUC | Falsos negativos |
|---|---|---|---|---|---|---|
| Limiar padrão (0,50) | 0,853 | 0,771 | 0,643 | 0,701 | 0,854 | 15 |
| **Ponto clínico (0,29)** | 0,718 | 0,485 | **0,786** | 0,600 | 0,854 | **9** |

Baixar o limiar **reduz os cânceres não detectados** (15 → 9 falsos negativos)
ao custo de mais falsos positivos — a mesma discussão de métrica do modelo
tabular, agora aplicada à triagem por imagem. O `ROC-AUC` ~0,85 está dentro do
que a literatura reporta para o BreastMNIST (dataset pequeno e de baixa
resolução).

### Leitura crítica
O modelo de imagem é **honestamente mais fraco** que o tabular (AUC 0,85 vs
0,99). Isso é esperado: ele resolve um problema mais difícil — aprende os
padrões direto dos pixels, sem features pré-extraídas, com poucos dados e imagens
28→64 px. Serve como **prova de conceito** e base para evoluir com transfer
learning (ResNet/EfficientNet), imagens de maior resolução e mais dados. O
Grad-CAM é o que torna o uso responsável: permite auditar **onde** a rede olhou
antes de confiar na recomendação.

---

### Mapa das entregas exigidas → onde estão

| Exigência do desafio | Onde |
|---|---|
| Escolha e discussão do dataset | README §2, notebook §1 |
| Carregar e explorar a base | notebook §2–§3, `src/eda.py` |
| Estatísticas descritivas e distribuições | notebook §3, `reports/figures/` |
| Padrões de saúde/segurança feminina | notebook §3.4 |
| Limpeza e valores ausentes | `src/preprocessing.py`, notebook §3.3–§4 |
| Pipeline de pré-processamento | `src/preprocessing.py` (`Pipeline`/`ColumnTransformer`) |
| Variáveis categóricas/numéricas em formato adequado | `src/preprocessing.py` |
| Análise de correlação | notebook §3.5, `src/eda.py` |
| Modelos (2+ técnicas) | `src/modeling.py` (4 técnicas) |
| Separação treino/teste | `src/preprocessing.py` (`split_data`, estratificado) |
| Treino + avaliação (accuracy, recall, F1) | `src/evaluation.py`, notebook §5–§6 |
| Discussão da escolha da métrica | README §5, notebook §6.1 |
| Explicabilidade (feature importance + SHAP) | `src/explainability.py`, notebook §7 |
| Discussão crítica / uso na prática | README §7, notebook §8 |
| Projeto Python estruturado e documentado | todo o repositório |
| **EXTRA** — diagnóstico por imagem com CNN | `src/vision.py`, `main_vision.py`, notebook CNN |
| **EXTRA** — explicabilidade da CNN (Grad-CAM) | `src/vision.py`, notebook CNN §6 |
| Dockerfile | `Dockerfile`, README §4.1 |
| PDF entregável | `scripts/gerar_entregavel_pdf.py` → `Tech_Challenge_Fase1_Entregavel.pdf` |
| Roteiro do vídeo de demonstração | `docs/ROTEIRO_VIDEO.md` |
