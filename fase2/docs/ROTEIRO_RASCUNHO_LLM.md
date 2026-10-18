# Rascunho da narração escrito pela LLM

Modelo: `nvidia/nemotron-3-ultra-550b-a55b:free` (OpenRouter, gratuito). Gerado por `scripts/video/rascunho_llm.py` a partir dos pontos de cada cena em `scripts/video/roteiro.py`. A narração final (`narracao_texto.py`) é a revisão deste rascunho: números conferidos com os resultados e ritmo ajustado para a voz.

## Bloco 1 — Abertura
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b01c01_abertura** — Tech Challenge — Fase 2 (alvo 25 s, 51 palavras)

> Sou Enio Rodrigues. Este é o Tech Challenge da Fase 2, Projeto 2. O problema: distribuir medicamentos e insumos do hospital universitário para unidades de saúde e pacientes em atendimento domiciliar. A solução combina algoritmo genético para as rotas com modelo de linguagem para instruções, relatórios e respostas em linguagem natural.

**b01c02_visao** — Visão geral da solução (alvo 25 s, 60 palavras)

> O pacote Python se chama medroute. A entrada traz o cenário do dia, regras de negócio e distâncias. A otimização usa função fitness, algoritmo genético e abordagens de comparação. As saídas entregam plano com indicadores, mapas, modelo de linguagem via OpenRouter e as interfaces: linha de comando, API REST, painel Streamlit, notebook e o visualizador pygame herdado do código base.

## Bloco 2 — O problema
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b02c01_cenario** — O cenário do dia (alvo 25 s, 72 palavras)

> Dados sintéticos e reprodutíveis com semente quarenta e dois sobre a geografia real de São Paulo. Trinta e seis entregas para UBS, UPA, AME, CAPS, Hospital Dia e dezesseis pacientes em atendimento domiciliar, identificados só por código. Mil cento e cinquenta e seis quilos; oito entregas críticas, dezesseis altas e doze normais. Seis exigem cadeia fria e seis são medicamentos controlados da Portaria trezentos e quarenta e quatro de noventa e oito.

**b02c02_restricoes** — Frota e restrições modeladas (alvo 25 s, 75 palavras)

> Frota heterogênea de cinco veículos; a van elétrica tem setenta quilômetros de autonomia e as motos carregam vinte e cinco quilos. Prioridade com prazo: crítica até duas horas após a saída, alta até quatro horas. Cadeia fria só nos veículos V1 e V4; controlados só em V1 e V2 com cofre. Janelas de recebimento e jornada de oito horas. A tensão: oito críticas espalhadas pela cidade, prazo de duas horas e só dois veículos refrigerados.

## Bloco 3 — Ponto de partida: o código base
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b03c01_codigo_base** — Código base: o laço evolutivo do tsp.py (alvo 30 s, 69 palavras)

> O código base resolve um TSP: um único caixeiro, distância em pixels, sem nenhuma restrição. Na linha cento e vinte e dois, order_crossover recebe parent1 duas vezes; o pai cruza com ele mesmo, o filho vira cópia e não há recombinação. A linha correta está comentada logo acima. Outros pontos: a mutação só troca vizinhos, a população inicial é só aleatória e o visualizador usa função removida do Matplotlib.

**b03c02_impacto_base** — Partindo do código base (alvo 20 s, 71 palavras)

> Corrigir o crossover reduz o TSP do código base de duzentos e sessenta e sete para duzentos e vinte e um quilômetros em média, dez sementes, menos dezessete por cento. Usar a rota única do TSP e fatiá-la entre os veículos gera sete violações em média e só trinta e um por cento das críticas no prazo. Conclusão: o problema precisa ser modelado como roteamento de veículos com restrições, o VRP.

## Bloco 4 — Representação e função fitness
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b04c01_cromossomo** — Representação genética (alvo 25 s, 67 palavras)

> O cromossomo é uma permutação das trinta e seis entregas intercalada com quatro separadores. Cada trecho entre separadores vira a rota de um veículo. Com um único veículo, volta a ser exatamente o cromossomo do caixeiro viajante do código base. Toda permutação já é uma solução completa e os operadores de permutação continuam valendo. O algoritmo genético decide quantas entregas cada veículo faz apenas movendo os separadores.

