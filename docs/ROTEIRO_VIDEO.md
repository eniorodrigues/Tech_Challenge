# Roteiro do vídeo de demonstração — Tech Challenge Fase 1

**Duração alvo:** 11–13 minutos (limite do enunciado: 15 min)
**Plataforma:** YouTube (público ou **não listado**)
**Formato:** gravação de tela com narração. Câmera é opcional (um quadrinho no
canto ajuda, mas o que vale nota é a tela).

---

## Antes de gravar — checklist

| # | Item | Por quê |
|---|---|---|
| 1 | Rodar `python main.py` **uma vez antes** | as figuras e o CSV de métricas já ficam prontos; na gravação o script roda rápido e sem surpresa |
| 2 | Rodar `python main_vision.py` **uma vez antes** | o `medmnist` baixa o BreastMNIST do Zenodo na primeira execução; você **não** quer esse download no vídeo |
| 3 | Aumentar a fonte do terminal (14–16 pt) e do editor | legibilidade em 1080p |
| 4 | Tema claro no editor e no terminal | contraste melhor na compressão do YouTube |
| 5 | Fechar Slack/WhatsApp/e-mail e silenciar notificações | evita cortes e vazamento de dados pessoais |
| 6 | Abrir de antemão: VS Code na pasta do projeto, 1 terminal, 1 navegador com os 2 notebooks já renderizados | zero tempo morto trocando de janela |
| 7 | Gravar em 1920x1080, 30 fps | padrão, arquivo leve |
| 8 | Testar o microfone com 10 s de gravação | áudio ruim derruba a nota percebida |

**Abas/janelas na ordem de uso:**
1. VS Code — `README.md` aberto
2. VS Code — `src/` (preprocessing.py, modeling.py, evaluation.py, explainability.py, vision.py)
3. Terminal com o `.venv` já ativado
4. Explorador de arquivos em `reports/figures/`
5. Navegador: `notebooks/tech_challenge_breast_cancer.ipynb` e `notebooks/tech_challenge_cnn_imagem.ipynb`

**Comandos que você vai digitar (deixe copiados num bloco de notas):**

```bash
python main.py
```

```bash
python main_vision.py
```

```bash
python -m pytest -v
```

---

## BLOCO 1 — Abertura e problema (0:00 – 0:50)

**TELA:** slide/título simples ou o `README.md` no topo.

**FALA:**
> "Olá! Eu sou o [SEU NOME], e este é o Tech Challenge da Fase 1.
> O desafio é criar a base de um sistema inteligente de suporte ao diagnóstico
> para uma rede de hospitais especializada na saúde da mulher.
> O que eu construí foi um sistema de Machine Learning que classifica tumores
> de mama como **malignos** ou **benignos** a partir de dados de exame — e,
> como item extra, uma **rede neural convolucional** que faz o mesmo
> diagnóstico direto de **imagens de ultrassom**.
> A premissa central do projeto é uma só: o modelo é um **copiloto**. O médico
> tem sempre a palavra final."

---

## BLOCO 2 — Dataset e discussão do problema (0:50 – 2:00)

**TELA:** `README.md`, seção "2. A base de dados". Depois abra
`data/breast_cancer_wisconsin.csv` rapidamente.

**FALA:**
> "A base é a **Breast Cancer Wisconsin Diagnostic**, que é justamente a tarefa
> principal sugerida no enunciado. São **569 pacientes** e **30 features
> numéricas** extraídas de imagens de punção por agulha fina: raio, textura,
> perímetro, área, concavidade — cada uma em três resumos: média, erro-padrão e
> o 'pior' valor observado.
> A distribuição é **357 benignos contra 212 malignos** — 37% de malignos,
> um desbalanceamento moderado que eu trato com estratificação e com pesos de
> classe.
> Uma decisão de projeto importante: o scikit-learn carrega essa base com
> `0 = maligno`. Eu **inverti** o rótulo para que `1 = maligno`, porque assim o
> **recall** passa a significar literalmente 'quantos cânceres eu detectei' —
> que é a métrica que importa clinicamente."

**MOSTRAR:** `src/config.py` — o bloco comentado da convenção de rotulagem.

---

## BLOCO 3 — Tour pela arquitetura do projeto (2:00 – 3:00)

**TELA:** árvore de arquivos do VS Code, expandida.

