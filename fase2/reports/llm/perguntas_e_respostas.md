# Perguntas em linguagem natural sobre o plano do dia

**Pergunta:** Qual veículo leva a insulina do paciente PD-05 e a que horas chega?

**Resposta** (cache, nvidia/nemotron-3-ultra-550b-a55b:free; fidelidade 100.0/100):

A insulina do paciente PD-05 (entrega **E25**) é transportada pela **Moto 01 (baú térmico) — V4**, na **3ª parada** da rota.  
A chegada prevista é **09:03**, com **atraso previsto de 2 minutos** em relação ao prazo das 09:00.  
A entrega é **CRÍTICA** e exige **cadeia fria (refrigerado)**.

---

**Pergunta:** Alguma entrega crítica corre risco de atraso? O que fazer?

**Resposta** (cache, nvidia/nemotron-3-ultra-550b-a55b:free; fidelidade 100.0/100):

Sim. A entrega **E25** (Paciente PD-05, Jabaquara) — **CRÍTICA**, **refrigerada** (insulina) — na **Moto 01 (V4), 3ª parada**, tem **chegada prevista 09:03** com **atraso de 2 min** (prazo 09:00).  
No consolidado do turno há **1 entrega atrasada** e **1 crítica atrasada** (maior atraso 2,5 min; horário médio de entrega crítica 08:02).  
**Ação imediata:** monitorar V4 em tempo real; se o atraso aumentar, acionar moto reserva ou redistribuir a carga para veículo refrigerado mais próximo (V1 tem capacidade e recursos).  
Confirmar recebimento da insulina assim que entregue e registrar o desvio no painel MedRoute.

---

**Pergunta:** Quais entregas de medicamentos controlados existem hoje e em quais veículos?

**Resposta** (cache, nvidia/nemotron-3-ultra-550b-a55b:free; fidelidade 100.0/100):

Há **6 entregas com requisito "controlado"** (Portaria 344/98), distribuídas em **2 veículos**:

**V1 — Van Refrigerada 01**  
- 6ª parada: **E24** – Paciente PD-04 (Perdizes) – Morfina e fentanil – chegada **10:24**  
- 7ª parada: **E10** – UPA Lapa – Morfina e fentanil – chegada **10:47**

**V2 — Van 02 (cofre)**  
- 1ª parada: **E09** – UPA Moema – Morfina e fentanil + soro – chegada **07:18**  
- 5ª parada: **E23** – Paciente PD-03 (Ipiranga) – Morfina e fentanil – chegada **09:03**  
- 6ª parada: **E20** – CAPS Vila Prudente – Clonazepam e haloperidol – chegada **09:29**  
- 7ª parada: **E18** – CAPS Carrão – Clonazepam e haloperidol + EPIs – chegada **09:57**

Todos os veículos possuem o recurso **"controlado"** (V1 e V2).

---

**Pergunta:** Qual é o telefone do paciente PD-08?

**Resposta** (cache, nvidia/nemotron-3-ultra-550b-a55b:free; fidelidade 100.0/100):

Essa informação não está disponível no plano do dia.
