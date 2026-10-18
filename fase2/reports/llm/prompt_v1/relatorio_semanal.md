<!-- gerado por: llm · modelo nvidia/nemotron-3-ultra-550b-a55b:free · fidelidade 98.0/100 -->

# Relatório semanal de distribuição — 2026-10-12 a 2026-10-16

## Resumo da semana
Na semana de 2026-10-12 a 2026-10-16, foram realizadas 170 entregas, sendo 38 críticas. A otimização via MedRoute (GA) reduziu 318,7 km (23,9%), economizando R$ 1.845,24, 18,8 horas e 104,4 kg de CO₂. O cumprimento de prazo (SLA) saltou de 57,6% para 98,8%, com 100% das entregas críticas no prazo nos últimos três dias e zero violações de janela em ambos os cenários.

## Economia acumulada
| Indicador | Processo atual | MedRoute | Economia |
|---|---|---|---|
| Quilometragem (km) | 1.333,4 | 1.014,7 | 318,7 (23,9%) |
| Custo (R$) | 7.396,01 | 5.550,77 | 1.845,24 |
| Tempo (horas) | 112,2 | 93,4 | 18,8 |
| CO₂ (kg) | 271,5 | 167,1 | 104,4 |
| SLA (%) | 57,6 | 98,8 | +41,2 pp |
| Entregas críticas no prazo (%) | — | 100% (Qua–Sex) | — |

## Dia a dia
- **Segunda (12/10):** 38 entregas (7 críticas); maior volume da semana; economia de 25,5% km; SLA GA 97,4%.
- **Terça (13/10):** 34 entregas (8 críticas); maior economia percentual de km (29,0%); SLA GA 97,1%.
- **Quarta (14/10):** 33 entregas (10 críticas); SLA GA 100% e 100% críticas no prazo; economia 25,8% km.
- **Quinta (15/10):** 35 entregas (10 críticas); maior km absoluto (315,9 → 244,5); SLA GA 100%.
- **Sexta (16/10):** 30 entregas (3 críticas); menor volume; frota GA reduzida a 4 veículos; SLA GA 100%.

## Padrões identificados
- **Segunda-feira** concentra o pico de demanda (38 entregas) e exige 5 veículos no GA.
- **Quarta a Sexta** atingem SLA 100% e 100% de críticas no prazo, indicando estabilização da rota otimizada.
- **Terça-feira** apresenta a melhor relação custo-benefício (maior % de economia de km e custo).
- A frota GA mantém-se em 5 veículos de Segunda a Quinta, caindo para 4 na Sexta, acompanhando a queda de volume.

## Recomendações para a próxima semana
1. **Manter a escala de 5 veículos de Segunda a Quinta** e avaliar redução para 4 na Sexta, replicando o padrão desta semana.
2. **Priorizar o sequenciamento de cargas críticas (cadeia fria e controlados) nas primeiras janelas** de Quarta a Sexta, garantindo a manutenção do SLA 100%.
3. **Investigar a rota de Quinta-feira** (maior km absoluto) para identificar clusters de entrega que possam ser consolidados, visando ampliar a economia de km acima de 25%.
