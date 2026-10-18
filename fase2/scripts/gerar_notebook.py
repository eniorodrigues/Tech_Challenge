"""
Gera e executa o notebook de demonstração ``notebooks/demo_medroute.ipynb``.

    python scripts/gerar_notebook.py            # cria + executa (salva com as saídas)
    python scripts/gerar_notebook.py --so-criar

O notebook usa o mesmo cenário e a mesma configuração do pipeline
(``python main.py``), então as respostas da LLM vêm do cache — rodar o
notebook não gasta cota da OpenRouter.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat as nbf

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "notebooks" / "demo_medroute.ipynb"


def md(texto: str):
    return nbf.v4.new_markdown_cell(texto.strip())


def code(texto: str):
    return nbf.v4.new_code_cell(texto.strip())


CELULAS = [
    md("""
# MedRoute — demonstração narrada
**Tech Challenge · Fase 2 · Projeto 2 — Otimização de rotas para distribuição de medicamentos e insumos**

Este notebook percorre a solução de ponta a ponta:

1. o cenário do dia (entregas, prioridades, frota e restrições);
2. o ponto de partida — o algoritmo genético do **código base** de TSP — e por que ele não basta;
3. o **algoritmo genético do MedRoute** (representação, fitness, operadores) rodando no cenário;
4. as rotas otimizadas no **mapa**, na linha do tempo e na ocupação da frota;
5. o **comparativo** com outras abordagens de roteamento;
6. a **semana operacional** simulada;
7. a **integração com a LLM**: instruções, relatório, perguntas em linguagem natural e a avaliação
   automática (guardrails).
"""),
    code("""
import sys, json
from pathlib import Path
RAIZ = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(RAIZ / "src"))

import pandas as pd
import matplotlib
matplotlib.use("module://matplotlib_inline.backend_inline")
import matplotlib.pyplot as plt
pd.set_option("display.max_colwidth", 60)

from medroute.scenario import default_scenario
from medroute.problem import Problem
from medroute.ga import GAConfig, GeneticAlgorithm
from medroute.plan import RoutePlan
from medroute.baselines import nearest_neighbor, run_baseline, split_tour_greedy
from medroute.legacy_tsp import run_base_tsp
from medroute.viz import plots, static_map
from medroute.viz.folium_map import build_route_map
print("MedRoute importado de", RAIZ / "src")
"""),
    md("""
## 1. O cenário do dia

Dados **sintéticos e reprodutíveis** (semente 42) sobre a geografia real de São Paulo: 36 entregas
saindo da Central de Abastecimento Farmacêutico do hospital universitário, para UBS, UPA, AME, CAPS,
Hospital Dia e pacientes em atendimento domiciliar (identificados só por código).
"""),
    code("""
sc = default_scenario()
print(sc.description)
entregas = pd.DataFrame([{"id": d.id, "destino": d.name, "tipo": d.kind, "prioridade": d.priority.label,
                          "kg": d.demand_kg, "requisitos": ", ".join(sorted(d.requirements)) or "—",
                          "janela": f"{sc.clock(d.window[0])}–{sc.clock(d.window[1])}", "itens": d.items}
                         for d in sc.deliveries])
entregas.head(12)
"""),
    code("""
print(entregas["prioridade"].value_counts().to_string())
pd.DataFrame([{"veículo": f"{v.id} · {v.name}", "capacidade (kg)": v.capacity_kg, "autonomia (km)": v.range_km,
               "km/h": v.speed_kmh, "R$/km": v.cost_per_km, "recursos": ", ".join(sorted(v.features)) or "—"}
              for v in sc.vehicles])
"""),
    md("""
**Restrições modeladas:** prioridade com prazo (crítica 2 h, alta 4 h), capacidade de carga, autonomia,
múltiplos veículos heterogêneos (VRP), cadeia fria (só V1 e V4), medicamentos controlados da Portaria
344/98 (só V1 e V2, que têm cofre), janelas de recebimento e jornada de 8 h.
"""),
    md("""
## 2. Ponto de partida: o GA do código base

O código base resolve um **TSP**: um único "caixeiro" visita todos os pontos, sem carga, autonomia,
prioridade ou horário. Ele tinha também um bug: `order_crossover(parent1, parent1)` — o pai cruzava com
ele mesmo e não havia recombinação. Abaixo, o GA do base (reproduzido em `legacy_tsp.py`) com e sem a
correção, e o que acontece quando a rota única é fatiada entre os veículos.
"""),
    code("""