**b04c02_fitness** — Função fitness (problem.py) (alvo 30 s, 89 palavras)

> A fitness é minimizada. Soma-se os quilômetros rodados mais o peso da prioridade vezes a hora de chegada: dez para crítica, três para alta, um para normal. Adiciona-se o peso vezes os minutos de atraso em relação ao prazo, considerando o menor entre o fim da janela e o prazo da prioridade. Por fim, entram as penalidades de capacidade, autonomia, compatibilidade e jornada: um custo fixo alto mais um termo proporcional ao excesso. Existe uma versão rápida e uma detalhada da mesma conta e um teste garante que concordam.

## Bloco 5 — Operadores genéticos
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b05c01_ciclo** — O ciclo evolutivo (alvo 25 s, 52 palavras)

> A população inicial mistura indivíduos aleatórios com soluções heurísticas. A seleção é por torneio e o crossover sorteia entre OX, PMX, ERX e BCRC. As mutações são troca, inversão, inserção, embaralhamento, prioridade e reparo. Há elitismo, anti-duplicata e imigrantes quando a população estagna. Busca local dois-opt e relocate roda no melhor indivíduo.

**b05c02_bcrc** — Crossover especializado para VRP: BCRC (alvo 25 s, 47 palavras)

> O BCRC, Best Cost Route Crossover de Ombuki dois mil e seis, herda as rotas do pai um. Retira as entregas de uma rota sorteada do pai dois e reinsere cada uma na posição mais barata, respeitando compatibilidade e carga. Foi o operador mais importante na ablação.

**b05c03_mutacoes** — Mutações especializadas: prioridade e reparo (alvo 20 s, 45 palavras)

> A mutação de prioridade antecipa uma entrega crítica ou alta dentro da rota. A mutação de reparo tira uma entrega de uma rota que viola restrição e a reinsere onde é viável. Por exemplo, insulina numa moto sem baú térmico volta para um veículo refrigerado.

## Bloco 6 — O algoritmo genético em execução
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b06c01_terminal** — python main.py — otimização (alvo 30 s, 69 palavras)

> O pipeline completo roda com python main.py. Geração zero: o melhor indivíduo ainda é inviável. Geração cinco: aparece a primeira solução viável. Geração cem: fitness quinhentos e dois. Para por paciência após trezentas e cinquenta e uma gerações, cerca de trinta e seis mil avaliações e seis segundos. Resultado: duzentos e cinquenta e três vírgula cinco quilômetros, noventa e sete por cento das entregas no prazo e zero violações.

**b06c02_evolucao** — Evolução das rotas geração a geração (alvo 25 s, 37 palavras)

> A animação mostra um algoritmo genético puro partindo de população totalmente aleatória, sem sementes heurísticas. No início as rotas cruzam a cidade e violam restrições. Em poucas dezenas de gerações se organizam por região e ficam viáveis.

**b06c03_convergencia** — Convergência (alvo 15 s, 35 palavras)

> Em escala logarítmica, o melhor indivíduo cai de milhares, que são as penalidades, para cerca de quinhentos em cem gerações. A média da população continua alta de propósito porque crossover e mutação exploram regiões inviáveis.

## Bloco 7 — As rotas otimizadas
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b07c01_painel** — Painel interativo (Streamlit) (alvo 30 s, 83 palavras)

> O painel mostra duzentos e cinquenta e três vírgula cinco quilômetros, quarenta e seis a menos que o processo atual. Custo de mil cento e setenta e oito reais, trezentos e noventa e nove a menos. Noventa e sete por cento das entregas no prazo, trinta e nove pontos a mais, e zero violações. No mapa interativo, cada veículo tem sua camada. A ordem de visita aparece em números, a forma indica a prioridade e a janela traz os detalhes de cada entrega.

**b07c02_gantt** — Linha do tempo dos veículos (alvo 25 s, 76 palavras)

> Na linha do tempo, a van refrigerada V1 entrega as três críticas com vacinas e trombolítico às sete e vinte e cinco, oito e quinze e oito e cinquenta e oito, todas antes do prazo das nove horas. A moto com baú térmico V4 leva três insulinas; a terceira chega às nove e três, dois minutos e meio depois do prazo, o único atraso do dia. Todos os veículos retornam até doze e quarenta e três.

