<!-- gerado por: llm · modelo nvidia/nemotron-3-ultra-550b-a55b:free · fidelidade 94.0/100 -->

# Relatório semanal de distribuição — 2026-10-12 a 2026-10-16

## Resumo da semana
Na semana de 2026-10-12 a 2026-10-16, o MedRoute processou 170 entregas (38 críticas) com zero violações de SLA. A otimização de rotas gerou economia acumulada de **318,7 km** (23,9%), **R$ 1.845,24**, **18,8 horas** e **104,4 kg de CO₂**. O cumprimento de prazo (SLA) saltou de 57,6% no processo atual para 98,8% com o MedRoute; nas entregas críticas, a pontualidade subiu de médias entre 30–57% para 85–100% ao longo dos dias.

## Economia acumulada
| Indicador | Processo atual | MedRoute | Economia |
|---|---|---|---|
| Quilometragem (km) | 1.333,4 | 1.014,7 | 318,7 (23,9%) |
| Custo (R$) | 7.396,01 | 5.550,77 | 1.845,24 |
| Horas | 112,2 | 93,4 | 18,8 |
| CO₂ (kg) | 271,5 | 167,1 | 104,4 |

## Dia a dia
- **Segunda (12/10):** 38 entregas (7 críticas) — 25,5% menos km (277,5 → 206,6 km); SLA geral 60,5% → 97,4%; críticas no prazo 57,1% → 85,7%; 5 veículos; GA 6,4 s.
- **Terça (13/10):** 34 entregas (8 críticas) — **maior economia percentual da semana: 29,0%** (284,7 → 202,1 km); custo caiu 28,4% (R$ 1.581,6 → R$ 1.132,8); SLA geral 52,9% → 97,1%; críticas 37,5% → 87,5%; 5 veículos; GA 3,5 s.
- **Quarta (14/10):** 33 entregas (10 críticas) — 25,8% menos km; SLA geral 48,5% → **100%**; críticas no prazo 30% → **100%**; 5 veículos; GA 6,2 s.
- **Quinta (15/10):** 35 entregas (10 críticas) — 22,6% menos km; SLA geral 60% → **100%**; críticas 30% → **100%**; 5 veículos; GA 3,8 s.
- **Sexta (16/10):** 30 entregas (3 críticas) — 14,5% menos km (menor economia % da semana); SLA geral 66,7% → **100%**; críticas **100% → 100%**; frota reduzida a **4 veículos**; GA 2,9 s.

## Padrões identificados
- **Segunda-feira** concentra o maior volume (38 entregas, 7 críticas) e exige 5 veículos; ainda assim, a otimização cortou ~71 km.
- **Terça-feira** apresentou a maior redução percentual de km (29%) e de custo (28,4%), indicando rotas com maior ociosidade no processo atual.
- **Quarta a sexta** atingiram **SLA 100% (geral e críticas)** com o MedRoute, enquanto o processo atual ficou entre 48,5% e 66,7%.
- **Sexta-feira** operou com **4 veículos** (vs. 5 nos demais dias), mantendo 100% de SLA e 14,5% de economia de km, sugerindo folga de capacidade no fim da semana.

## Recomendações para a próxima semana
1. **Manter a escala de 5 veículos de segunda a quinta** e validar a permanência de **4 veículos na sexta**, monitorando eventuais picos de demanda de urgência.
2. **Priorizar a otimização de terças-feiras** como benchmark: a estrutura de entregas desse dia permite ganhos consistentes de ~29% em km e ~28% em custo; replicar padrões de agrupamento e sequenciamento nos demais dias.
3. **Consolidar janelas de entrega críticas nas primeiras horas da manhã** (especialmente segunda a quarta, onde o processo atual teve 30–57% de pontualidade nas críticas) para preservar o SLA 100% observado com o MedRoute.
