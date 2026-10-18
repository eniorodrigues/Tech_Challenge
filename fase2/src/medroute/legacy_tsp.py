"""
O algoritmo genético do **código base** (``genetic_algorithm.py`` + ``tsp.py``),
reproduzido fielmente para servir de ponto de partida e de linha de base.

O original trabalha com cidades como tuplas ``(x, y)`` em pixels e distância
euclidiana. Aqui a única adaptação é trocar a tupla pelo índice do ponto e a
distância euclidiana pela matriz em km do cenário — a lógica evolutiva é a
mesma:

* população inicial aleatória (``generate_random_population``);
* fitness = comprimento do ciclo (``calculate_fitness``);
* elitismo de 1 indivíduo;
* seleção por roleta com peso ``1/fitness`` (``random.choices``);
* crossover OX (``order_crossover``);
* mutação: troca de dois vizinhos com probabilidade 0,5 (``mutate``).

Problemas encontrados no base (documentados no relatório técnico):

1. ``tsp.py`` chama ``order_crossover(parent1, parent1)`` — o pai cruza com
   ele mesmo, o filho é uma cópia e **não existe recombinação**. A flag
   ``fix_crossover_bug`` (padrão ``True``) usa ``parent2``.
2. A mutação só troca vizinhos (o próprio código deixa um TODO pedindo
   inversão de trechos) — exploração muito lenta.
3. Não há restrição alguma: um único "caixeiro" visita tudo, sem carga,
   autonomia, prioridade ou horário.
4. ``draw_functions.draw_text`` usa ``np`` e ``HEIGHT`` sem importá-los, e
   ``renderer.tostring_rgb()`` não existe mais no Matplotlib ≥ 3.10.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np


@dataclass
class BaseTSPResult:
    best_tour: list[int]                 # começa e termina implícito no nó 0
    best_distance: float
    history: list[float] = field(default_factory=list)


def _ciclo(tour: list[int], D: list[list[float]]) -> float:
    """``calculate_fitness`` do base: soma das arestas do ciclo fechado."""
    n = len(tour)
    return sum(D[tour[i]][tour[(i + 1) % n]] for i in range(n))


def _order_crossover(p1: list[int], p2: list[int], rng: random.Random) -> list[int]:
    """Cópia literal da lógica do ``order_crossover`` do base."""
    length = len(p1)
    start = rng.randint(0, length - 1)
    end = rng.randint(start + 1, length)
    child = p1[start:end]
    remaining_positions = [i for i in range(length) if i < start or i >= end]
    remaining_genes = [g for g in p2 if g not in child]
    for position, gene in zip(remaining_positions, remaining_genes):
        child.insert(position, gene)
    return child


def _mutate(solution: list[int], p: float, rng: random.Random) -> list[int]:
    """``mutate`` do base: troca o gene ``i`` com o ``i+1``."""
    out = list(solution)
    if rng.random() < p and len(solution) >= 2:
        i = rng.randint(0, len(solution) - 2)
        out[i], out[i + 1] = solution[i + 1], solution[i]
    return out


def run_base_tsp(
    dist_km: np.ndarray,
    generations: int = 600,
    population_size: int = 100,
    mutation_probability: float = 0.5,
    seed: int = 42,
    fix_crossover_bug: bool = True,
) -> BaseTSPResult:
    """Roda o GA do código base sobre todos os pontos (central + entregas)."""
    rng = random.Random(seed)
    D = np.asarray(dist_km).tolist()
    cidades = list(range(len(D)))
    populacao = [rng.sample(cidades, len(cidades)) for _ in range(population_size)]
    historico: list[float] = []
    melhor, melhor_f = None, float("inf")

    for _ in range(generations):
        fits = [_ciclo(ind, D) for ind in populacao]
        ordem = sorted(range(len(populacao)), key=fits.__getitem__)
        populacao = [populacao[i] for i in ordem]
        fits = [fits[i] for i in ordem]
        if fits[0] < melhor_f:
            melhor, melhor_f = list(populacao[0]), fits[0]
        historico.append(fits[0])

        nova = [populacao[0]]                       # ELITISMO
        pesos = [1.0 / f for f in fits]
        while len(nova) < population_size:
            pai1, pai2 = rng.choices(populacao, weights=pesos, k=2)
            outro = pai2 if fix_crossover_bug else pai1
            filho = _order_crossover(pai1, outro, rng)
            filho = _mutate(filho, mutation_probability, rng)
            nova.append(filho)
        populacao = nova

    assert melhor is not None
    zero = melhor.index(0)                          # gira para começar na central
    tour = melhor[zero:] + melhor[:zero]
    return BaseTSPResult(best_tour=tour, best_distance=melhor_f, history=historico)
