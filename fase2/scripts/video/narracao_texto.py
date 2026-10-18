"""
Texto narrado final de cada cena.

Base: rascunho escrito pela LLM gratuita da OpenRouter (Nemotron 3 Ultra) a
partir dos pontos de cada cena — ver ``docs/ROTEIRO_RASCUNHO_LLM.md``.
Revisão: números conferidos com ``reports/``, ritmo e pronúncia ajustados
para a voz sintética (números e siglas por extenso quando a leitura
automática ficaria estranha; sem símbolos como R$, % ou CO2).

``{NOTA_V3}`` e ``{N_TESTES}`` são preenchidos com os resultados reais
(``reports/llm/avaliacao_v3.json`` e a saída capturada do pytest).
"""

NARRACAO: dict[str, str] = {
    # ------------------------------------------------------------------ 1
    "b01c01_abertura": (
        "Olá! Eu sou o Enio Rodrigues, e este é o Tech Challenge da Fase dois. Escolhi o projeto "
        "dois: distribuir medicamentos e insumos de um hospital universitário para as unidades de "
        "saúde e para pacientes em atendimento domiciliar. A solução combina um algoritmo genético, "
        "que planeja as rotas, com um modelo de linguagem, que transforma essas rotas em "
        "instruções, relatórios e respostas para a equipe."
    ),
    "b01c02_visao": (
        "Tudo está num pacote Python chamado Med Route. A entrada é o cenário do dia, com as "
        "regras de negócio e as distâncias. A otimização tem a função fitness, o algoritmo "
        "genético e as abordagens de comparação. Na saída, um plano com indicadores, mapas, a "
        "integração com a LLM pela OpenRouter, e as interfaces: linha de comando, API REST, um "
        "painel em Streamlit, um notebook e o visualizador pygame herdado do código base."
    ),
    # ------------------------------------------------------------------ 2
    "b02c01_cenario": (
        "O cenário é sintético e reprodutível, sobre a geografia real de São Paulo. São trinta e "
        "seis entregas: UBS, UPA, AME, CAPS, Hospital Dia e dezesseis pacientes em casa, "
        "identificados só por código. Somam mil cento e cinquenta e seis quilos. Oito entregas são "
        "críticas, dezesseis são de prioridade alta e doze são normais. Seis exigem cadeia fria, e "
        "seis são medicamentos controlados da Portaria trezentos e quarenta e quatro."
    ),
    "b02c02_restricoes": (
        "A frota tem cinco veículos diferentes: uma van refrigerada, uma van com cofre, uma van "
        "elétrica com setenta quilômetros de autonomia e duas motos que levam vinte e cinco quilos. "
        "Entrega crítica tem prazo de duas horas; alta, de quatro. Cadeia fria só vai nos veículos "
        "V1 e V4, e controlados só em V1 e V2. Ainda há janelas de recebimento e jornada de oito "
        "horas. A tensão está aí: oito críticas espalhadas pela cidade, duas horas de prazo, e só "
        "dois veículos refrigerados."
    ),
    # ------------------------------------------------------------------ 3
    "b03c01_codigo_base": (
        "O ponto de partida foi o código base fornecido. Ele resolve um TSP: um único caixeiro, "
        "distância em pixels e nenhuma restrição. E tem um bug importante, na linha cento e vinte "
        "e dois: o crossover recebe o mesmo pai duas vezes. O filho sai cópia do pai, e não existe "
        "recombinação. A linha correta está comentada logo acima. Além disso, a mutação só troca "
        "vizinhos, a população inicial é só aleatória, e o visualizador usa uma função que saiu do "
        "Matplotlib."
    ),
    "b03c02_impacto_base": (
        "Medi o efeito: só corrigir o crossover leva o TSP do código base de duzentos e sessenta e "
        "sete para duzentos e vinte e um quilômetros, dezessete por cento a menos. Mas fatiar essa "
        "rota única entre os veículos dá sete violações em média, e só trinta e um por cento das "
        "críticas no prazo. Conclusão: era preciso modelar um problema de roteamento de veículos "
        "com restrições, o VRP."
    ),
    # ------------------------------------------------------------------ 4
    "b04c01_cromossomo": (
        "A representação genética é uma permutação das trinta e seis entregas, intercalada com "
        "quatro separadores. Cada trecho entre separadores é a rota de um veículo. Com um veículo "
        "só, é exatamente o cromossomo do código base. Toda permutação é uma solução completa, os "
        "operadores de permutação continuam valendo, e o algoritmo decide quantas entregas cada "
        "veículo faz só movendo os separadores."
    ),
    "b04c02_fitness": (
        "A fitness é um custo a minimizar. Ela soma os quilômetros rodados; o peso da prioridade "
        "vezes a hora de chegada, com peso dez para crítica, três para alta e um para normal; o "
        "peso vezes os minutos de atraso em relação ao prazo; e as penalidades de capacidade, "
        "autonomia, compatibilidade e jornada, com um custo fixo alto mais uma parte proporcional "
        "ao excesso. Existem uma versão rápida e uma detalhada da mesma conta, e um teste garante "
        "que as duas sempre concordam."
    ),
    # ------------------------------------------------------------------ 5
    "b05c01_ciclo": (
        "O ciclo evolutivo começa com indivíduos aleatórios e algumas soluções heurísticas. A "
        "seleção é por torneio, e o crossover é sorteado entre OX, PMX, ERX e BCRC. As mutações "
        "são troca, inversão, inserção, embaralhamento, prioridade e reparo. Há elitismo, "
        "bloqueio de duplicatas e imigrantes quando a população estagna, e uma busca local dois "
        "opt e relocate no melhor indivíduo."
    ),
    "b05c02_bcrc": (
        "O operador mais importante é o BCRC, um crossover feito para roteamento. Ele herda as "
        "rotas do primeiro pai, retira as entregas de uma rota sorteada do segundo pai e reinsere "
        "cada uma na posição mais barata, respeitando a compatibilidade e a carga. Assim o filho "
        "herda um bom agrupamento sem destruir a estrutura do outro pai."
    ),
    "b05c03_mutacoes": (
        "Duas mutações também são específicas do problema. A de prioridade antecipa uma entrega "
        "crítica ou alta dentro da rota. A de reparo tira uma entrega de uma rota que viola "
        "restrição e a reinsere onde é viável. Por exemplo, insulina numa moto sem baú térmico "
        "volta para um veículo refrigerado."
    ),
    # ------------------------------------------------------------------ 6
    "b06c01_terminal": (
        "Aqui está a execução real, com python main ponto py. Na geração zero, o melhor indivíduo "
        "ainda é inviável. Na geração cinco aparece a primeira solução viável, e na geração cem a "
        "fitness chega a quinhentos e dois. O algoritmo para por paciência depois de trezentas e "
        "cinquenta e uma gerações, cerca de trinta e seis mil avaliações, em poucos segundos. "
        "Resultado: duzentos e cinquenta e três vírgula cinco quilômetros, noventa e sete por cento "
        "das entregas no prazo e nenhuma violação."
    ),
    "b06c02_evolucao": (
        "Nesta animação, o algoritmo parte de uma população totalmente aleatória, sem heurísticas. "
        "No começo, as rotas cruzam a cidade de ponta a ponta e violam restrições. Em poucas "
        "dezenas de gerações, elas se organizam por região e ficam viáveis."
    ),
    "b06c03_convergencia": (
        "Na curva de convergência, em escala logarítmica, o melhor indivíduo cai dos milhares, que "
        "são as penalidades, para cerca de quinhentos. A média da população continua alta de "
        "propósito: crossover e mutação seguem explorando."
    ),
    # ------------------------------------------------------------------ 7
    "b07c01_painel": (
        "No painel, o plano do dia: duzentos e cinquenta e três vírgula cinco quilômetros, "
        "quarenta e seis a menos que o processo atual. Custo de mil cento e setenta e oito reais, "
        "trezentos e noventa e nove a menos. Noventa e sete por cento das entregas no prazo, "
        "trinta e nove pontos acima, e nenhuma violação. No mapa, cada veículo é uma camada, o "
        "número é a ordem de visita, a forma indica a prioridade, e cada parada abre os detalhes "
        "da entrega."
    ),
    "b07c02_gantt": (
        "Na linha do tempo, a van refrigerada entrega as três críticas com vacinas e trombolítico "
        "às sete e vinte e cinco, oito e quinze e oito e cinquenta e oito, todas antes do prazo "
        "das nove. A moto com baú térmico leva três insulinas: a terceira chega às nove e três, "
        "dois minutos e meio depois do prazo. É o único atraso do dia. Todos os veículos voltam "
        "até meio-dia e quarenta e três."
    ),
    "b07c03_ocupacao": (
        "A moto V4 usa noventa e oito por cento da autonomia e noventa e seis por cento da carga. "
        "As restrições estão ativas, não são decorativas."
    ),
    # ------------------------------------------------------------------ 8
    "b08c01_atual": (
        "Para comparar, simulei o processo atual: o despachante atende primeiro as urgências e, "
        "depois, sempre a entrega mais próxima. Resultado: duzentos e noventa e nove vírgula cinco "
        "quilômetros, mil quinhentos e setenta e sete reais, só cinquenta e oito por cento das "
        "entregas no prazo, e trinta e sete e meio por cento das críticas. O algoritmo genético "
        "economiza quarenta e seis quilômetros, trezentos e noventa e nove reais e quatro horas e "
        "dezoito minutos de rota."
    ),
    "b08c02_comparativo": (
        "No comparativo, dez abordagens no mesmo cenário, com a mesma avaliação, e dez execuções "
        "para cada método aleatório. O algoritmo genético tem fitness média quinhentos e quatro "
        "vírgula sete, com desvio de quatro vírgula sete. O Simulated Annealing fica em quinhentos "
        "e vinte vírgula sete, com desvio de quarenta e oito: nas medianas não há diferença "
        "estatística, mas o algoritmo genético é dez vezes mais estável. O OR-Tools, do Google, "
        "roda menos quilômetros, duzentos e vinte e cinco, mas entrega as críticas mais tarde, "
        "porque não modela o peso da prioridade. As heurísticas construtivas e o TSP do código "
        "base ficam com atrasos e violações."
    ),
    "b08c03_ablacao": (
        "Na ablação, vinte e uma configurações, com dez sementes cada. O crossover BCRC chega a "
        "quinhentos e dois; OX e PMX ficam perto de setecentos e cinquenta; e o ERX, acima de três "
        "mil, porque embaralha os separadores e só metade das soluções é viável. Torneio é a "
        "melhor seleção, e truncamento, a seleção original do código base, é a pior. A "
        "configuração do código base nunca chega a uma solução viável."
    ),
    "b08c04_escala": (
        "Na escalabilidade, de vinte a noventa entregas, o algoritmo genético e o Simulated "
        "Annealing ficam a no máximo três por cento do melhor resultado conhecido. O tempo do "
        "algoritmo genético cresce até cerca de cinquenta segundos com noventa entregas."
    ),
    # ------------------------------------------------------------------ 9
    "b09c01_fluxo": (
        "Agora, a integração com a LLM. Uso a OpenRouter com um modelo gratuito, o Nemotron três "
        "Ultra, da NVIDIA. A LLM não calcula nada: ela recebe um JSON com os números prontos. O "
        "prompt traz papel, regras, dados delimitados, o esqueleto da resposta e um exemplo, com "
        "temperatura baixa. Há cache em disco, porque a cota gratuita é de cinquenta requisições "
        "por dia, um modo offline, e guardrails que dão uma nota de zero a cem a cada resposta."
    ),
    "b09c02_instrucoes": (
        "Estas são as instruções geradas para o motorista da moto com baú térmico. Primeiro, um "
        "checklist antes de sair, com a caixa térmica e o registro de temperatura. Depois, as "
        "paradas na ordem, com horário, janela e prazo. A instrução avisa do atraso previsto na "
        "terceira insulina e diz o que fazer em caso de imprevisto. Nota de fidelidade: cem."
    ),
    "b09c03_relatorio": (
        "O relatório diário compara o plano com o processo atual numa tabela de indicadores, e "
        "aponta os dois pontos de atenção do dia: o atraso da entrega E vinte e cinco e a "
        "autonomia da moto V4 no limite."
    ),
    "b09c04_sugestoes": (
        "As sugestões de melhoria partem de padrões medidos e de simulações do tipo e se: o "
        "sistema re-otimiza o dia com a mudança proposta antes de sugerir. Instalar um baú "
        "térmico também na moto dois leva as críticas no prazo de oitenta e sete e meio para cem "
        "por cento, com trinta e quatro quilômetros e setenta e sete reais a menos. Já operar sem "
        "a van elétrica piora o dia, com três atrasos e uma violação. Então, ela fica."
    ),
    "b09c05_chat": (
        "A equipe também pode perguntar em linguagem natural. Quem leva a insulina do paciente P "
        "D cinco? A moto V4, na terceira parada, às nove e três. Qual crítica corre risco, e "
        "quais entregas são de medicamentos controlados? E uma pergunta armadilha: o telefone de "
        "um paciente. A resposta correta é que essa informação não está no plano."
    ),
    "b09c06_avaliacao": (
        "E como saber se a LLM está certa? Cada resposta é conferida contra os dados: paradas, "
        "ordem, horários, códigos, números e requisitos. Na versão um do prompt, a avaliação pegou "
        "a LLM chamando um antibiótico de medicamento controlado, e entrou uma regra nova. Na "
        "versão dois, pegou um CAPS listado como controlado, e entraram índices pré-calculados. "
        "Na versão três, nenhum erro factual, e nota média de {NOTA_V3}."
    ),
    # ------------------------------------------------------------------ 10
    "b10c01_semana": (
        "Para o relatório semanal, simulei uma semana de segunda a sexta, de trinta a trinta e "
        "oito entregas por dia. O Med Route economiza trezentos e dezenove quilômetros, vinte e "
        "quatro por cento, mil oitocentos e quarenta e cinco reais, quase dezenove horas de rota e "
        "cento e quatro quilos de CO dois. As entregas no prazo sobem de cinquenta e oito para "
        "noventa e nove por cento."
    ),
    # ------------------------------------------------------------------ 11
    "b11c01_api": (
        "Tudo isso também está numa API REST, com documentação automática: otimizar, comparar, "
        "mapa, instruções, relatório, sugestões e perguntas. Os endpoints da LLM aceitam os modos "
        "automático, LLM e offline."
    ),
    "b11c02_testes": (
        "São {N_TESTES} testes automatizados, todos passando. Eles cobrem as contas exatas da "
        "fitness, a concordância das duas implementações, os operadores, a regressão do bug do "
        "código base, o algoritmo genético, as heurísticas, a LLM com HTTP simulado, sem rede, "
        "os guardrails, a API e as visualizações."
    ),
    "b11c03_arvore": (
        "O projeto é um pacote instalável, com os módulos do algoritmo genético, da LLM, das "
        "visualizações e da API, além dos scripts de experimentos, avaliação, notebook e vídeo, "
        "e da documentação."
    ),
    # ------------------------------------------------------------------ 12
    "b12c01_resultados": (
        "Resumindo: rotas viáveis, sem violações, com noventa e sete por cento das entregas no "
        "prazo. Quinze por cento menos quilômetros e vinte e cinco por cento menos custo no dia, "
        "e vinte e quatro por cento menos quilômetros na semana. Um algoritmo genético robusto, e "
        "uma LLM auditada automaticamente, com nota média de {NOTA_V3}."
    ),
    "b12c02_proximos": (
        "Como limitações, os dados são sintéticos e as distâncias são estimadas; o próximo passo "
        "é integrar um roteador real. Também quero evoluir para várias viagens por veículo e "
        "reotimização em tempo real, usar um modelo pago ou local em produção, e validar tudo "
        "com a equipe de logística do hospital. Obrigado!"
    ),
}