**FALA:**
> "O projeto está organizado como pacote Python, não como um notebook solto.
> Em `src/` ficam os módulos reutilizáveis: `data_loader` carrega os dados,
> `preprocessing` faz limpeza e split, `eda` gera a análise exploratória,
> `modeling` define os classificadores, `evaluation` calcula as métricas,
> `explainability` faz feature importance e SHAP, e `vision` é o extra da CNN.
> O `main.py` orquestra o pipeline tabular de ponta a ponta e o
> `main_vision.py` orquestra o de imagem.
> Os notebooks em `notebooks/` contam a mesma história de forma narrada, com as
> saídas já salvas. E tem `tests/` com as provas de correção — eu volto nisso
> no final, porque é o que sustenta a credibilidade dos números.
> Tem também um **Dockerfile**, pra quem quiser rodar sem instalar nada."

---

## BLOCO 4 — Análise exploratória (3:00 – 4:30)

**TELA:** notebook `tech_challenge_breast_cancer.ipynb`, seção 3. Role pelas
figuras. Alternativa: abrir os PNGs em `reports/figures/`.

**FALA (figura 01 — balanceamento):**
> "Primeiro o balanceamento: 63% benignos, 37% malignos. Isso já mata a
> accuracy como métrica única — um modelo que chutasse 'benigno' pra todo mundo
> já acertaria 63%."

**FALA (figura 02 — distribuições por classe):**
> "Aqui está o achado mais forte da exploração. Nas seis features mais
> correlacionadas com o diagnóstico — `worst concave points`, `worst perimeter`,
> `worst area`, `worst radius` — as duas classes formam **duas montanhas
> claramente separadas**: o benigno concentrado à esquerda, o maligno deslocado
> para a direita, com uma zona de sobreposição estreita.
> Traduzindo clinicamente: **tumores malignos têm núcleos celulares maiores e
> contornos mais irregulares**. Isso é exatamente o que a literatura médica
> descreve, e é o que explica por que esse problema é tratável com modelos
> relativamente simples."

**FALA (figura 03 — correlação):**
> "A matriz de correlação mostra blocos vermelhos muito fortes. Encontrei
> **21 pares de features com correlação acima de 0,9** — é multicolinearidade
> pesada, e é esperada: `raio`, `perímetro` e `área` são geometricamente a mesma
> informação. Isso não atrapalha árvores nem KNN, mas **espalha os coeficientes**
> da regressão logística entre features redundantes. Guarde isso, porque volta
> na parte de explicabilidade."

---

## BLOCO 5 — Pré-processamento e o anti-vazamento (4:30 – 5:30)

**TELA:** `src/preprocessing.py`, depois `src/modeling.py` (função `build_models`).

**FALA:**
> "O pré-processamento tem três peças: limpeza defensiva — duplicatas e colunas
> vazias; imputação pela **mediana**, que é robusta a outliers; e padronização
> com StandardScaler, que é obrigatória aqui porque as escalas são absurdamente
> diferentes: `mean area` está na casa dos milhares e `mean smoothness` na casa
> dos centésimos. Sem padronizar, o KNN vira lixo.
> E o ponto **mais importante** do projeto inteiro: repare que o scaler não é
> aplicado no dataset antes do split. Ele vive **dentro de um `Pipeline` do
> scikit-learn**, junto com o classificador. Isso garante que a média e o desvio
> sejam aprendidos **só do treino**, a cada fold da validação cruzada. Se eu
> normalizasse o dataset inteiro antes, teria **vazamento de dados** e os números
> seriam otimistas e falsos.
> O split é 80/20, **estratificado**, pra manter a proporção de malignos nos
> dois lados."

---

## BLOCO 6 — Rodar o pipeline AO VIVO (5:30 – 7:30)

**TELA:** terminal, tela cheia. Digite e execute:

```bash
python main.py
```

**FALA (enquanto roda — narre as seções conforme aparecem):**
> "Vou rodar o pipeline completo agora. Ele executa sete etapas em sequência...
> — carregamento e limpeza: 569 pacientes, 30 features;
> — exploração: balanceamento, ausentes (nenhum), descritivas e correlações;
> — split: 455 de treino, 114 de teste, com a proporção de malignos preservada;
> — modelagem: quatro técnicas com validação cruzada estratificada de 5 folds;
> — avaliação no teste;
> — explicabilidade;
> — e a persistência do melhor modelo."

> "Repare que ele imprime a matriz de confusão detalhada e destaca os **falsos
> negativos** — que são os tumores malignos que passariam despercebidos. Esse é
> o número que eu mais persigo no projeto."

**AO FINAL:** mostre o explorador em `reports/figures/` — as 7 imagens recém-geradas.

---

## BLOCO 7 — Resultados e a escolha da métrica (7:30 – 9:00)

**TELA:** tabela de resultados no terminal (ou `reports/metricas_teste.csv`),
depois figuras `04_matriz_confusao_regressao_logistica.png` e `05_curvas_roc.png`.

