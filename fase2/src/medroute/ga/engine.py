"""
Motor do algoritmo genético.

Ciclo de uma geração (a mesma espinha dorsal do ``tsp.py`` do código base,
com as peças trocadas por versões mais fortes)::

    avaliar → ordenar → [busca local no melhor] → registrar estatísticas
            → elitismo → (seleção → crossover → mutação)* → nova população

Mecanismos adicionados em relação ao código base:

* **População inicial semeada**: além de indivíduos aleatórios, entram as
  soluções das heurísticas construtivas (vizinho mais próximo, sweep,
  economias) e variações delas — o TODO "usar heurística para inicializar"
  do base.
* **Portfólio de operadores**: a cada filho sorteia-se um crossover e uma
  mutação, com pesos configuráveis.
* **Anti-duplicata**: filho idêntico a alguém da nova população sofre uma
  mutação extra (mantém diversidade).
* **Imigrantes**: após ``immigrants_after`` gerações sem melhora, parte da
  população é substituída por indivíduos novos (aleatórios e perturbações do
  melhor) — combate a convergência prematura.
* **Memético**: 2-opt periódico no melhor indivíduo e relocate entre rotas.
* **Parada antecipada** por paciência ou por tempo, e *callback* por geração
  (a interface usa para barra de progresso e para cancelar).
* **Cache de fitness** por cromossomo (populações maduras repetem muito).
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import asdict, dataclass, field
from typing import Callable

from ..domain import Scenario
from ..problem import Evaluation, FitnessWeights, Problem
from . import operators as ops
from .local_search import improve_solution, two_opt_route
from .representation import normalize_separators, random_chromosome

DEFAULT_CROSSOVER_MIX = {"ox": 0.3, "pmx": 0.1, "erx": 0.1, "bcrc": 0.5}
DEFAULT_MUTATION_MIX = {
    "swap": 1.0, "inversion": 2.0, "insertion": 2.0, "scramble": 0.5,
    "priority": 1.0, "repair": 1.5,
}


@dataclass
class GAConfig:
    """Hiperparâmetros do GA (os padrões são os do experimento principal)."""

    population_size: int = 120
    generations: int = 500
    crossover: str = "mix"                 # ox | pmx | erx | bcrc | mix
    crossover_mix: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_CROSSOVER_MIX))
    crossover_rate: float = 0.9
    mutation: str = "mix"                  # nome de um operador ou mix
    mutation_mix: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_MUTATION_MIX))
    mutation_rate: float = 0.4
    selection: str = "tournament"          # tournament | roulette | rank | truncation
    tournament_k: int = 3
    elitism: int = 2
    heuristic_seeds: bool = True
    local_search: bool = True
    local_search_every: int = 10
    relocate_every: int = 50
    final_polish: bool = True
    immigrants_after: int = 40
    immigrant_fraction: float = 0.25
    patience: int | None = 250
    time_limit_s: float | None = None
    seed: int = 42

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def base_code_like(cls, **kw) -> "GAConfig":
        """Configuração equivalente ao código base (para comparação/ablação)."""
        base = dict(
            population_size=100, crossover="ox", mutation="adjacent_swap",
            mutation_rate=0.5, selection="roulette", elitism=1,
            heuristic_seeds=False, local_search=False, final_polish=False,
            immigrants_after=10**9, patience=None,
        )
        base.update(kw)
        return cls(**base)


@dataclass
class GenerationStats:
    generation: int
    best: float
    mean: float
    worst: float
    diversity: float          # fração de indivíduos distintos
    best_distance_km: float
    best_feasible: bool
    best_violations: int
    elapsed_s: float


@dataclass
class Snapshot:
    """Fotografia do melhor indivíduo (para animação da evolução)."""

    generation: int
    fitness: float
    distance_km: float
    routes: list[list[int]]


@dataclass
class GAResult:
    best_routes: list[list[int]]
    best_chromosome: list[int]
    best_fitness: float
    evaluation: Evaluation
    history: list[GenerationStats]
    snapshots: list[Snapshot]
    runtime_s: float
    evaluations: int
    generations_run: int
    stop_reason: str
    config: GAConfig
    fitness_before_polish: float = math.nan

    @property
    def history_dicts(self) -> list[dict]:
        return [asdict(h) for h in self.history]


Callback = Callable[[GenerationStats, list[list[int]]], "bool | None"]


class GeneticAlgorithm:
    """GA para o VRP hospitalar.

    Exemplo
    -------
    >>> from medroute.scenario import default_scenario
    >>> from medroute.problem import Problem
    >>> ga = GeneticAlgorithm(Problem(default_scenario()), GAConfig(generations=50))
    >>> resultado = ga.run()            # doctest: +SKIP
    """

    def __init__(self, problem: Problem, config: GAConfig | None = None,
                 callback: Callback | None = None) -> None:
        self.problem = problem
        self.cfg = config or GAConfig()
        self.callback = callback
        self._cache: dict[tuple[int, ...], float] = {}
        self.evaluations = 0
        self.selector = ops.make_selector(self.cfg.selection, k=self.cfg.tournament_k)
        self._cx = self._operadores_crossover()
        self._mut = self._operadores_mutacao()

    # ------------------------------------------------------------ operadores
    def _operadores_crossover(self) -> tuple[list[str], list[float]]:
        if self.cfg.crossover == "mix":
            nomes = list(self.cfg.crossover_mix)
            return nomes, [self.cfg.crossover_mix[n] for n in nomes]
        if self.cfg.crossover not in ops.CROSSOVERS:
            raise ValueError(f"crossover desconhecido: {self.cfg.crossover}")
        return [self.cfg.crossover], [1.0]

    def _operadores_mutacao(self) -> tuple[list[str], list[float]]:
        if self.cfg.mutation == "mix":
            nomes = list(self.cfg.mutation_mix)
            return nomes, [self.cfg.mutation_mix[n] for n in nomes]
        if self.cfg.mutation not in ops.MUTATIONS:
            raise ValueError(f"mutação desconhecida: {self.cfg.mutation}")
        return [self.cfg.mutation], [1.0]

    def _crossover(self, p1: list[int], p2: list[int], rng: random.Random) -> list[int]:
        nome = rng.choices(self._cx[0], weights=self._cx[1], k=1)[0]
        fn = ops.CROSSOVERS[nome]
        if nome in ops.PRECISA_PROBLEMA:
            return fn(p1, p2, rng, self.problem)
        return fn(p1, p2, rng)

    def _mutate(self, ch: list[int], rng: random.Random) -> list[int]:
        nome = rng.choices(self._mut[0], weights=self._mut[1], k=1)[0]
        fn = ops.MUTATIONS[nome]
        if nome in ops.MUTACAO_PRECISA_PROBLEMA:
            return fn(ch, rng, self.problem)
        return fn(ch, rng)

    # ---------------------------------------------------------------- fitness
    def fitness(self, ch: list[int]) -> float:
        chave = tuple(ch)
        f = self._cache.get(chave)
        if f is None:
            f = self.problem.fitness(ch)
            self.evaluations += 1
            if len(self._cache) > 400_000:
                self._cache.clear()
            self._cache[chave] = f
        return f

    # ------------------------------------------------------- população inicial
    def _sementes_heuristicas(self) -> list[list[int]]:
        from ..baselines import clarke_wright, nearest_neighbor, sweep

        p = self.problem
        solucoes = [
            nearest_neighbor(p),
            nearest_neighbor(p, priority_first=True),
            sweep(p, rotacoes=8),
            clarke_wright(p),
        ]
        return [normalize_separators(p.encode(s), p.n) for s in solucoes]

    def _populacao_inicial(self, rng: random.Random) -> list[list[int]]:
        P = self.cfg.population_size
        pop: list[list[int]] = []
        if self.cfg.heuristic_seeds:
            sementes = self._sementes_heuristicas()
            pop.extend(sementes)
            # Variações das sementes: ~15% da população no total.
            alvo = max(len(sementes), int(0.15 * P))
            while len(pop) < alvo:
                filho = list(rng.choice(sementes))
                for _ in range(rng.randint(1, 3)):
                    filho = self._mutate(filho, rng)
                pop.append(normalize_separators(filho, self.problem.n))
        while len(pop) < P:
            pop.append(normalize_separators(random_chromosome(self.problem, rng), self.problem.n))
        return pop[:P]

    # ------------------------------------------------------------- busca local
    def _polir(self, ch: list[int], completo: bool) -> list[int]:
        p = self.problem
        rotas = p.decode(ch)
        if completo:
            rotas = improve_solution(p, rotas, rounds=2)
        else:
            rotas = [two_opt_route(p, v, r, max_passes=10) for v, r in enumerate(rotas)]
        return normalize_separators(p.encode(rotas), p.n)

    # ------------------------------------------------------------------ laço
    def run(self) -> GAResult:
        cfg = self.cfg
        p = self.problem
        rng = random.Random(cfg.seed)
        t0 = time.perf_counter()

        pop = self._populacao_inicial(rng)
        fits = [self.fitness(c) for c in pop]

        historico: list[GenerationStats] = []
        snapshots: list[Snapshot] = []
        melhor_ch: list[int] = list(pop[0])
        melhor_f = math.inf
        melhor_eval: Evaluation | None = None
        sem_melhora = 0
        motivo = "gerações esgotadas"
        geracao = -1

        for geracao in range(cfg.generations):
            ordem = sorted(range(len(pop)), key=fits.__getitem__)
            pop = [pop[i] for i in ordem]
            fits = [fits[i] for i in ordem]

            # Memético: 2-opt frequente, relocate completo de tempos em tempos.
            if cfg.local_search and geracao % cfg.local_search_every == 0:
                completo = geracao % cfg.relocate_every == 0
                polido = self._polir(pop[0], completo)
                f_polido = self.fitness(polido)
                if f_polido < fits[0] - 1e-9:
                    pop[0], fits[0] = polido, f_polido

            if fits[0] < melhor_f - 1e-9:
                melhor_f = fits[0]
                melhor_ch = list(pop[0])
                melhor_eval = p.evaluate_chromosome(melhor_ch)
                snapshots.append(Snapshot(geracao, melhor_f, melhor_eval.distance_km,
                                          melhor_eval.as_routes()))
                sem_melhora = 0
            else:
                sem_melhora += 1
            assert melhor_eval is not None

            stats = GenerationStats(
                generation=geracao,
                best=melhor_f,
                mean=sum(fits) / len(fits),
                worst=fits[-1],
                diversity=len({tuple(c) for c in pop}) / len(pop),
                best_distance_km=melhor_eval.distance_km,
                best_feasible=melhor_eval.feasible,
                best_violations=melhor_eval.n_violations,
                elapsed_s=time.perf_counter() - t0,
            )
            historico.append(stats)

            if self.callback is not None and self.callback(stats, melhor_eval.as_routes()) is False:
                motivo = "interrompido pelo usuário"
                break
            if cfg.patience is not None and sem_melhora >= cfg.patience:
                motivo = f"sem melhora por {cfg.patience} gerações"
                break
            if cfg.time_limit_s is not None and stats.elapsed_s >= cfg.time_limit_s:
                motivo = f"limite de tempo ({cfg.time_limit_s:.0f} s)"
                break
            if geracao == cfg.generations - 1:
                break

            # Imigrantes contra convergência prematura.
            if sem_melhora and sem_melhora % cfg.immigrants_after == 0:
                n_imig = int(cfg.immigrant_fraction * len(pop))
                for j in range(len(pop) - n_imig, len(pop)):
                    if rng.random() < 0.5:
                        novo = random_chromosome(p, rng)
                    else:
                        novo = list(melhor_ch)
                        for _ in range(rng.randint(2, 6)):
                            novo = self._mutate(novo, rng)
                    pop[j] = normalize_separators(novo, p.n)
                    fits[j] = self.fitness(pop[j])

            # Nova geração.
            self.selector.prepare(pop, fits)
            nova = [list(c) for c in pop[:cfg.elitism]]
            vistos = {tuple(c) for c in nova}
            while len(nova) < cfg.population_size:
                pai1 = self.selector.select(rng)
                pai2 = self.selector.select(rng)
                if rng.random() < cfg.crossover_rate:
                    filho = self._crossover(pai1, pai2, rng)
                else:
                    filho = list(pai1)
                if rng.random() < cfg.mutation_rate:
                    filho = self._mutate(filho, rng)
                filho = normalize_separators(filho, p.n)
                if tuple(filho) in vistos:
                    filho = normalize_separators(self._mutate(filho, rng), p.n)
                vistos.add(tuple(filho))
                nova.append(filho)
            pop = nova
            fits = [self.fitness(c) for c in pop]

        f_antes = melhor_f
        if cfg.final_polish:
            polido = self._polir(melhor_ch, completo=True)
            f_polido = self.fitness(polido)
            if f_polido < melhor_f - 1e-9:
                melhor_ch, melhor_f = polido, f_polido
                ev = p.evaluate_chromosome(melhor_ch)
                snapshots.append(Snapshot(max(geracao, 0), melhor_f, ev.distance_km, ev.as_routes()))

        avaliacao = p.evaluate_chromosome(melhor_ch)
        return GAResult(
            best_routes=avaliacao.as_routes(),
            best_chromosome=melhor_ch,
            best_fitness=melhor_f,
            evaluation=avaliacao,
            history=historico,
            snapshots=snapshots,
            runtime_s=time.perf_counter() - t0,
            evaluations=self.evaluations,
            generations_run=len(historico),
            stop_reason=motivo,
            config=cfg,
            fitness_before_polish=f_antes,
        )


def solve(scenario: Scenario, config: GAConfig | None = None,
          weights: FitnessWeights | None = None,
          callback: Callback | None = None) -> tuple[Problem, GAResult]:
    """Atalho: compila o cenário e roda o GA."""
    problema = Problem(scenario, weights)
    return problema, GeneticAlgorithm(problema, config, callback).run()
