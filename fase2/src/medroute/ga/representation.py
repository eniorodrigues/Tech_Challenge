"""
Representação genética das rotas.

Cromossomo = **permutação das N entregas intercalada com K−1 separadores**.

::

    N = 7 entregas, K = 3 veículos  →  separadores 8 e 9

    cromossomo:  [ 3  6  1 | 8 | 5  2 | 9 | 7  4 ]
    rotas:        V1: 3 → 6 → 1      V2: 5 → 2      V3: 7 → 4

Propriedades que justificam a escolha:

* **Generaliza o código base.** Com K = 1 não há separador e o cromossomo é
  exatamente a permutação de cidades do TSP original.
* **Toda permutação decodifica numa solução completa** (cada entrega aparece
  uma única vez). Os operadores clássicos de permutação (OX, PMX, swap,
  inversão...) funcionam sem adaptação — os separadores são genes como
  quaisquer outros.
* **O GA decide quantas entregas cada veículo faz** movendo separadores. Dois
  separadores vizinhos = veículo parado (rota vazia).
* Inverter um trecho que contém um separador troca o "rabo" de duas rotas —
  é o movimento 2-opt* entre veículos, de graça.

Restrições (capacidade, autonomia, compatibilidade...) **não** são impostas
pela representação: são cobradas na fitness e corrigidas pelos operadores
especializados de :mod:`medroute.ga.operators`.
"""

from __future__ import annotations

import random
from typing import Sequence

from ..problem import Problem


def random_chromosome(problem: Problem, rng: random.Random) -> list[int]:
    """Permutação aleatória uniforme de entregas + separadores."""
    genes = list(range(1, problem.n + problem.k))
    rng.shuffle(genes)
    return genes


def is_valid(chromosome: Sequence[int], problem: Problem) -> bool:
    """Um cromossomo válido é uma permutação exata de ``1..N+K-1``."""
    return sorted(chromosome) == list(range(1, problem.n + problem.k))


def separator_positions(chromosome: Sequence[int], n: int) -> list[int]:
    return [i for i, g in enumerate(chromosome) if g > n]


def route_slices(chromosome: Sequence[int], n: int) -> list[tuple[int, int]]:
    """Intervalos ``[ini, fim)`` de cada rota dentro do cromossomo."""
    limites = [-1] + separator_positions(chromosome, n) + [len(chromosome)]
    return [(limites[j] + 1, limites[j + 1]) for j in range(len(limites) - 1)]


def normalize_separators(chromosome: Sequence[int], n: int) -> list[int]:
    """Renumera os separadores na ordem em que aparecem (N+1, N+2, ...).

    Dois cromossomos que só diferem pelo *rótulo* dos separadores representam
    a mesma solução; normalizar evita duplicatas disfarçadas na população e
    melhora o aproveitamento do cache de fitness.
    """
    out = list(chromosome)
    prox = n + 1
    for i, g in enumerate(out):
        if g > n:
            out[i] = prox
            prox += 1
    return out