**b07c03_ocupacao** — Ocupação da frota (alvo 15 s, 29 palavras)

> A moto V4 usa noventa e oito por cento da autonomia e noventa e seis por cento da carga, está no limite. As restrições estão ativas, não são decorativas.

## Bloco 8 — Comparativo com outras abordagens
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b08c01_atual** — Processo atual (despachante) (alvo 25 s, 81 palavras)

> O processo atual simulado atende primeiro as urgências e depois o mais próximo. Resultado: duzentos e noventa e nove vírgula cinco quilômetros, mil quinhentos e setenta e sete reais, só cinquenta e oito por cento no prazo e trinta e sete vírgula cinco por cento das críticas no prazo. O último retorno é às catorze e cinquenta e sete. O algoritmo genético economiza quarenta e seis quilômetros, trezentos e noventa e nove reais e quatro horas e dezoito minutos de rota.

**b08c02_comparativo** — 10 abordagens, mesmo cenário, mesma avaliação (alvo 35 s, 101 palavras)

> Dez execuções por método estocástico. O algoritmo genético tem fitness média quinhentos e quatro vírgula sete com desvio de quatro vírgula sete. Simulated Annealing: quinhentos e vinte vírgula sete com desvio de quarenta e oito vírgula cinco, sem diferença estatística na mediana, teste de Mann-Whitney p igual a zero vírgula quarenta e nove, mas o algoritmo genético é dez vezes mais estável. OR-Tools roda duzentos e vinte e cinco quilômetros, mas atende as críticas mais tarde por não modelar o termo de prioridade, fitness quinhentos e dezoito. As heurísticas construtivas e o TSP do código base ficam com atrasos e violações.

**b08c03_ablacao** — Ablação do algoritmo genético (alvo 30 s, 73 palavras)

> Vinte e uma configurações com dez sementes cada. Crossover BCRC: quinhentos e dois; OX: setecentos e cinquenta e quatro; PMX: setecentos e setenta e quatro; ERX: três mil trezentos e dezesseis, o ERX embaralha os separadores e só metade das soluções é viável. Torneio é a melhor seleção; truncamento, a original do código base, é a pior. A configuração do código base nunca chega a uma solução viável, fitness seis mil e treze.

**b08c04_escala** — Escalabilidade (alvo 20 s, 44 palavras)

> De vinte a noventa entregas, algoritmo genético e Simulated Annealing ficam a até três por cento do melhor resultado conhecido; OR-Tools, de três a dezessete por cento no nosso objetivo. O tempo do algoritmo genético cresce até cerca de cinquenta segundos com noventa entregas.

## Bloco 9 — Integração com LLM
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b09c01_fluxo** — Como a LLM foi integrada (alvo 30 s, 82 palavras)

> A integração usa OpenRouter com modelo gratuito Nemotron 3 Ultra da NVIDIA, a conta só libera provedores NVIDIA e Z-AI. A LLM não calcula nada, recebe um JSON com os números prontos. Prompt com papel, regras, dados delimitados, esqueleto de saída e um exemplo; temperatura zero vírgula dois para instruções e zero vírgula quatro para relatórios. Cache em disco por causa da cota de cinquenta requisições por dia, modo offline e guardrails que dão nota de zero a cem a cada resposta.

**b09c02_instrucoes** — Instruções para o motorista da Moto 01 (V4) (alvo 25 s, 37 palavras)

> Instruções geradas para o motorista da moto V4: checklist antes de sair, paradas na ordem com horário, cuidados de cadeia fria, alerta do atraso previsto e o que fazer em caso de imprevisto. Nota de fidelidade: cem.

**b09c03_relatorio** — Relatório diário de eficiência (alvo 20 s, 26 palavras)

> O relatório diário compara o plano com o processo atual numa tabela. Aponta o atraso da entrega E25 e a autonomia da moto V4 no limite.

**b09c04_sugestoes** — Sugestões de melhoria (com simulação “e se”) (alvo 30 s, 79 palavras)

