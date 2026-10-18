# Código base fornecido (TSP com algoritmo genético)

`codigo_base_tsp/` é o código base entregue com o enunciado da Fase 2
(repositório `genetic_algorithm_tsp`, licença **CC0 1.0** — domínio público),
mantido **sem alterações** para referência e comparação.

O MedRoute parte dele. A tabela mostra o que foi encontrado na análise e onde
cada ponto foi tratado:

| # | Arquivo / linha | Problema no código base | No MedRoute |
|---|---|---|---|
| 1 | `tsp.py:122` | `order_crossover(parent1, parent1)` — o pai cruza com **ele mesmo**; o filho é uma cópia e não há recombinação (o `parent2` sorteado nunca é usado). | Crossover entre os dois pais (`ga/operators.py`). A reprodução fiel em `src/medroute/legacy_tsp.py` mede o efeito: com o bug o TSP termina em **267 km** em média; corrigido, em **221 km** (−17%, 10 sementes — `reports/experimentos/e4_bug_codigo_base.csv`). |
| 2 | `genetic_algorithm.py:119` | Mutação só troca dois genes **vizinhos** (o próprio TODO pede inversão de trechos). | Inversão (2-opt), inserção, swap, scramble + mutações específicas de VRP (prioridade e reparo). |
| 3 | `tsp.py:68` | População inicial só aleatória (TODO pede heurística). | Sementes de vizinho mais próximo, sweep e Clarke & Wright (`ga/engine.py`). |
| 4 | `draw_functions.py:38` | `renderer.tostring_rgb()` foi removido no Matplotlib 3.10 — o visualizador quebra nas versões atuais. | Visualizador pygame reescrito sem essa API (`viz/pygame_viewer.py`). |
| 5 | `draw_functions.py` (`draw_text`) | Usa `np` e `HEIGHT` sem importá-los/defini-los. | Não reaproveitado. |
| 6 | todo o código | Um único "caixeiro", sem carga, autonomia, prioridade, horário ou frota — e distância em **pixels**. | VRP com frota heterogênea, prioridades, capacidade, autonomia, cadeia fria, controlados, janelas e jornada, sobre coordenadas reais (haversine). |
| 7 | `tsp.py` | Seleção: roleta com peso `1/fitness`; a versão em `genetic_algorithm.py` sorteia entre os 10 melhores. | Torneio (padrão), roleta, ranking e truncamento disponíveis; a ablação mostra que o truncamento é o pior (`reports/experimentos/e2_ablacao_resumo.csv`). |

Para rodar o original (abre uma janela pygame):

```bash
cd legacy/codigo_base_tsp
python tsp.py
```
