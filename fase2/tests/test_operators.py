"""Operadores genéticos: validade das permutações e comportamento específico."""

from __future__ import annotations

import random

import pytest

from medroute.ga import operators as ops
from medroute.ga.local_search import improve_solution, relocate, swap_between, two_opt_route
from medroute.ga.representation import is_valid, normalize_separators, random_chromosome
from medroute.legacy_tsp import _order_crossover


@pytest.mark.parametrize("nome", ["ox", "pmx", "erx", "bcrc"])
def test_crossover_sempre_gera_permutacao_valida(nome, problema_padrao):
    rng = random.Random(42)
    fn = ops.CROSSOVERS[nome]
    for _ in range(150):
        p1 = random_chromosome(problema_padrao, rng)
        p2 = random_chromosome(problema_padrao, rng)
        c1, c2 = list(p1), list(p2)
        filho = fn(p1, p2, rng, problema_padrao) if nome in ops.PRECISA_PROBLEMA else fn(p1, p2, rng)
        assert is_valid(filho, problema_padrao)
        assert p1 == c1 and p2 == c2  # pais intactos


@pytest.mark.parametrize("nome", list(ops.MUTATIONS))
def test_mutacao_sempre_gera_permutacao_valida(nome, problema_padrao):
    rng = random.Random(7)
    fn = ops.MUTATIONS[nome]
    for _ in range(150):
        ch = random_chromosome(problema_padrao, rng)
        copia = list(ch)
        m = fn(ch, rng, problema_padrao) if nome in ops.MUTACAO_PRECISA_PROBLEMA else fn(ch, rng)
        assert is_valid(m, problema_padrao)
        assert ch == copia


def test_ox_preserva_trecho_do_pai1_e_ordem_do_pai2():
    p1 = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    p2 = [9, 3, 7, 8, 2, 6, 5, 1, 4]
    for seed in range(30):
        rng = random.Random(seed)
        filho = ops.order_crossover(p1, p2, rng)
        rng = random.Random(seed)
        a, b = ops._cortes(len(p1), rng)
        assert filho[a:b] == p1[a:b]
        resto = [g for g in filho if g not in p1[a:b]]
        assert resto == [g for g in p2 if g not in p1[a:b]]


def test_bug_do_codigo_base_cruzar_pai_com_ele_mesmo_nao_recombina():
    """Regressão: o tsp.py original chamava order_crossover(parent1, parent1)."""
    rng = random.Random(0)
    pai = [3, 1, 4, 0, 2, 5]
    for _ in range(20):
        assert _order_crossover(pai, pai, rng) == pai          # cópia: sem recombinação
    outro = [5, 4, 3, 2, 1, 0]
    filhos = {tuple(_order_crossover(pai, outro, rng)) for _ in range(50)}
    assert len(filhos) > 1                                     # corrigido: recombina


def test_pmx_preserva_posicoes_do_trecho():
    rng = random.Random(3)
    p1, p2 = [1, 2, 3, 4, 5, 6, 7, 8], [8, 7, 6, 5, 4, 3, 2, 1]
    filho = ops.pmx_crossover(p1, p2, rng)
    assert sorted(filho) == p1


def test_erx_herda_arestas_dos_pais():
    rng = random.Random(1)
    p1, p2 = list(range(1, 11)), [1, 3, 5, 7, 9, 2, 4, 6, 8, 10]
    filho = ops.edge_recombination(p1, p2, rng)
    arestas_pais = set()
    for p in (p1, p2):
        for i in range(len(p)):
            arestas_pais |= {(p[i], p[(i + 1) % len(p)]), (p[(i + 1) % len(p)], p[i])}
    herdadas = sum((filho[i], filho[i + 1]) in arestas_pais for i in range(len(filho) - 1))
    assert herdadas >= len(filho) - 3


def test_insercao_mais_barata_respeita_cadeia_fria(problema_padrao):
    p = problema_padrao
    frias = [i for i in range(1, p.n + 1) if "refrigerado" in p.scenario.deliveries[i - 1].requirements]
    rotas = [[] for _ in range(p.k)]
    for c in frias:
        ops.cheapest_insertion(p, rotas, c)
    for v, r in enumerate(rotas):
        for c in r:
            assert p.compat[v][c], "entrega refrigerada inserida em veículo sem refrigeração"