**FALA (a discussão da métrica — este é o bloco que mais vale nota):**
> "Antes dos números, a pergunta certa: **qual métrica importa aqui?**
> Os erros têm custo **assimétrico**. Um **falso negativo** — dizer que um tumor
> maligno é benigno — atrasa o tratamento e coloca a vida da paciente em risco.
> Um **falso positivo** — dizer que um benigno é maligno — gera uma biópsia
> desnecessária e ansiedade: é um custo real, mas incomparavelmente menor.
> Por isso a métrica prioritária do projeto é o **recall da classe maligna**,
> com F1 e precision como contrapeso pra não virar um alarme que dispara sempre."

**FALA (os números):**
> "No conjunto de teste, com 114 pacientes:
> a **Regressão Logística** teve **97,4% de accuracy** e **95,2% de recall** —
> ela detectou **40 dos 42 tumores malignos**, com **apenas 2 falsos negativos**
> e 1 falso positivo. ROC-AUC de 0,995.
> O **Random Forest** empatou em accuracy e teve o melhor AUC, 0,998, e
> **precision de 100%** — nenhum falso positivo. Mas deixou passar **3**
> malignos em vez de 2.
> E aqui está o trade-off explícito: pelo critério do projeto, **um câncer a
> menos passando despercebido vale mais do que um alarme falso a menos**. Por
> isso o modelo escolhido é a Regressão Logística.
> KNN e Árvore de Decisão ficam atrás — a árvore em especial, com AUC de 0,90,
> mostrando que uma única árvore rasa não captura bem essa fronteira."

**MOSTRAR a curva ROC:** "Três dos quatro modelos ficam colados no canto
superior esquerdo — a árvore é a única visivelmente pior."

---

## BLOCO 8 — Explicabilidade (9:00 – 10:15)

**TELA:** figuras `06_feature_importance.png` e `07_shap_summary.png`.

**FALA (feature importance):**
> "Explicabilidade é obrigatória em saúde: nenhum médico aceita um modelo que
> diz 'é maligno' sem dizer **por quê**.
> Este primeiro gráfico são os coeficientes da Regressão Logística em valor
> absoluto — como as features estão padronizadas, eles são comparáveis.
> No topo aparecem `worst texture`, `radius error` e `worst symmetry`.
> E aqui eu preciso ser honesto sobre uma sutileza: **isso não significa que
> raio e área não importam**. Lembra da multicolinearidade que eu mostrei na
> matriz de correlação? Quando várias features carregam a mesma informação, o
> modelo linear **divide o peso entre elas** e nenhuma aparece grande sozinha.
> Coeficiente de modelo linear sob multicolinearidade **não é** uma medida
> confiável de importância — e é exatamente por isso que o SHAP existe."

**FALA (SHAP):**
> "O SHAP resolve isso. Ele vem da teoria dos jogos e atribui a cada feature uma
> contribuição para **cada previsão individual** — dá pra perguntar 'por que
> **esta** paciente foi classificada como maligno?'.
> Rodei sobre o Random Forest, e o resultado é limpo: as features que mais
> pesam são `worst area`, `worst perimeter`, `worst concave points`,
> `mean concave points` e `worst radius`.
> E veja o código de cores: os pontos **vermelhos** — valores altos dessas
> medidas — estão todos do lado **positivo**, empurrando a previsão para
> 'maligno'. Os azuis, valores baixos, empurram para 'benigno'.
> Ou seja: **o modelo aprendeu exatamente o critério clínico** — núcleo maior e
> contorno mais irregular indica malignidade. Não é uma correlação espúria. É
> isso que dá confiança pra colocar o modelo perto de um médico."

---

## BLOCO 9 — EXTRA: CNN em imagens de ultrassom (10:15 – 12:00)

**TELA:** notebook `tech_challenge_cnn_imagem.ipynb` (já executado) OU rode
`python main_vision.py` se quiser mostrar ao vivo — mas **só se já tiver rodado
antes**, para o dataset estar em cache.

**FALA:**
> "O item extra do enunciado é diagnóstico por imagem com rede neural
> convolucional. Eu usei o **BreastMNIST**, derivado do dataset BUSI: 780
> imagens de ultrassom de mama, baixadas automaticamente do Zenodo — sem
> depender de Kaggle, o que mantém o projeto reprodutível.
> A rede é uma CNN compacta: três blocos convolucionais e um classificador
> denso, cerca de 24 mil parâmetros — treina em **CPU em poucos minutos**.
> Mantive a mesma convenção clínica: `1 = maligno`, foco em recall."

