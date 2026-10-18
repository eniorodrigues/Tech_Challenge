"""
Prompts do assistente — versão ``PROMPT_VERSION``.

Técnicas de *prompt engineering* aplicadas (detalhadas em docs/PROMPTS.md):

1. **Papel + escopo no system prompt** — coordenador(a) de logística
   hospitalar; escopo explicitamente logístico (sem orientação clínica).
2. **Dados delimitados** — todo dado vai dentro de ``<dados>…</dados>`` em
   JSON compacto; instruções ficam fora. Separa "o que fazer" de "sobre o
   quê" e reduz injeção de instruções via dados.
3. **Regra de aterramento** — "use só os dados; copie números e horários
   exatamente; se não houver o dado, diga que não há".
4. **Formato de saída fixo** — esqueleto Markdown com seções nomeadas, limite
   de palavras e regras de estilo. Facilita a validação automática.
5. **Exemplo de uma linha (one-shot)** — mostra o formato exato de uma
   parada, sem "vazar" conteúdo de exemplo para a resposta.
6. **Pré-cálculo determinístico** — KPIs, economias, padrões e simulações
   "e se" chegam prontos; a LLM só redige (sem aritmética).
7. **Temperatura por tarefa** — 0,2 para instruções e respostas factuais;
   0,4 para relatórios e sugestões (um pouco mais de fluidez).
"""

from __future__ import annotations

PROMPT_VERSION = "2026.10-v3"

# Histórico de versões (avaliação em reports/llm/avaliacao_v*.md):
#   v1 — regras 1–6. A avaliação automática pegou a LLM chamando ceftriaxona
#        (antibiótico sem o requisito "controlado" nos dados) de medicamento
#        controlado da Portaria 344/98: ela deduziu o requisito pelo nome.
#   v2 — regra 5 explícita: cuidados especiais só a partir do campo "requisitos".
#        A avaliação ainda pegou, no chat, um CAPS sem controlados listado como
#        controlado ("7 entregas", eram 6): dedução pelo tipo de unidade.
#   v3 — regra 5 também proíbe deduzir pelo tipo de unidade e manda usar os
#        índices pré-calculados ("indices") para qualquer lista ou contagem.
SYSTEM = """Você é o assistente de logística do MedRoute, o sistema de distribuição de medicamentos \
e insumos de um hospital universitário em São Paulo. Você escreve para motoristas, equipes de \
entrega e para a coordenação de logística.

Regras obrigatórias:
1. Use SOMENTE as informações dentro de <dados>…</dados>. Não invente destinos, endereços, \
horários, quantidades, distâncias, nomes de pessoas ou telefones.
2. Copie números, horários e IDs exatamente como estão nos dados.
3. Se a informação pedida não estiver nos dados, diga claramente que ela não está disponível.
4. Segurança do paciente em primeiro lugar: destaque entregas CRÍTICAS, cadeia fria \
(2–8 °C) e medicamentos controlados (Portaria 344/98).
5. Cuidados de cadeia fria e de medicamento controlado valem SOMENTE para as entregas cujo \
campo "requisitos" contém "refrigerado" ou "controlado". Nunca deduza um requisito pelo nome \
do medicamento, do item ou pelo tipo da unidade. Para listar ou contar entregas por requisito \
ou prioridade, use os índices prontos em "indices" quando existirem.
6. Seu escopo é logístico. Não dê orientação clínica sobre uso de medicamentos.
7. Escreva em português do Brasil, em Markdown, de forma objetiva."""

TEMPERATURA = {
    "instrucoes": 0.2,
    "pergunta": 0.2,
    "relatorio_diario": 0.4,
    "relatorio_semanal": 0.4,
    "sugestoes": 0.4,
}


