"""
Tech Challenge — Fase 2 · Projeto 2: Otimização de Rotas para Distribuição
de Medicamentos e Insumos.

Ponto de entrada do pipeline completo (equivalente a ``medroute``):

    python main.py                 # cenário → GA → comparativo → mapas → semana → LLM
    python main.py --sem-llm       # idem, sem chamar a LLM
    python main.py otimizar --geracoes 800
    python main.py llm perguntar "Qual veículo leva a insulina do PD-05?"

Veja ``python main.py <comando> --help`` para as opções.
"""

import sys
from pathlib import Path

# Permite rodar sem instalar o pacote (pip install -e .).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from medroute.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