**FALA (o ponto de operação — mostre a tabela dos dois limiares):**
> "E aqui tem a discussão mais interessante do extra. A CNN devolve uma
> **probabilidade**, então eu escolho o **limiar de decisão** conforme a
> prioridade clínica — e calibro esse limiar na **validação**, nunca no teste.
> No limiar padrão de 0,50: accuracy 85%, recall 64% — **15 cânceres não
> detectados**.
> No **ponto de operação clínico**, limiar 0,29: o recall sobe pra **79%** e os
> falsos negativos caem de 15 para **9**. O preço é a precision cair — mais
> alarmes falsos.
> Em **triagem**, esse é o trade-off certo: um falso positivo custa um exame a
> mais; um falso negativo custa um câncer não tratado."

**FALA (Grad-CAM — figura 11):**
> "E a explicabilidade da imagem é o **Grad-CAM**, que é o análogo visual do
> SHAP: ele destaca as regiões que a rede olhou pra decidir.
> E aqui eu vou ser honesto na leitura: em vários exemplos o mapa de calor está
> **espalhado pela textura do tecido**, e não concentrado no nódulo. Isso é um
> sinal de alerta legítimo — indica que a rede está se apoiando em textura geral
> e ruído de speckle, e não na lesão. É exatamente **para isso** que o Grad-CAM
> serve: ele permite **auditar** o modelo antes de confiar nele."

**FALA (leitura crítica):**
> "O modelo de imagem é honestamente **mais fraco** que o tabular — AUC de 0,85
> contra 0,99. E isso é esperado: ele resolve um problema muito mais difícil,
> aprendendo direto dos pixels, com pouquíssimos dados e imagens de baixa
> resolução, enquanto o tabular recebe features que **especialistas já
> extraíram**. Ele é uma **prova de conceito**, e o caminho de evolução é claro:
> transfer learning com ResNet ou EfficientNet, imagens maiores e mais dados."

---

## BLOCO 10 — Provas de correção (12:00 – 12:45)

**TELA:** terminal.

```bash
python -m pytest -v
```

**FALA:**
> "Por último, o que sustenta tudo que eu falei: os testes.
> São 19 testes — 12 do pipeline tabular e 7 da CNN. E o mais importante é este
> aqui: `test_scaler_ajustado_somente_no_treino`.
> Ele **prova** que o StandardScaler aprendeu a média do conjunto de treino e
> **não** a do dataset completo. Se esse teste falhasse, haveria vazamento de
> dados e **todos os números que eu mostrei seriam inválidos**.
> Tem também o teste que prova que o remapeamento do rótulo está correto — se o
> maligno não fosse a classe positiva, todo o recall que eu discuti estaria
> invertido e sem sentido."

---

## BLOCO 11 — Discussão crítica e encerramento (12:45 – 13:30)

**TELA:** `README.md`, seção 7 ("O modelo pode ser usado na prática?").

**FALA:**
> "Fechando com a pergunta que o enunciado faz: **esse modelo pode ser usado na
> prática?**
> Sim — mas **como ferramenta de apoio, nunca de decisão autônoma**.
> Dois usos concretos: **priorização de fila**, sinalizando casos de alto risco
> para revisão rápida; e **segunda opinião**, alertando quando o modelo diverge
> do laudo — uma rede de segurança.
> As limitações, com honestidade: a base é pequena e de fonte única; as features
> já foram extraídas por especialistas, então o modelo **não substitui o exame**;
> isso não é um dispositivo médico certificado. Um uso real exigiria validação
> externa e prospectiva, aprovação regulatória e monitoramento de viés entre
> subgrupos de pacientes.
> O sistema entrega **probabilidade mais explicação**. A conduta é do
> profissional. O médico tem sempre a palavra final.
> Obrigado!"

---

## Dicas finais de gravação

- **Não leia o roteiro palavra por palavra.** Use como guia; soar natural vale
  mais do que soar perfeito.
- **Se errar, não pare a gravação.** Faça uma pausa de 2 segundos, repita a
  frase e corte na edição.
- **Corte os tempos de espera.** Se `main.py` demorar 40 s, acelere ou corte —
  ninguém precisa ver a barra rodando.
- **Priorize, se o tempo apertar:** os blocos 7 (métrica), 8 (explicabilidade) e
  11 (discussão crítica) são os que mais pesam na avaliação. Blocos 3 e 10 podem
  ser encurtados.
- **Ao subir no YouTube:** marque como **Não listado**, coloque o título
  `Tech Challenge Fase 1 — Sistema de suporte ao diagnóstico em saúde da mulher`
  e **cole o link do repositório na descrição**.
