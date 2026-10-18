# Engenharia de prompts e avaliação da LLM

Código: [`src/medroute/llm/prompts.py`](../src/medroute/llm/prompts.py) ·
contexto: [`context.py`](../src/medroute/llm/context.py) ·
validação: [`guardrails.py`](../src/medroute/llm/guardrails.py) ·
avaliação: [`scripts/avaliar_llm.py`](../scripts/avaliar_llm.py)

## 1. Modelo e provedor

| Item | Escolha | Motivo |
|---|---|---|
| Provedor | OpenRouter (API compatível com a da OpenAI) | Um só cliente HTTP dá acesso a dezenas de modelos gratuitos e permite trocar de modelo sem mudar código. |
| Modelo principal | `nvidia/nemotron-3-ultra-550b-a55b:free` | Gratuito, contexto de 1 M tokens, melhor português entre os gratuitos testados com a conta do projeto. |
| Fallback | `nvidia/nemotron-3-super-120b-a12b:free` → `openrouter/free` | A conta só libera provedores NVIDIA/Z-AI (Gemma e outros devolveram 404); `openrouter/free` é o roteador de modelos gratuitos. |
| Raciocínio interno | desligado (`reasoning.enabled = false`) | Nos testes, o "pensamento" consumiu ~1.000 tokens, estourou o limite e cortou a resposta no meio. Para *redigir* dados já calculados ele não ajuda. |
| Cota | ~50 requisições gratuitas por dia | Por isso: cache em disco por hash do pedido + modo offline. |

Teste de modelos feito no desenvolvimento (mesmo prompt curto, em pt-BR):

| Modelo | Resultado |
|---|---|
| `google/gemma-4-31b-it:free` | 404 — provedor não liberado na conta |
| `thinkingmachines/inkling:free` | 403 — só disponível para "agentic harnesses" |
| `nvidia/nemotron-3.5-lightning:free` | resposta vazia (tokens gastos em raciocínio) |
| `nvidia/nemotron-3-super-120b-a12b:free` | ok (3–9 s) |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | **ok, texto mais preciso** (12 s) → escolhido |

## 2. Técnicas aplicadas

1. **Papel e escopo no *system prompt*.** O assistente é o "assistente de logística do MedRoute",
   escreve para motoristas e para a coordenação, e o escopo é **logístico** (proibido dar
   orientação clínica).
2. **Dados delimitados.** Todo dado vai entre `<dados>…</dados>`, em JSON compacto com chaves
   em português (`chegada`, `prazo`, `requisitos`...). Instrução fica fora do bloco — separa
   "o que fazer" de "sobre o quê" e dificulta injeção de instruções pelos dados.
3. **Aterramento explícito.** "Use SOMENTE as informações dentro de `<dados>`", "copie números
   e horários exatamente", "se não estiver nos dados, diga que não está disponível".
4. **Pré-cálculo determinístico.** KPIs, economias, padrões ("achados") e simulações "e se" são
   calculados em Python. A LLM não faz conta — só organiza e redige.
5. **Formato de saída fixo.** Cada tarefa tem um esqueleto Markdown com seções nomeadas,
   ordem das paradas, limite de palavras. Facilita a leitura e a validação automática.
6. **Exemplo de uma linha (*one-shot*).** O prompt de instruções mostra o formato de **uma**
   parada com dados fictícios e avisa para não copiar o conteúdo.
7. **Temperatura por tarefa.** 0,2 para instruções e respostas factuais; 0,4 para relatórios
   e sugestões.
8. **Histórico curto no chat.** Os dados vão uma vez no início da conversa; o histórico guarda
   as últimas 3 trocas (economia de tokens, coerência entre perguntas).
9. **Versão do prompt** registrada em cada resposta (`extra.prompt_version`).

### Esqueleto do *system prompt* (v2)

```text
Você é o assistente de logística do MedRoute, o sistema de distribuição de medicamentos
e insumos de um hospital universitário em São Paulo. [...]
Regras obrigatórias:
1. Use SOMENTE as informações dentro de <dados>…</dados>. Não invente destinos, endereços,
   horários, quantidades, distâncias, nomes de pessoas ou telefones.
2. Copie números, horários e IDs exatamente como estão nos dados.
3. Se a informação pedida não estiver nos dados, diga claramente que ela não está disponível.
4. Segurança do paciente em primeiro lugar: destaque entregas CRÍTICAS, cadeia fria
   (2–8 °C) e medicamentos controlados (Portaria 344/98).
5. Cuidados de cadeia fria e de medicamento controlado valem SOMENTE para as entregas cujo
   campo "requisitos" contém "refrigerado" ou "controlado". Nunca deduza um requisito pelo
   nome do medicamento ou do item.                                     ← novo na v2
6. Seu escopo é logístico. Não dê orientação clínica sobre uso de medicamentos.
7. Escreva em português do Brasil, em Markdown, de forma objetiva.
```

## 3. As cinco tarefas

| Tarefa | Entrada (`<dados>`) | Saída pedida | Temp. |
|---|---|---|---|
| Instruções do motorista | rota do veículo: paradas em ordem, horários, janela, prazo, itens, carga, requisitos, esperas, atrasos previstos | resumo · checklist "antes de sair" · paradas · atenção · imprevistos | 0,2 |
| Relatório diário | KPIs do MedRoute × processo atual, economia, frota, atrasos | resumo executivo · tabela de indicadores · pontos de atenção · uso da frota | 0,4 |
| Relatório semanal | 5 dias simulados (atual × GA), totais, dia mais carregado | resumo · economia acumulada · dia a dia · padrões · recomendações | 0,4 |
| Sugestões de melhoria | achados medidos + simulações "e se" (antes → depois) | 3–5 sugestões: problema (com número) · ação · impacto · esforço | 0,4 |
| Perguntas (chat) | plano completo do dia + histórico | até 6 frases, citando veículo, ordem e horário | 0,2 |

