<!-- gerado por: llm · modelo nvidia/nemotron-3-ultra-550b-a55b:free · fidelidade 82.0/100 -->

### 1. Instalar baú térmico na Moto 02 (V5)
- **Problema observado:** A entrega crítica E25 (Paciente PD-05, Jabaquara) atrasou 2,5 min (início previsto 09:03 vs. prazo 09:00). A frota possui apenas 2 veículos refrigerados (V1 e V4) para atender 6 entregas refrigeradas, todas críticas. V4 opera no limite de autonomia (97,8% — 58,7 de 60 km) e carga (96% — 24 de 25 kg).
- **Ação recomendada:** Equipar a Moto 02 (V5) com baú térmico certificado, criando terceiro veículo refrigerado.
- **Impacto esperado:** Simulação `bau_termico_moto02` projeta: km 253,5 → 218,6 (-13,8%); custo R$ 1.178,08 → R$ 1.100,91 (-6,5%); SLA geral 97,2% → 100%; SLA crítico 87,5% → 100%; atrasos 1 → 0; último retorno 12:43 → 12:40.
- **Esforço:** médio

### 2. Manter a Van Elétrica 03 (V3) na frota ativa
- **Problema observado:** Testar a remoção da V3 degrada todos os indicadores.
- **Ação recomendada:** Não reduzir a frota; manter V3 operacional.
- **Impacto esperado:** Simulação `sem_van_eletrica` mostra: km 253,5 → 275,8 (+8,8%); custo R$ 1.178,08 → R$ 1.308,00 (+11,0%); SLA geral 97,2% → 91,7%; atrasos 1 → 3; violações 0 → 1; último retorno 12:43 → 13:23. A V3 contribui com 40,5 km elétricos (16% do total) e 40,1 kg CO₂ totais.
- **Esforço:** baixo (decisão gerencial)

### 3. Redistribuir entregas refrigeradas para aliviar V4
- **Problema observado:** V4 concentra 6 entregas refrigeradas críticas, atingindo 97,8% da autonomia e 96% da capacidade de carga, sem margem para desvios.
- **Ação recomendada:** Rebalancear rotas no planejador movendo parte das entregas refrigeradas para V1 (Van Refrigerada 01) e, após a melhoria 1, para V5.
- **Impacto esperado:** Redução do risco de falha de cadeia fria e atrasos por estouro de autonomia/carga. Impacto quantitativo depende de nova otimização; não há simulação direta.
- **Esforço:** baixo

### 4. Aproveitar folga de jornada para janelas mais cedo nas críticas
- **Problema observado:** Último retorno às 12:43 com turno até 15:00; 20,9 h de jornada livre somadas. Horário médio de entrega crítica é 08:02, mas E25 iniciou às 09:03.
- **Ação recomendada:** Negociar com solicitantes janelas de entrega crítica mais cedo (ex.: até 08:30) e priorizar sequenciamento no roteirizador.
- **Impacto esperado:** Aumento da margem de segurança para imprevistos. Impacto em SLA e km precisa ser medido em nova simulação.
- **Esforço:** baixo

### 5. Monitorar emissões e custo/km da frota mista
- **Problema observado:** Custo/km total de R$ 4,65 (R$ 1.178,08 / 253,5 km); participação elétrica de 16% (40,5 km).
- **Ação recomendada:** Estabelecer meta mensal de km elétrico ≥ 20% e custo/km ≤ R$ 4,50; acompanhar via dashboard.
- **Impacto esperado:** Redução contínua de custos e CO₂. Impacto exato depende de decisões de frota e roteirização futuras; não há simulação específica.
- **Esforço:** baixo