problema = Problem(sc)
com_bug = run_base_tsp(problema.dist_np, generations=600, seed=1, fix_crossover_bug=False)
corrigido = run_base_tsp(problema.dist_np, generations=600, seed=1)
print(f"TSP do base como fornecido : {com_bug.best_distance:.1f} km")
print(f"TSP do base corrigido      : {corrigido.best_distance:.1f} km")

tour = [c for c in corrigido.best_tour if c != 0]
fatiado = problema.evaluate(split_tour_greedy(problema, tour))
plano_base = RoutePlan.from_evaluation(problema, fatiado, "TSP do código base + fatiamento")
print(plano_base.summary_text())
"""),
    md("""
A rota única é curta, mas ao dividi-la entre os veículos aparecem **violações**: insulina e vacinas
em veículo sem refrigeração, controlados sem cofre, capacidade estourada — e as entregas críticas
chegam tarde. Daí a necessidade de modelar o problema como **VRP com restrições**.

## 3. O algoritmo genético do MedRoute

* **Cromossomo**: permutação das 36 entregas + 4 separadores (um a menos que o número de veículos);
  o segmento *k* é a rota do veículo *k*.
* **Fitness** (minimizar): km + peso_prioridade × hora de chegada + peso × minutos de atraso +
  penalidades de capacidade, autonomia, compatibilidade e jornada.
