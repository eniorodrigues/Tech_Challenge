# Roteiro do vídeo de demonstração (até 15 min)

Gerado de `scripts/video/roteiro.py` + `narracao_texto.py` por `scripts/video/exportar_roteiro.py`. O vídeo é montado automaticamente por `python scripts/video/gerar_video.py` (narração pt-BR com edge-tts, telas e saídas reais do sistema). A narração partiu de um rascunho escrito pela LLM gratuita da OpenRouter (`docs/ROTEIRO_RASCUNHO_LLM.md`) e foi revisada.

## 1. Abertura

**[00:00] Tech Challenge — Fase 2** · cartão de título · 22 s

> Olá! Eu sou o Enio Rodrigues, e este é o Tech Challenge da Fase dois. Escolhi o projeto dois: distribuir medicamentos e insumos de um hospital universitário para as unidades de saúde e para pacientes em atendimento domiciliar. A solução combina um algoritmo genético, que planeja as rotas, com um modelo de linguagem, que transforma essas rotas em instruções, relatórios e respostas para a equipe.

**[00:22] Visão geral da solução** · figura — `00_arquitetura.png` · 25 s

> Tudo está num pacote Python chamado Med Route. A entrada é o cenário do dia, com as regras de negócio e as distâncias. A otimização tem a função fitness, o algoritmo genético e as abordagens de comparação. Na saída, um plano com indicadores, mapas, a integração com a LLM pela OpenRouter, e as interfaces: linha de comando, API REST, um painel em Streamlit, um notebook e o visualizador pygame herdado do código base.

## 2. O problema

**[00:47] O cenário do dia** · captura real do sistema — `painel_dados.png` · 25 s

> O cenário é sintético e reprodutível, sobre a geografia real de São Paulo. São trinta e seis entregas: UBS, UPA, AME, CAPS, Hospital Dia e dezesseis pacientes em casa, identificados só por código. Somam mil cento e cinquenta e seis quilos. Oito entregas são críticas, dezesseis são de prioridade alta e doze são normais. Seis exigem cadeia fria, e seis são medicamentos controlados da Portaria trezentos e quarenta e quatro.

**[01:13] Frota e restrições modeladas** · cartão de título · 27 s

> A frota tem cinco veículos diferentes: uma van refrigerada, uma van com cofre, uma van elétrica com setenta quilômetros de autonomia e duas motos que levam vinte e cinco quilos. Entrega crítica tem prazo de duas horas; alta, de quatro. Cadeia fria só vai nos veículos V1 e V4, e controlados só em V1 e V2. Ainda há janelas de recebimento e jornada de oito horas. A tensão está aí: oito críticas espalhadas pela cidade, duas horas de prazo, e só dois veículos refrigerados.

## 3. Ponto de partida: o código base

**[01:41] Código base: o laço evolutivo do tsp.py** · código — `legacy/codigo_base_tsp/tsp.py` · 26 s

> O ponto de partida foi o código base fornecido. Ele resolve um TSP: um único caixeiro, distância em pixels e nenhuma restrição. E tem um bug importante, na linha cento e vinte e dois: o crossover recebe o mesmo pai duas vezes. O filho sai cópia do pai, e não existe recombinação. A linha correta está comentada logo acima. Além disso, a mutação só troca vizinhos, a população inicial é só aleatória, e o visualizador usa uma função que saiu do Matplotlib.

**[02:07] Partindo do código base** · cartão de título · 21 s

> Medi o efeito: só corrigir o crossover leva o TSP do código base de duzentos e sessenta e sete para duzentos e vinte e um quilômetros, dezessete por cento a menos. Mas fatiar essa rota única entre os veículos dá sete violações em média, e só trinta e um por cento das críticas no prazo. Conclusão: era preciso modelar um problema de roteamento de veículos com restrições, o VRP.

## 4. Representação e função fitness

**[02:29] Representação genética** · figura — `00b_cromossomo.png` · 21 s

> A representação genética é uma permutação das trinta e seis entregas, intercalada com quatro separadores. Cada trecho entre separadores é a rota de um veículo. Com um veículo só, é exatamente o cromossomo do código base. Toda permutação é uma solução completa, os operadores de permutação continuam valendo, e o algoritmo decide quantas entregas cada veículo faz só movendo os separadores.

**[02:51] Função fitness (problem.py)** · código — `src/medroute/problem.py` · 27 s

