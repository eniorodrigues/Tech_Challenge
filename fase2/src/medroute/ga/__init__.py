"""Algoritmo genético para o VRP hospitalar (evolução do TSP do código base)."""

from .engine import GAConfig, GAResult, GenerationStats, GeneticAlgorithm, solve

__all__ = ["GAConfig", "GAResult", "GenerationStats", "GeneticAlgorithm", "solve"]