> As sugestões partem de padrões medidos e simulações e se, em que o sistema re-otimiza o dia com a mudança proposta. Instalar baú térmico também na moto zero dois: críticas no prazo de oitenta e sete vírgula cinco por cento para cem por cento, trinta e quatro vírgula nove quilômetros e setenta e sete reais a menos. Operar sem a van elétrica piora: duzentos e setenta e cinco vírgula oito quilômetros, três atrasos e uma violação, manter a van.

**b09c05_chat** — Perguntas em linguagem natural (alvo 30 s, 43 palavras)

> Perguntas sobre as rotas: quem leva a insulina do paciente PD-zero cinco, V4 parada três, nove e três; qual crítica corre risco; quais entregas são controladas. Pergunta-armadilha: o telefone de um paciente, a resposta é que a informação não está disponível no plano.

**b09c06_avaliacao** — Avaliação da qualidade da LLM (alvo 30 s, 71 palavras)

> Cada resposta é conferida contra os dados: cobertura e ordem das paradas, horários e IDs inventados, números não rastreáveis e requisitos inventados. Na versão um, a avaliação pegou a LLM chamando ceftriaxona de medicamento controlado; entrou regra nova no prompt. Na versão dois, pegou um CAPS listado como controlado no chat; entraram índices pré-calculados por requisito. Na versão três, a nota média ficou em noventa e sete vírgula oito de cem.

## Bloco 10 — Semana operacional
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b10c01_semana** — Semana simulada: processo atual × MedRoute (alvo 25 s, 78 palavras)

> Simulei uma semana operacional de segunda a sexta com trinta a trinta e oito entregas por dia. O MedRoute economiza trezentos e dezenove quilômetros, vinte e quatro por cento, mil oitocentos e quarenta e cinco reais, dezoito vírgula oito horas e cento e quatro quilos de CO2. As entregas no prazo sobem de cinquenta e sete vírgula seis por cento para noventa e oito vírgula oito por cento. A LLM escreve o relatório semanal a partir desses totais.

## Bloco 11 — Engenharia
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b11c01_api** — API REST (FastAPI) — documentação automática (alvo 20 s, 30 palavras)

> A API REST com FastAPI traz documentação automática. Os endpoints cobrem otimizar, comparar, mapa, instruções, relatório, sugestões e perguntas. Os endpoints de LLM aceitam os modos auto, LLM e offline.

**b11c02_testes** — python -m pytest -v — 133 testes (alvo 25 s, 49 palavras)

> Cento e trinta e três testes automatizados passando. Cobrem as contas exatas da fitness, a concordância das duas implementações, a validade dos operadores, a regressão do bug do código base, o algoritmo genético, as heurísticas, a LLM com HTTP simulado sem rede, os guardrails, a API e as visualizações.

**b11c03_arvore** — Organização do projeto (alvo 15 s, 35 palavras)

> O pacote source medroute organiza os módulos GA, LLM, viz e API. Scripts de experimentos, avaliação da LLM, diagramas, notebook e vídeo ficam na raiz. Documentação em docs, ambiente virtual e pyproject compatível com Poetry.

## Bloco 12 — Encerramento
_origem: nvidia/nemotron-3-ultra-550b-a55b:free (chamada real)_

**b12c01_resultados** — Resultados (alvo 25 s, 79 palavras)

> Rotas viáveis sem violações e com noventa e sete por cento das entregas no prazo. Quinze por cento a menos de quilômetros e vinte e cinco por cento a menos de custo no dia; vinte e quatro por cento a menos de quilômetros na semana. O algoritmo genético é robusto: quinhentos e quatro vírgula sete mais ou menos quatro vírgula sete em dez execuções. A LLM é auditada automaticamente com nota média noventa e sete vírgula oito de cem.

**b12c02_proximos** — Limitações e próximos passos (alvo 20 s, 55 palavras)

> Limitações: dados sintéticos e distâncias estimadas por haversine vezes um vírgula trinta e cinco. Próximos passos: integrar um roteador real. Uma viagem por veículo: evoluir para múltiplas viagens e reotimização em tempo real. A LLM gratuita tem fila e cota; em produção, modelo pago ou local. Validar com a equipe de logística do hospital. Obrigado.