> A fitness é um custo a minimizar. Ela soma os quilômetros rodados; o peso da prioridade vezes a hora de chegada, com peso dez para crítica, três para alta e um para normal; o peso vezes os minutos de atraso em relação ao prazo; e as penalidades de capacidade, autonomia, compatibilidade e jornada, com um custo fixo alto mais uma parte proporcional ao excesso. Existem uma versão rápida e uma detalhada da mesma conta, e um teste garante que as duas sempre concordam.

## 5. Operadores genéticos

**[03:18] O ciclo evolutivo** · figura — `00c_ciclo_ga.png` · 23 s

> O ciclo evolutivo começa com indivíduos aleatórios e algumas soluções heurísticas. A seleção é por torneio, e o crossover é sorteado entre OX, PMX, ERX e BCRC. As mutações são troca, inversão, inserção, embaralhamento, prioridade e reparo. Há elitismo, bloqueio de duplicatas e imigrantes quando a população estagna, e uma busca local dois opt e relocate no melhor indivíduo.

**[03:42] Crossover especializado para VRP: BCRC** · código — `src/medroute/ga/operators.py` · 18 s

> O operador mais importante é o BCRC, um crossover feito para roteamento. Ele herda as rotas do primeiro pai, retira as entregas de uma rota sorteada do segundo pai e reinsere cada uma na posição mais barata, respeitando a compatibilidade e a carga. Assim o filho herda um bom agrupamento sem destruir a estrutura do outro pai.

**[04:00] Mutações especializadas: prioridade e reparo** · código — `src/medroute/ga/operators.py` · 16 s

> Duas mutações também são específicas do problema. A de prioridade antecipa uma entrega crítica ou alta dentro da rota. A de reparo tira uma entrega de uma rota que viola restrição e a reinsere onde é viável. Por exemplo, insulina numa moto sem baú térmico volta para um veículo refrigerado.

## 6. O algoritmo genético em execução

**[04:16] python main.py — otimização** · terminal (saída real) — `terminal_pipeline` · 28 s

> Aqui está a execução real, com python main ponto py. Na geração zero, o melhor indivíduo ainda é inviável. Na geração cinco aparece a primeira solução viável, e na geração cem a fitness chega a quinhentos e dois. O algoritmo para por paciência depois de trezentas e cinquenta e uma gerações, cerca de trinta e seis mil avaliações, em poucos segundos. Resultado: duzentos e cinquenta e três vírgula cinco quilômetros, noventa e sete por cento das entregas no prazo e nenhuma violação.

**[04:44] Evolução das rotas geração a geração** · animação da evolução do GA · 14 s

> Nesta animação, o algoritmo parte de uma população totalmente aleatória, sem heurísticas. No começo, as rotas cruzam a cidade de ponta a ponta e violam restrições. Em poucas dezenas de gerações, elas se organizam por região e ficam viáveis.

**[04:58] Convergência** · figura — `04_convergencia_ga.png` · 12 s

> Na curva de convergência, em escala logarítmica, o melhor indivíduo cai dos milhares, que são as penalidades, para cerca de quinhentos. A média da população continua alta de propósito: crossover e mutação seguem explorando.

## 7. As rotas otimizadas

**[05:10] Painel interativo (Streamlit)** · captura real do sistema — `painel_mapa.png` · 24 s

> No painel, o plano do dia: duzentos e cinquenta e três vírgula cinco quilômetros, quarenta e seis a menos que o processo atual. Custo de mil cento e setenta e oito reais, trezentos e noventa e nove a menos. Noventa e sete por cento das entregas no prazo, trinta e nove pontos acima, e nenhuma violação. No mapa, cada veículo é uma camada, o número é a ordem de visita, a forma indica a prioridade, e cada parada abre os detalhes da entrega.

**[05:35] Linha do tempo dos veículos** · figura — `05_linha_do_tempo_ga.png` · 21 s

> Na linha do tempo, a van refrigerada entrega as três críticas com vacinas e trombolítico às sete e vinte e cinco, oito e quinze e oito e cinquenta e oito, todas antes do prazo das nove. A moto com baú térmico leva três insulinas: a terceira chega às nove e três, dois minutos e meio depois do prazo. É o único atraso do dia. Todos os veículos voltam até meio-dia e quarenta e três.

**[05:57] Ocupação da frota** · figura — `07_ocupacao_frota.png` · 8 s

