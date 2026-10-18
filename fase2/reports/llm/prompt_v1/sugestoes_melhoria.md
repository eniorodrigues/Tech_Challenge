<!-- gerado por: llm · modelo nvidia/nemotron-3-ultra-550b-a55b:free · fidelidade 74.0/100 -->

### 1. Instalar baú térmico na Moto 02 (V5)
- **Problema observado:** Apenas 2 veículos (V1 e V4) atendem 6 entregas refrigeradas (todas CRÍTICAS). V4 roda a 98% da autonomia (58,7/60 km) e 96% da carga (24/25 kg), gerando 2,5 min de atraso na entrega E25 (Paciente PD-05, Jabaquara).
- **Ação recomendada:** Equipar V5 (Moto 02) com baú térmico certificado para 2–8 °C, redistribuindo parte das entregas refrigeradas.
- **Impacto esperado:** Simulação `bau_termico_moto02` projeta: **0 atrasos** (antes 1), **100% no prazo** (antes 97,2%), **100% críticas no prazo** (antes 87,5%), –34,9 km, –R$ 77,17, retorno 3 min mais cedo (12:40).
- **Esforço:** médio

### 2. Manter a Van Elétrica 03 (V3) na frota ativa
- **Problema observado:** V3 responde por 16% dos km (40,5/253,5 km) e ajuda a manter emissões em 40,1 kg CO₂.
- **Ação recomendada:** Não reduzir a frota removendo V3; priorizar sua alocação em rotas de maior densidade.
- **Impacto esperado:** Simulação `sem_van_eletrica` mostra que a remoção **aumenta** km para 275,8 (+22,3 km), custo para R$ 1.308,00 (+R$ 129,92), atrasos para 3 (+2), violações para 1 e retorno para 13:23.
- **Esforço:** baixo (decisão gerencial)

### 3. Redistribuir carga e rota do V4 para aliviar gargalo de autonomia e peso
- **Problema observado:** V4 opera no limite: 97,8% da autonomia e 96% da capacidade de carga, concentrando entregas refrigeradas críticas.
- **Ação recomendada:** Com o baú térmico em V5 (Sugestão 1), mover 2–3 entregas refrigeradas leves de V4 para V5; revisar sequenciamento para encurtar percurso.
- **Impacto esperado:** Redução direta de km e tempo em V4, eliminando a causa-raiz do atraso de 2,5 min na E25. Impacto quantificado depende da nova roteirização (a medir).
- **Esforço:** médio

### 4. Aproveitar folga de jornada (20,9 h) para janelas mais cedo em entregas críticas
- **Problema observado:** Último retorno às 12:43 (turno até 15:00); 20,9 h ociosas somadas. Horário médio de entrega crítica é 08:02, mas E25 teve prazo 09:00 e atrasou.
- **Ação recomendada:** Antecipar saídas do CD em 15–30 min nos dias de maior volume crítico; usar folga para absorver imprevistos sem estourar turno.
- **Impacto esperado:** Maior margem para trânsito/imprevistos, protegendo SLA de 87,5% → 100% em críticas. Ganho exato a medir em piloto.
- **Esforço:** baixo

### 5. Monitorar e relatar emissões por veículo como KPI contínuo
- **Problema observado:** Emissão total 40,1 kg CO₂; participação do elétrico (16% dos km) ainda não é meta formal.
- **Ação recomendada:** Incluir "kg CO₂/entrega" e "% km elétrico" no dashboard diário; definir meta trimestral de aumento da parcela elétrica.
- **Impacto esperado:** Visibilidade para decisões de frota (ex.: expansão de elétricos) e ESG. Impacto financeiro/operacional a medir.
- **Esforço:** baixo