def test_bcrc_gera_filho_completo_e_sem_incompatibilidade_nova(problema_padrao):
    from medroute.baselines import nearest_neighbor, sweep

    p = problema_padrao
    rng = random.Random(9)
    p1 = p.encode(nearest_neighbor(p))
    p2 = p.encode(sweep(p, rotacoes=4))
    for _ in range(20):
        filho = ops.best_cost_route_crossover(p1, p2, rng, p)
        assert is_valid(filho, p)
        assert p.evaluate_chromosome(filho).routes  # decodifica sem erro


def test_mutacao_de_prioridade_antecipa_entrega_prioritaria(mini):
    rng = random.Random(0)
    ch = [2, 3, 1, 4]          # V1: 2 → 3 → 1(crítica)
    antes = ch.index(1)
    movida = False
    for _ in range(20):
        m = ops.priority_mutation(ch, rng, mini)
        if m != ch:
            movida = True
            alvo = 1 if m.index(1) != antes else 3
            assert m.index(alvo) < ch.index(alvo)
    assert movida


def test_mutacao_de_reparo_remove_incompatibilidade(mini):
    rng = random.Random(0)
    ch = [2, 4, 1, 3]          # V1: [2]   V2 (moto, sem frio): [1, 3] -> insulina na moto
    antes = mini.evaluate_chromosome(ch)
    assert any(r.incompatible for r in antes.routes)
    reparado = ops.repair_mutation(ch, rng, mini)
    depois = mini.evaluate_chromosome(reparado)
    assert sum(r.incompatible for r in depois.routes) < sum(r.incompatible for r in antes.routes)


def test_selecao_por_torneio_e_truncamento():
    pop = [[i] for i in range(10)]
    fits = [float(i) for i in range(10)]           # 0 é o melhor
    rng = random.Random(0)
    freq = {}
    for k in (2, 10):
        t = ops.TournamentSelector(k=k)
        t.prepare(pop, fits)
        freq[k] = sum(t.select(rng) == [0] for _ in range(4000)) / 4000
    # Sorteio com reposição: P(melhor vencer) = 1 - 0,9^k
    assert freq[2] == pytest.approx(1 - 0.9 ** 2, abs=0.03)
    assert freq[10] == pytest.approx(1 - 0.9 ** 10, abs=0.03)
    tr = ops.TruncationSelector(top=3)
    tr.prepare(pop, fits)
    assert all(tr.select(rng)[0] < 3 for _ in range(100))


def test_roleta_favorece_menor_fitness():
    pop = [["bom"], ["ruim"]]
    sel = ops.RouletteSelector()
    sel.prepare(pop, [1.0, 9.0])                      # pesos 1/f: 0,9 x 0,1
    rng = random.Random(0)
    bons = sum(sel.select(rng) == ["bom"] for _ in range(2000))
    assert 1650 < bons < 1950


def test_ranking_requer_ordem_e_favorece_o_topo():
    pop = [[i] for i in range(5)]
    sel = ops.RankSelector(1.9)
    sel.prepare(pop, [1, 2, 3, 4, 5])
    rng = random.Random(1)
    contagem = [0] * 5
    for _ in range(5000):
        contagem[sel.select(rng)[0]] += 1
    assert contagem[0] > contagem[2] > contagem[4]


def test_normalizacao_de_separadores(problema_padrao):
    n = problema_padrao.n
    ch = [n + 3, 1, n + 1, 2, n + 4, n + 2] + list(range(3, n + 1))
    norm = normalize_separators(ch, n)
    assert [g for g in norm if g > n] == [n + 1, n + 2, n + 3, n + 4]
    assert problema_padrao.decode(norm) == problema_padrao.decode(ch)


def test_two_opt_desfaz_cruzamento_e_nunca_piora(problema_padrao):
    rng = random.Random(5)
    p = problema_padrao
    for _ in range(30):
        rotas = p.decode(random_chromosome(p, rng))
        for v, r in enumerate(rotas):
            melhor = two_opt_route(p, v, r)
            assert sorted(melhor) == sorted(r)
            assert p.route_cost(v, melhor) <= p.route_cost(v, r) + 1e-9


def test_buscas_locais_nunca_pioram(problema_padrao):
    rng = random.Random(11)
    p = problema_padrao
    for _ in range(4):
        rotas = p.decode(random_chromosome(p, rng))
        c0 = p.routes_cost(rotas)
        for fn in (relocate, swap_between, improve_solution):
            novo = fn(p, rotas)
            p.check_solution(novo)
            assert p.routes_cost(novo) <= c0 + 1e-9