> A moto V4 usa noventa e oito por cento da autonomia e noventa e seis por cento da carga. As restrições estão ativas, não são decorativas.

## 8. Comparativo com outras abordagens

**[06:06] Processo atual (despachante)** · figura — `02_mapa_rotas_processo_atual.png` · 26 s

> Para comparar, simulei o processo atual: o despachante atende primeiro as urgências e, depois, sempre a entrega mais próxima. Resultado: duzentos e noventa e nove vírgula cinco quilômetros, mil quinhentos e setenta e sete reais, só cinquenta e oito por cento das entregas no prazo, e trinta e sete e meio por cento das críticas. O algoritmo genético economiza quarenta e seis quilômetros, trezentos e noventa e nove reais e quatro horas e dezoito minutos de rota.

**[06:32] 10 abordagens, mesmo cenário, mesma avaliação** · figura — `10_comparativo_metodos.png` · 37 s

> No comparativo, dez abordagens no mesmo cenário, com a mesma avaliação, e dez execuções para cada método aleatório. O algoritmo genético tem fitness média quinhentos e quatro vírgula sete, com desvio de quatro vírgula sete. O Simulated Annealing fica em quinhentos e vinte vírgula sete, com desvio de quarenta e oito: nas medianas não há diferença estatística, mas o algoritmo genético é dez vezes mais estável. O OR-Tools, do Google, roda menos quilômetros, duzentos e vinte e cinco, mas entrega as críticas mais tarde, porque não modela o peso da prioridade. As heurísticas construtivas e o TSP do código base ficam com atrasos e violações.

**[07:10] Ablação do algoritmo genético** · figura — `12_ablacao_ga.png` · 24 s

> Na ablação, vinte e uma configurações, com dez sementes cada. O crossover BCRC chega a quinhentos e dois; OX e PMX ficam perto de setecentos e cinquenta; e o ERX, acima de três mil, porque embaralha os separadores e só metade das soluções é viável. Torneio é a melhor seleção, e truncamento, a seleção original do código base, é a pior. A configuração do código base nunca chega a uma solução viável.

**[07:35] Escalabilidade** · figura — `14_escalabilidade.png` · 13 s

> Na escalabilidade, de vinte a noventa entregas, o algoritmo genético e o Simulated Annealing ficam a no máximo três por cento do melhor resultado conhecido. O tempo do algoritmo genético cresce até cerca de cinquenta segundos com noventa entregas.

## 9. Integração com LLM

**[07:48] Como a LLM foi integrada** · figura — `00d_fluxo_llm.png` · 26 s

> Agora, a integração com a LLM. Uso a OpenRouter com um modelo gratuito, o Nemotron três Ultra, da NVIDIA. A LLM não calcula nada: ela recebe um JSON com os números prontos. O prompt traz papel, regras, dados delimitados, o esqueleto da resposta e um exemplo, com temperatura baixa. Há cache em disco, porque a cota gratuita é de cinquenta requisições por dia, um modo offline, e guardrails que dão uma nota de zero a cem a cada resposta.

**[08:14] Instruções para o motorista da Moto 01 (V4)** · texto gerado pela LLM (rolagem) — `instrucoes_V4.md` · 19 s

> Estas são as instruções geradas para o motorista da moto com baú térmico. Primeiro, um checklist antes de sair, com a caixa térmica e o registro de temperatura. Depois, as paradas na ordem, com horário, janela e prazo. A instrução avisa do atraso previsto na terceira insulina e diz o que fazer em caso de imprevisto. Nota de fidelidade: cem.

**[08:34] Relatório diário no painel (aba Assistente)** · captura real do sistema — `painel_llm.png` · 11 s

> O relatório diário compara o plano com o processo atual numa tabela de indicadores, e aponta os dois pontos de atenção do dia: o atraso da entrega E vinte e cinco e a autonomia da moto V4 no limite.

**[08:45] Sugestões de melhoria (com simulação “e se”)** · texto gerado pela LLM (rolagem) — `sugestoes_melhoria.md` · 24 s

> As sugestões de melhoria partem de padrões medidos e de simulações do tipo e se: o sistema re-otimiza o dia com a mudança proposta antes de sugerir. Instalar um baú térmico também na moto dois leva as críticas no prazo de oitenta e sete e meio para cem por cento, com trinta e quatro quilômetros e setenta e sete reais a menos. Já operar sem a van elétrica piora o dia, com três atrasos e uma violação. Então, ela fica.

