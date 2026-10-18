<!-- gerado por: cache · modelo nvidia/nemotron-3-ultra-550b-a55b:free · fidelidade 94.0/100 -->

# Relatório semanal de distribuição — 2026-10-12 a 2026-10-16

## Resumo da semana
Na semana de 12 a 16 de outubro, o MedRoute processou 170 entregas (38 críticas) com zero violações de SLA. A otimização de rotas gerou economia acumulada de 318,7 km (23,9%), R$ 1.845,24, 18,8 horas e 104,4 kg de CO₂. O cumprimento de prazo (SLA) saltou de 57,6% no processo atual para 98,8% com o MedRoute, e as entregas críticas no prazo passaram de médias entre 30% e 57% para 85,7%–100% nos dias otimizados.

## Economia acumulada
| Indicador | Processo atual | MedRoute | Economia |
|---|---|---|---|
| Quilometragem (km) | 1.333,4 | 1.014,7 | 318,7 (23,9%) |
| Custo (R$) | 7.396,01 | 5.550,77 | 1.845,24 |
| Tempo (horas) | 112,2 | 93,4 | 18,8 |
| CO₂ (kg) | 271,5 | 167,1 | 104,4 |

## Dia a dia
- **Segunda (12/10):** 38 entregas (7 críticas); maior volume da semana; economia de 25,5% no km (70,9 km); SLA subiu de 60,5% para 97,4%.
- **Terça (13/10):** 34 entregas (8 críticas); maior economia percentual de km (29,0% / 82,6 km); custo caiu 28,4%; críticas no prazo foram a 87,5%.
- **Quarta (14/10):** 33 entregas (10 críticas, pico da semana); SLA atingiu 100% com MedRoute (era 48,5%); críticas no prazo chegaram a 100%.
- **Quinta (15/10):** 35 entregas (10 críticas); maior km absoluto da semana (315,9 km → 244,5 km); economia de 22,6%; SLA e críticas no prazo em 100%.
- **Sexta (16/10):** 30 entregas (3 críticas); menor volume; frota GA com 4 veículos; economia de 14,5% no km; SLA e críticas no prazo em 100%.

## Padrões identificados
- **Segunda-feira concentra o maior volume** (38 entregas, 277,5 km atuais) e exige 5 veículos na solução otimizada.
- **Quarta e quinta têm mais entregas críticas** (10 cada), e o MedRoute elimina os atrasos: críticas no prazo passam de 30% para 100%.
- **Sexta-feira opera com frota enxuta** (4 veículos GA) e já apresenta bom SLA atual (66,7%), com ganhos marginais de km.
- **Tempo de cálculo do GA** varia de 2,9 s a 6,4 s, compatível com replanejamento intradiário.

## Recomendações para a próxima semana
- **Manter 5 veículos de segunda a quinta** e avaliar 4 na sexta, conforme demanda confirmada na véspera.
- **Priorizar sequenciamento de cargas críticas (refrigeradas/controladas) nas quartas e quintas**, dias de maior concentração, para sustentar 100% de SLA.
- **Automatizar disparo do GA no fechamento do dia anterior** (tempo < 7 s) para capturar janelas de trânsito e reduzir km em ~24% consistentemente.
