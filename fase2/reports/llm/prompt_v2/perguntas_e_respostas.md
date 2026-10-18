# Perguntas em linguagem natural sobre o plano do dia

**Pergunta:** Qual veículo leva a insulina do paciente PD-05 e a que horas chega?

**Resposta** (llm, nvidia/nemotron-3-ultra-550b-a55b:free; fidelidade 100.0/100):

A insulina do paciente PD-05 (Jabaquara) é transportada pela **Moto 01 (baú térmico) – V4**, na **parada de ordem 3**. A chegada prevista é **09:03**, com **atraso previsto de 2 minutos** em relação ao prazo das 09:00. A entrega tem prioridade **CRÍTICA** e exige **cadeia fria (refrigerado)**.

---

**Pergunta:** Alguma entrega crítica corre risco de atraso? O que fazer?

**Resposta** (llm, nvidia/nemotron-3-ultra-550b-a55b:free; fidelidade 100.0/100):

Sim. A entrega **E25** (Paciente PD-05, Jabaquara – insulina cadeia fria, prioridade CRÍTICA) na **Moto 01 (V4), ordem 3**, tem **chegada prevista 09:03** com **atraso previsto de 2 min** (prazo 09:00).  
No consolidado do turno há **1 entrega crítica atrasada** (maior atraso 2,5 min) e **87,5 %** das críticas no prazo.  
**Ação imediata:** monitorar o motoboy da V4 em tempo real; se o atraso se confirmar, acionar veículo de apoio (van refrigerada ou outra moto com baú térmico) para assumir a carga e garantir a janela 07:00–12:00.  
Comunicar a Central e ao paciente/família o novo horário estimado.  
Verificar se as demais críticas (E02, E01, E11, E28, E31, E22, E34) mantêm horários — todas chegam antes dos respectivos prazos no plano atual.

---

**Pergunta:** Quais entregas de medicamentos controlados existem hoje e em quais veículos?

**Resposta** (llm, nvidia/nemotron-3-ultra-550b-a55b:free; fidelidade 100.0/100):

Há **7 entregas com requisito "controlado" (Portaria 344/98)** distribuídas em **2 veículos**:

**Van Refrigerada 01 (V1)**  
- Ordem 6 – E24 – Paciente PD-04 (Perdizes) – Morfina e fentanil – chegada **10:24**  
- Ordem 7 – E10 – UPA Lapa – Morfina e fentanil – chegada **10:47**

**Van 02 – cofre (V2)**  
- Ordem 1 – E09 – UPA Moema – Morfina e fentanil – chegada **07:18**  
- Ordem 5 – E23 – Paciente PD-03 (Ipiranga) – Morfina e fentanil – chegada **09:03**  
- Ordem 6 – E20 – CAPS Vila Prudente – Clonazepam e haloperidol – chegada **09:29**  
- Ordem 7 – E18 – CAPS Carrão – Clonazepam e haloperidol – chegada **09:57**  
- Ordem 19 – E19 – CAPS Barra Funda – Anti-hipertensivos e hipoglicemiantes de uso contínuo · Luvas, seringas e gaze – chegada **08:39** (veículo **Moto 02 – V5**, ordem 3)  

Todas essas paradas exigem custódia de controlados conforme Portaria 344/98.

---

**Pergunta:** Qual é o telefone do paciente PD-08?

**Resposta** (llm, nvidia/nemotron-3-ultra-550b-a55b:free; fidelidade 100.0/100):

Essa informação não está disponível no plano do dia. Os dados contêm apenas ID, endereço, bairro, prioridade, janela, horários, itens e requisitos da entrega E28 (Paciente PD-08, Lapa, CRÍTICA, insulina cadeia fria, V4 ordem 1, chegada 07:15), mas não incluem telefone de contato.