**[09:09] Perguntas em linguagem natural** · chat com a LLM — `perguntas_e_respostas.md` · 19 s

> A equipe também pode perguntar em linguagem natural. Quem leva a insulina do paciente P D cinco? A moto V4, na terceira parada, às nove e três. Qual crítica corre risco, e quais entregas são de medicamentos controlados? E uma pergunta armadilha: o telefone de um paciente. A resposta correta é que essa informação não está no plano.

**[09:28] Avaliação da qualidade da LLM** · cartão de título · 25 s

> E como saber se a LLM está certa? Cada resposta é conferida contra os dados: paradas, ordem, horários, códigos, números e requisitos. Na versão um do prompt, a avaliação pegou a LLM chamando um antibiótico de medicamento controlado, e entrou uma regra nova. Na versão dois, pegou um CAPS listado como controlado, e entraram índices pré-calculados. Na versão três, nenhum erro factual, e nota média de noventa e sete vírgula oito.

## 10. Semana operacional

**[09:54] Semana simulada: processo atual × MedRoute** · figura — `09_semana_km.png` · 22 s

> Para o relatório semanal, simulei uma semana de segunda a sexta, de trinta a trinta e oito entregas por dia. O Med Route economiza trezentos e dezenove quilômetros, vinte e quatro por cento, mil oitocentos e quarenta e cinco reais, quase dezenove horas de rota e cento e quatro quilos de CO dois. As entregas no prazo sobem de cinquenta e oito para noventa e nove por cento.

## 11. Engenharia

**[10:17] API REST (FastAPI) — documentação automática** · captura real do sistema — `api_docs.png` · 14 s

> Tudo isso também está numa API REST, com documentação automática: otimizar, comparar, mapa, instruções, relatório, sugestões e perguntas. Os endpoints da LLM aceitam os modos automático, LLM e offline.

**[10:31] python -m pytest -v — 135 testes** · terminal (saída real) — `terminal_pytest` · 20 s

> São cento e trinta e cinco testes automatizados, todos passando. Eles cobrem as contas exatas da fitness, a concordância das duas implementações, os operadores, a regressão do bug do código base, o algoritmo genético, as heurísticas, a LLM com HTTP simulado, sem rede, os guardrails, a API e as visualizações.

**[10:50] Organização do projeto** · árvore do projeto · 12 s

> O projeto é um pacote instalável, com os módulos do algoritmo genético, da LLM, das visualizações e da API, além dos scripts de experimentos, avaliação, notebook e vídeo, e da documentação.

## 12. Encerramento

**[11:03] Resultados** · cartão de título · 20 s

> Resumindo: rotas viáveis, sem violações, com noventa e sete por cento das entregas no prazo. Quinze por cento menos quilômetros e vinte e cinco por cento menos custo no dia, e vinte e quatro por cento menos quilômetros na semana. Um algoritmo genético robusto, e uma LLM auditada automaticamente, com nota média de noventa e sete vírgula oito.

**[11:23] Limitações e próximos passos** · cartão de título · 17 s

> Como limitações, os dados são sintéticos e as distâncias são estimadas; o próximo passo é integrar um roteador real. Também quero evoluir para várias viagens por veículo e reotimização em tempo real, usar um modelo pago ou local em produção, e validar tudo com a equipe de logística do hospital. Obrigado!

## Resumo de tempos

| Bloco | Início | Duração |
|---|---|---|
| 1. Abertura | 00:00 | 00:47 |
| 2. O problema | 00:47 | 00:53 |
| 3. Ponto de partida: o código base | 01:41 | 00:48 |
| 4. Representação e função fitness | 02:29 | 00:48 |
| 5. Operadores genéticos | 03:18 | 00:57 |
| 6. O algoritmo genético em execução | 04:16 | 00:54 |
| 7. As rotas otimizadas | 05:10 | 00:55 |
| 8. Comparativo com outras abordagens | 06:06 | 01:42 |
| 9. Integração com LLM | 07:48 | 02:06 |
| 10. Semana operacional | 09:54 | 00:22 |
| 11. Engenharia | 10:17 | 00:46 |
| 12. Encerramento | 11:03 | 00:37 |

**Total:** 11:41 (medido nos áudios) — limite do enunciado: 15:00.
