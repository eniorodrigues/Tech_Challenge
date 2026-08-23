# ---------------------------------------------------------------------------
# Tech Challenge — Fase 1
# Imagem reprodutível para rodar o pipeline tabular, o pipeline de visão
# computacional (CNN) e a suíte de testes sem instalar nada na máquina host.
#
# Build:
#   docker build -t tech-challenge-fase1 .
#
# Pipeline tabular (padrão):
#   docker run --rm -v "$(pwd)/reports:/app/reports" -v "$(pwd)/models:/app/models" tech-challenge-fase1
#
# Pipeline da CNN (EXTRA):
#   docker run --rm -v "$(pwd)/reports:/app/reports" -v "$(pwd)/models:/app/models" \
#     tech-challenge-fase1 python main_vision.py
#
# Testes (provas de correção):
#   docker run --rm tech-challenge-fase1 python -m pytest -v
#
# Notebooks (Jupyter em http://localhost:8888):
#   docker run --rm -p 8888:8888 tech-challenge-fase1 \
#     jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg

WORKDIR /app

# Dependências de compilação exigidas por algumas rodas (shap/scikit-image).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# O índice extra entrega as rodas CPU do PyTorch: imagem muito menor e sem
# nenhuma dependência de GPU/CUDA.
RUN pip install --upgrade pip \
    && pip install --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements.txt

COPY . .

# As saídas (figuras, métricas, modelos) são geradas aqui — monte volumes para
# recuperá-las no host.
RUN mkdir -p reports/figures models data

CMD ["python", "main.py"]
