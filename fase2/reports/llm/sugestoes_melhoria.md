<!-- gerado por: cache · modelo nvidia/nemotron-3-ultra-550b-a55b:free · fidelidade 90.0/100 -->

### 1. Instalar baú térmico na Moto 02 (V5)
- **Problema observado:** Apenas 2 veículos (V1 e V4) atendem 6 entregas refrigeradas, todas críticas. O V4 opera no limite de autonomia (97,8% — 58,7/60 km) e de carga (96% — 24/25 kg), o que gerou atraso de 2,5 min na entrega crítica E25 (PD-05, Jabaquara).
- **Ação recomendada:** Equipar a Moto 02 (V5) com baú térmico, criando terceiro veículo refrigerado e redistribuindo a carga do V4.
- **Impacto esperado:** Simulação `bau_termico_moto02` projeta: km 253,5 → 218,6 (−13,8%); custo R$ 1.178,08 → R$ 1.100,91 (−6,5%); SLA geral 97,2% → 100%; SLA crítico 87,5% → 100%; atrasos 1 → 0; último retorno 12:43 → 12:40.
- **Esforço:** médio

### 2. Manter a Van Elétrica 03 (V3) na frota ativa
- **Problema observado:** A van elétrica responde por 40,5 km (16% do total) e contribui para emissões totais de 40,1 kg CO₂.
- **Ação recomendada:** Não reduzir a frota removendo a V3.
- **Impacto esperado:** Simulação `sem_van_eletrica` mostra que a remoção elevaria km 253,5 → 275,8 (+8,8%), custo R$ 1.178,08 → R$ 1.308,00 (+11%), SLA geral 97,2% → 91,7%, atrasos 1 → 3 e geraria 1 violação de restrição; último retorno passaria de 12:43 para 13:23.
- **Esforço:** baixo (decisão gerencial)

### 3. Redistribuir carga e rota do V4 para criar margem de segurança
- **Problema observado:** V4 roda 58,7 de 60 km (97,8% da autonomia) e carrega 24 de 25 kg (96%), sem folga para desvios de trânsito ou reentregas.
- **Ação recomendada:** Após instalar o baú térmico no V5 (Sugestão 1), mover parte das entregas refrigeradas do V4 para o V5 e reotimizar a sequência de paradas do V4.
- **Impacto esperado:** Redução da utilização de autonomia e carga do V4 para < 85%, eliminando o risco de novos atrasos críticos. Impacto exato depende da reotimização e precisa ser medido.
- **Esforço:** médio

### 4. Aproveitar a folga de jornada (20,9 h) para janelas de entrega mais amplas
- **Problema observado:** Último retorno às 12:43 com turno até 15:00; 20,9 h de jornada livre somando os veículos.
- **Ação recomendada:** Negociar com a coordenação janelas de entrega mais flexíveis (ex.: até 14:00) para permitir rotas menos apertadas e melhor agrupamento de pedidos.
- **Impacto esperado:** Potencial redução adicional de km e custo, além de maior resiliência a imprevistos. Impacto ainda precisa ser medido via simulação.
- **Esforço:** baixo

### 5. Monitorar e relatar ganhos contínuos vs. processo anterior
- **Problema observado:** O processo otimizado já economiza 46,0 km (15,4%), R$ 399,39 (25,3%), 4,35 h de rota, 18,3 kg CO₂ e evitou 14 atrasos e 38,9 pontos de SLA.
- **Ação recomendada:** Instituir painel mensal comparando métricas atuais vs. baseline histórico para sustentar decisões de frota e investimentos (ex.: baú térmico, veículos elétricos).
- **Impacto esperado:** Visibilidade contínua de performance e base de dados para futuras expansões. Impacto qualitativo; ganhos quantitativos já demonstrados.
- **Esforço:** baixo