* **Operadores**: torneio; OX/PMX/ERX/**BCRC**; swap, inversão, inserção, scramble, **prioridade** e
  **reparo**; elitismo, anti-duplicata, imigrantes; 2-opt/relocate (memético).
"""),
    code("""
from medroute.ga import operators as ops
import random
rng = random.Random(3)
p1 = [1, 2, 3, 4, 5, 6, 7, 8, 9]
p2 = [9, 3, 7, 8, 2, 6, 5, 1, 4]
print("OX  :", ops.order_crossover(p1, p2, rng))
print("PMX :", ops.pmx_crossover(p1, p2, rng))
print("ERX :", ops.edge_recombination(p1, p2, rng))
ch = [1, 2, 3, 4, 5, 6, 7, 8, 9]
print("inversão:", ops.inversion_mutation(ch, rng), "| inserção:", ops.insertion_mutation(ch, rng))
"""),
    code("""
marcos = {0, 5, 10, 25, 50, 100, 200, 300}
def progresso(st, rotas):
    if st.generation in marcos:
        print(f"geração {st.generation:3d} | fitness {st.best:9.1f} | {st.best_distance_km:6.1f} km | "
              f"viável: {st.best_feasible}")

res = GeneticAlgorithm(problema, GAConfig(), callback=progresso).run()   # mesma config do pipeline
plano = RoutePlan.from_evaluation(problema, res.evaluation, "MedRoute (algoritmo genético)", res.runtime_s)
print(f"\\n{res.stop_reason} — {res.generations_run} gerações, {res.evaluations} avaliações, {res.runtime_s:.1f} s\\n")
print(plano.summary_text())
"""),
    code("""
fig = plots.plot_convergence(res.history_dicts)
"""),
    md("""
## 4. As rotas no mapa

Mapa interativo (camada por veículo, número = ordem de visita, forma = prioridade; clique numa parada
para ver itens, janela, prazo e chegada prevista).
"""),
    code("""
build_route_map(plano)
"""),
    code("""
fig = plots.plot_gantt(plano)
fig = plots.plot_utilization(plano)
"""),
    md("""
## 5. Comparativo com outras abordagens

Mesmo cenário e mesma função de avaliação. O "processo atual" é o despachante: atende primeiro as
urgências e, entre elas, a mais próxima.
"""),
    code("""
linhas = []
for nome in ["tsp_base_split", "vizinho_mais_proximo", "despachante_prioridade", "clarke_wright",
             "sweep", "melhoria_local", "simulated_annealing"]:
    r = run_baseline(nome, problema)
    k = RoutePlan.from_evaluation(problema, r.evaluation, r.name, r.runtime_s).kpis
    linhas.append({"metodo": r.name, "km": k.total_km, "no_prazo_pct": k.on_time_pct,
                   "violacoes": k.violations, "fitness": k.fitness, "tempo_s": round(r.runtime_s, 2)})
k = plano.kpis
linhas.append({"metodo": "MedRoute (algoritmo genético)", "km": k.total_km, "no_prazo_pct": k.on_time_pct,
               "violacoes": k.violations, "fitness": k.fitness, "tempo_s": round(res.runtime_s, 2)})
comparativo = pd.DataFrame(linhas).sort_values("fitness")
comparativo
"""),
    code("""
fig = plots.plot_methods_comparison(comparativo, "MedRoute (algoritmo genético)")
"""),
    code("""
atual = RoutePlan.from_evaluation(problema, problema.evaluate(nearest_neighbor(problema, True)),
                                  "Processo atual (despachante)")
pd.Series(plano.compare(atual), name="MedRoute vs processo atual")
"""),
    md("""
O experimento completo — 10 sementes por método, ablação dos operadores, escalabilidade até 90 entregas e
OR-Tools — está em `scripts/run_experiments.py` e no relatório técnico.

## 6. Semana operacional simulada
"""),
    code("""
semana = pd.read_csv(RAIZ / "reports" / "operacao_semanal.csv")
fig = plots.plot_weekly(semana)
semana[["dia", "entregas", "km_atual", "km_ga", "km_economia_pct", "sla_atual", "sla_ga"]]
"""),
    md("""
## 7. Integração com a LLM

`RouteAssistant` recebe o plano e gera os produtos pedidos no enunciado. Modo `auto`: usa a OpenRouter
(Nemotron 3 Ultra, gratuito) e cai para templates offline se faltar chave, rede ou cota. As respostas do
pipeline estão em cache — aqui elas voltam instantaneamente.
"""),
    code("""
from medroute.llm import RouteAssistant
from IPython.display import Markdown, display
assistente = RouteAssistant(plano, atual, mode="auto")

r = assistente.driver_instructions("V4")
print(f"origem: {r.source} | modelo: {r.model} | fidelidade: {r.validation['nota']}/100")
display(Markdown(r.text))
"""),
    code("""
r = assistente.daily_report()
print(f"origem: {r.source} | fidelidade: {r.validation['nota']}/100")
display(Markdown(r.text))
"""),
    code("""
historico = []
for pergunta in ["Qual veículo leva a insulina do paciente PD-05 e a que horas chega?",
                 "Alguma entrega crítica corre risco de atraso? O que fazer?",
                 "Quais entregas de medicamentos controlados existem hoje e em quais veículos?",
                 "Qual é o telefone do paciente PD-08?"]:
    r = assistente.ask(pergunta, historico)
    historico.append((pergunta, r.text))
    display(Markdown(f"**P:** {pergunta}\\n\\n**R** _({r.source}, fidelidade {r.validation['nota']:.0f})_: {r.text}"))
"""),
    md("""
### Avaliação automática (guardrails)

Cada resposta é conferida contra os dados. Abaixo, um texto propositalmente errado: um horário que não
existe, um ID inexistente e um antibiótico tratado como medicamento controlado (o erro real que a
avaliação encontrou na versão 1 do prompt).
"""),
    code("""
from medroute.llm import guardrails
rota = plano.route("V5")
parada = rota.stops[0]
texto_errado = (f"### Paradas\\n**1. {parada.arrival} — {parada.name}**\\n"
                f"  - Entrega controlada (Portaria 344/98): colher lacre e assinatura.\\n"
                f"### Atenção\\n- Passar também na E99 às 03:33.\\n")
guardrails.validate_route_text(texto_errado, rota, plano).to_dict()
"""),
    md("""
## Conclusão

* O GA do MedRoute encontra rotas **viáveis** (nenhuma restrição dura violada) que cumprem quase todos os
  prazos, com menos km e menos custo que o processo atual.
* As restrições hospitalares (prioridade, capacidade, autonomia, frota heterogênea, cadeia fria,
  controlados, janelas e jornada) entram na fitness por penalidade e são corrigidas por operadores
  especializados (BCRC, prioridade, reparo).
* A LLM transforma o plano em instruções, relatórios, sugestões e respostas — sempre com os números
  calculados pelo otimizador e com uma nota objetiva de fidelidade aos dados.
"""),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-criar", action="store_true")
    a = ap.parse_args()
    nb = nbf.v4.new_notebook()
    nb.cells = CELULAS
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    if not a.so_criar:
        from nbconvert.preprocessors import ExecutePreprocessor

        ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(
            nb, {"metadata": {"path": str(DESTINO.parent)}})
    nbf.write(nb, DESTINO)
    print(f"notebook: {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