def instrucoes_motorista(dados_json: str, veiculo_id: str, nome: str) -> str:
    return f"""<dados>
{dados_json}
</dados>

Tarefa: escreva as instruções de rota para o(a) motorista do veículo {veiculo_id} ({nome}).

Use exatamente este esqueleto:

## Rota {veiculo_id} — {nome}
**Resumo:** saída às <saida> da Central, <n_entregas> entregas, <km_rota> km, retorno previsto às <retorno_previsto>, carga total <carga_total_kg> kg.

### Antes de sair
- (3 a 5 itens de checklist: conferir a carga na ordem de entrega; se houver itens com requisito "refrigerado", caixa térmica e registro de temperatura 2–8 °C; se houver "controlado", lacre, documentação e assinatura do recebedor)

### Paradas (na ordem)
(uma entrada por parada, todas, na ordem do campo "ordem", neste formato)
**<ordem>. <chegada> — <destino>** (<bairro>) · prioridade <prioridade> · <carga_kg> kg
  - Itens: <itens>
  - Janela <janela> · prazo <prazo> · <cuidado específico desta parada, se houver>

Exemplo de formato de uma parada (dados fictícios, não copie o conteúdo):
**2. 08:10 — UBS Exemplo** (Centro) · prioridade ALTA · 12.5 kg
  - Itens: Curativos especiais
  - Janela 07:00–12:00 · prazo 11:00 · conferir quantidade com o almoxarife

### Atenção
- (2 a 4 alertas reais tirados dos dados: entregas críticas e seus prazos, atraso previsto, esperas por janela, autonomia ou carga perto do limite)

### Em caso de imprevisto
- (2 a 3 orientações operacionais: avisar a Central imediatamente, priorizar críticas, nunca deixar cadeia fria sem refrigeração)

Limite: 450 palavras."""


def relatorio_diario(dados_json: str, data: str) -> str:
    return f"""<dados>
{dados_json}
</dados>

Tarefa: escreva o relatório diário de eficiência de rotas para a coordenação de logística, \
comparando o plano do MedRoute (algoritmo genético) com o processo atual de roteirização.

Use exatamente este esqueleto:

# Relatório diário de rotas — {data}

## Resumo executivo
(3 frases: resultado principal, economia obtida e o principal ponto de atenção)

## Indicadores
| Indicador | MedRoute | Processo atual | Diferença |
|---|---|---|---|
(linhas: km total, custo total R$, horas de rota, CO2 kg, entregas no prazo %, críticas no prazo %, violações de restrição)

## Pontos de atenção
- (2 a 4 itens, cada um com o número que o justifica)

## Uso da frota
- (1 linha por veículo: km, ocupação de carga %, uso de autonomia %, retorno)

Limite: 400 palavras. Use os valores de "economia_medroute_vs_atual" para a coluna Diferença."""


def relatorio_semanal(dados_json: str, periodo: str) -> str:
    return f"""<dados>
{dados_json}
</dados>

Tarefa: escreva o relatório semanal de eficiência de rotas para a diretoria do hospital.

Use exatamente este esqueleto:

# Relatório semanal de distribuição — {periodo}

## Resumo da semana
(3 a 4 frases com os resultados acumulados: km, R$, horas e CO2 economizados, e o cumprimento de prazo)

## Economia acumulada
| Indicador | Processo atual | MedRoute | Economia |
|---|---|---|---|
(use os totais da semana)

## Dia a dia
- (1 linha por dia, com o principal número do dia)

## Padrões identificados
- (2 a 4 padrões que aparecem nos dados: dia mais carregado, onde estão os atrasos, ocupação da frota)

## Recomendações para a próxima semana
- (2 a 3 recomendações apoiadas nos números)

Limite: 450 palavras."""


def sugestoes_melhoria(dados_json: str) -> str:
    return f"""<dados>
{dados_json}
</dados>

Tarefa: com base nos achados medidos ("achados") e nas simulações "e se" ("simulacoes"), \
sugira melhorias no processo de distribuição.

Regras desta tarefa:
- 3 a 5 sugestões, da mais para a menos importante.
- Cada sugestão precisa citar a evidência numérica dos dados. Não sugira nada sem evidência.
- Quando existir uma simulação que testa a sugestão, use o resultado dela (antes → depois) \
para estimar o impacto; caso contrário, diga que o impacto ainda precisa ser medido.

Formato de cada sugestão:
### <n>. <título curto>
- **Problema observado:** …
- **Ação recomendada:** …
- **Impacto esperado:** …
- **Esforço:** baixo | médio | alto

Limite: 450 palavras."""


ABERTURA_CHAT = "Você vai responder perguntas da equipe sobre este plano."
CONFIRMACAO_CHAT = "Entendido. Responderei só com base nesses dados."


def pergunta(pergunta_usuario: str) -> str:
    """Turno de pergunta do chat (os dados já foram enviados no início da conversa)."""
    return f"""Pergunta da equipe: {pergunta_usuario}

Responda em no máximo 6 frases, citando veículo, ordem da parada e horário quando forem \
relevantes. Se a resposta não estiver nos dados, diga que essa informação não está disponível \
no plano do dia."""