As **simulações "e se"** são o que torna as sugestões confiáveis: quando os achados apontam
um gargalo (ex.: uma entrega crítica de cadeia fria atrasada e só dois veículos refrigerados),
o sistema **re-otimiza o dia com a mudança proposta** (ex.: baú térmico também na Moto 02) e
entrega à LLM o efeito medido (críticas no prazo 87,5% → 100%).

## 4. Avaliação da qualidade (guardrails)

Cada resposta é conferida automaticamente contra os dados e recebe uma **nota de fidelidade**
(0–100), exibida no painel, na API e gravada no cabeçalho de cada arquivo em `reports/llm/`.

| Checagem | Penalidade |
|---|---|
| Paradas da rota não citadas (cobertura) | até −40 |
| Paradas fora de ordem | −15 |
| Horários de chegada da rota não citados | até −15 |
| IDs inexistentes (ex.: `E99`) | −10 cada (máx. 3) |
| Horários `HH:MM` que não existem nos dados | −8 cada (máx. 3) |
| **Requisito inventado** (ex.: chamar de "controlado" um item que não é) | −10 cada (máx. 3) |
| Números com unidade (km, kg, R$, %) não rastreáveis aos dados | −2 cada (máx. 5) — é alerta: somas e margens legítimas também caem aqui |

### Iteração v1 → v2 → v3 (a avaliação guiou as mudanças do prompt)

* **v1** — a avaliação encontrou um erro real nas instruções da Moto 02: a LLM chamou
  **ceftriaxona** (antibiótico **sem** o requisito "controlado" nos dados) de "medicamento
  controlado (Portaria 344/98)" e mandou colher lacre e documentação. O conhecimento geral do modelo
  "vazou" sobre os dados. → regra 5: requisitos só a partir do campo `requisitos`.
* **v2** — o erro da ceftriaxona sumiu, mas no chat a LLM listou o **CAPS Barra Funda**
  (anti-hipertensivos, sem controlados) entre as entregas controladas e contou "7" (eram 6): deduziu
  pelo **tipo de unidade** (CAPS costuma receber psicotrópicos). O guardrail ganhou a checagem de
  listas e contagens. → v3: regra 5 também proíbe deduzir pelo tipo de unidade, e o contexto passou
  a trazer **índices pré-calculados** (`entregas_controladas`, `entregas_refrigeradas`,
  `entregas_criticas`, `entregas_com_atraso_previsto`, com total e lista).
* **v3** — nenhum erro factual; o chat responde "Há 6 entregas com requisito controlado" e lista as
  seis corretas.

| Versão | Nota média | Requisitos inventados | Horários/IDs inventados | Saídas |
|---|---|---|---|---|
| v1 | 98,0 | 1 (E22 ceftriaxona) | 0 | [`prompt_v1/`](../reports/llm/prompt_v1/) · [avaliação](../reports/llm/avaliacao_v1.md) |
| v2 | 95,1 | 2 (E19 na lista + contagem 7 ≠ 6) | 1 (08:30) | [`prompt_v2/`](../reports/llm/prompt_v2/) · [avaliação](../reports/llm/avaliacao_v2.md) |
| **v3** | **97,8** | **0** | **0** | [`prompt_v3/`](../reports/llm/prompt_v3/) · [avaliação](../reports/llm/avaliacao_v3.md) |

Todas as versões avaliadas com o **mesmo verificador final** (`scripts/avaliar_llm.py --pasta …`).
As penalidades restantes da v3 são números derivados legítimos (somas e percentuais calculados pela
LLM a partir dos dados), mostrados como alerta. Ressalva: uma geração por versão é uma amostra
pequena — a evidência é qualitativa (cada erro encontrado virou uma regra), não estatística.

O próprio verificador também foi corrigido ao longo do caminho (falsos positivos documentados nos
testes): contagens por veículo ("2 controladas na V1") eram acusadas como contagem total; "(13
paradas) … itens controlados" era lido como "13 controladas"; e "2h20" (duração) era lido como
horário.

### Outro problema real: geração interrompida pelo provedor

Numa das gerações, o provedor gratuito caiu no meio da resposta e a OpenRouter devolveu o texto
parcial com `finish_reason = "error"`. O cliente aceitou o texto e o gravou no cache; o guardrail
acusou (cobertura de 75% das paradas, nota 63,6). Correção: respostas com `finish_reason = "error"`
não são aceitas nem cacheadas — o cliente tenta de novo e, depois, o próximo modelo (teste de
regressão em `tests/test_llm.py`).

### Teste de recusa

A pergunta "Qual é o telefone do paciente PD-08?" (dado que não existe no plano) é feita de
propósito na demonstração. Resposta do modelo: *"Essa informação não está disponível no plano
do dia."* — a regra 3 funcionando.

## 5. Limitações conhecidas

* Os guardrails são **heurísticos** (texto e expressões regulares). Pegam o erro mais perigoso
  (requisito inventado), mas não entendem frases ambíguas — preferem não acusar a acusar errado.
* Modelos gratuitos têm fila: a latência variou de 2 s a 150 s no desenvolvimento. Para uso real,
  um modelo pago (ou local) com SLA de latência é recomendável; o código não muda.
* A cota gratuita (~50 requisições/dia) limita uso interativo intenso; o cache e o modo offline
  mitigam, mas não substituem uma cota paga em produção.
