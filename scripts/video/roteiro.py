"""
O roteiro do vídeo como dado estruturado.

Transcrição dos onze blocos de ``docs/ROTEIRO_VIDEO.md`` para objetos Python.
Cada bloco tem sub-cenas; cada cena carrega o texto que o TTS vai falar e o
que aparece na tela enquanto ele fala.

Regra de ouro deste arquivo: **o texto narrado define a duração da cena**.
Não existe duração fixa em lugar nenhum — a duração sai da medição do MP3
gerado pelo TTS (ver ``narracao.py``). Escrever uma frase a mais alonga a
cena automaticamente; apagar uma frase encurta.

Sobre o texto de :attr:`Cena.narracao`:

* nada de markdown (``**negrito**``, crases, listas) — o TTS leria os símbolos;
* números escritos por extenso quando a pronúncia mecânica ficaria ruim
  ("noventa e cinco vírgula dois por cento" em vez de "95,2%");
* siglas soletradas quando necessário ("Erre O Cê", "A U Cê").

A legenda ``.srt``, por outro lado, é gerada a partir dos *word boundaries*
do próprio TTS, então ela reflete exatamente o que foi falado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos (compartilhados por todo o pacote scripts/video)
# ---------------------------------------------------------------------------
ESTE_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = ESTE_DIR.parents[1]
CACHE_DIR: Path = ESTE_DIR / "_cache"
AUDIO_DIR: Path = CACHE_DIR / "audio"
PREVIA_DIR: Path = CACHE_DIR / "previa"
CLIPES_DIR: Path = CACHE_DIR / "clipes"
FIGURES_DIR: Path = PROJECT_ROOT / "reports" / "figures"
SAIDA_DIR: Path = PROJECT_ROOT / "video"

NOME_SAIDA: str = "tech_challenge_fase1_demo"

# Formato do vídeo.
LARGURA: int = 1920
ALTURA: int = 1080
FPS: int = 30

# Limite do enunciado, em segundos.
LIMITE_SEGUNDOS: int = 15 * 60


class Visual(str, Enum):
    """Tipo de tela que o renderizador deve desenhar para a cena."""

    TITULO = "titulo"      # cartão de título (frame estático)
    FIGURA = "figura"      # PNG de reports/figures/ com moldura e legenda
    TERMINAL = "terminal"  # animação de digitação da saída real capturada
    CODIGO = "codigo"      # trecho de .py com números de linha e destaque
    ARVORE = "arvore"      # árvore de arquivos do projeto


@dataclass(frozen=True)
class Cena:
    """Uma unidade indivisível: um áudio narrado + uma tela.

    Attributes
    ----------
    id:
        Identificador estável (usado no nome dos arquivos de cache).
    narracao:
        O texto que o TTS vai falar. Define a duração da cena.
    visual:
        Qual renderizador de ``visuais.py`` desenha esta cena.
    asset:
        Depende do ``visual``: caminho do PNG (``figura``), caminho do ``.py``
        relativo à raiz (``codigo``), id da captura (``terminal``), vazio para
        ``titulo`` e ``arvore``.
    titulo / subtitulo / topicos:
        Conteúdo dos cartões ``titulo`` e cabeçalho das demais telas.
    legenda:
        Linha de apoio no rodapé (usada em ``figura``).
    linha_inicial / linha_final:
        Recorte por número de linha (1-based, inclusivo). Usado em ``codigo``
        e como alternativa em ``terminal``.
    marcador_inicio / marcador_fim:
        Recorte de ``terminal`` por conteúdo, mais robusto que número de linha:
        procura a primeira linha que contém o texto. Se ``marcador_fim`` não
        for encontrado, vai até o fim do arquivo.
    linhas_finais:
        Em cenas ``terminal``, anexa as N últimas linhas do arquivo depois de
        um marcador ``[...]`` visível na tela. Serve para mostrar o veredito
        final de um comando sem exibir o miolo irrelevante (o bloco de
        *warnings* do pytest, por exemplo). A elisão aparece para o
        espectador — nada é reescrito nem inventado.
    destaque:
        Números de linha (absolutos, 1-based) a realçar com fundo amarelo em
        cenas ``codigo``.
    """

    id: str
    narracao: str
    visual: Visual
    asset: str = ""
    titulo: str = ""
    subtitulo: str = ""
    topicos: tuple[str, ...] = ()
    legenda: str = ""
    linha_inicial: int | None = None
    linha_final: int | None = None
    marcador_inicio: str = ""
    marcador_fim: str = ""
    linhas_finais: int = 0
    destaque: tuple[int, ...] = ()


@dataclass(frozen=True)
class Bloco:
    """Um dos onze blocos do roteiro."""

    numero: int
    titulo: str
    cenas: tuple[Cena, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Texto fixo reaproveitado
# ---------------------------------------------------------------------------
NOME_APRESENTADOR = "Enio Rodrigues"

TITULO_VIDEO = "Tech Challenge — Fase 1"
SUBTITULO_VIDEO = "Sistema de suporte ao diagnóstico em saúde da mulher"


# ---------------------------------------------------------------------------
# BLOCOS
# ---------------------------------------------------------------------------
BLOCOS: tuple[Bloco, ...] = (
    # ===================================================================== 1
    Bloco(
        numero=1,
        titulo="Abertura e problema",
        cenas=(
            Cena(
                id="b01c01_abertura",
                visual=Visual.TITULO,
                titulo=TITULO_VIDEO,
                subtitulo=SUBTITULO_VIDEO,
                topicos=(
                    "Machine Learning aplicado ao diagnóstico de câncer de mama",
                    "Breast Cancer Wisconsin  +  EXTRA: CNN em ultrassom",
                    NOME_APRESENTADOR,
                ),
                narracao=(
                    f"Olá! Eu sou o {NOME_APRESENTADOR}, e este é o Tech Challenge da Fase um. "
                    "O desafio é criar a base de um sistema inteligente de suporte ao diagnóstico "
                    "para uma rede de hospitais especializada na saúde da mulher."
                ),
            ),
            Cena(
                id="b01c02_o_que_construi",
                visual=Visual.TITULO,
                titulo="O que foi construído",
                subtitulo="Dois pipelines completos, do dado bruto à explicação",
                topicos=(
                    "1.  Classificação tabular: tumor maligno ou benigno",
                    "2.  EXTRA: rede neural convolucional em ultrassom",
                    "3.  Explicabilidade: SHAP e Grad-CAM",
                ),
                narracao=(
                    "O que eu construí foi um sistema de Machine Learning que classifica tumores "
                    "de mama como malignos ou benignos a partir de dados de exame. E, como item "
                    "extra, uma rede neural convolucional que faz o mesmo diagnóstico direto de "
                    "imagens de ultrassom."
                ),
            ),
            Cena(
                id="b01c03_copiloto",
                visual=Visual.TITULO,
                titulo="A premissa central",
                subtitulo="O modelo é um copiloto",
                topicos=(
                    "Entrega probabilidade + explicação",
                    "Nunca decide sozinho",
                    "O médico tem sempre a palavra final",
                ),
                narracao=(
                    "A premissa central do projeto é uma só: o modelo é um copiloto. "
                    "O médico tem sempre a palavra final."
                ),
            ),
        ),
    ),
    # ===================================================================== 2
    Bloco(
        numero=2,
        titulo="Dataset e discussão do problema",
        cenas=(
            Cena(
                id="b02c01_dataset",
                visual=Visual.TITULO,
                titulo="A base de dados",
                subtitulo="Breast Cancer Wisconsin (Diagnostic)",
                topicos=(
                    "569 pacientes  ·  30 features numéricas",
                    "Punção por agulha fina: raio, textura, perímetro, área, concavidade",
                    "Três resumos por medida: média, erro-padrão e o 'pior' valor",
                ),
                narracao=(
                    "A base é a Breast Cancer Wisconsin Diagnostic, que é justamente a tarefa "
                    "principal sugerida no enunciado. São quinhentos e sessenta e nove pacientes "
                    "e trinta features numéricas extraídas de imagens de punção por agulha fina: "
                    "raio, textura, perímetro, área, concavidade. Cada uma em três resumos: "
                    "a média, o erro-padrão e o pior valor observado."
                ),
            ),
            Cena(
                id="b02c02_balanceamento",
                visual=Visual.FIGURA,
                asset="01_balanceamento_classes.png",
                titulo="Distribuição das classes",
                legenda="357 benignos  ·  212 malignos  —  desbalanceamento moderado (37%)",
                narracao=(
                    "A distribuição é de trezentos e cinquenta e sete benignos contra duzentos e "
                    "doze malignos. Trinta e sete por cento de malignos: um desbalanceamento "
                    "moderado, que eu trato com estratificação no split e com pesos de classe "
                    "nos modelos."
                ),
            ),
            Cena(
                id="b02c03_convencao_rotulo",
                visual=Visual.CODIGO,
                asset="src/config.py",
                linha_inicial=26,
                linha_final=41,
                destaque=(38, 39),
                titulo="src/config.py — a convenção de rotulagem",
                narracao=(
                    "E aqui está uma decisão de projeto importante. O scikit-learn carrega essa "
                    "base com zero igual a maligno. Eu inverti o rótulo para que um seja igual a "
                    "maligno, porque assim o recall passa a significar literalmente: quantos "
                    "cânceres eu detectei. Que é a métrica que importa clinicamente."
                ),
            ),
        ),
    ),
    # ===================================================================== 3
    Bloco(
        numero=3,
        titulo="Tour pela arquitetura",
        cenas=(
            Cena(
                id="b03c01_arvore",
                visual=Visual.ARVORE,
                titulo="Arquitetura do projeto",
                narracao=(
                    "O projeto está organizado como pacote Python, não como um notebook solto. "
                    "Em src ficam os módulos reutilizáveis: data loader carrega os dados, "
                    "preprocessing faz limpeza e split, e dê a gera a análise exploratória, "
                    "modeling define os classificadores, evaluation calcula as métricas, "
                    "explainability faz feature importance e SHAP, e vision é o extra da CNN."
                ),
            ),
            Cena(
                id="b03c02_orquestracao",
                visual=Visual.ARVORE,
                titulo="Arquitetura do projeto",
                narracao=(
                    "O main ponto py orquestra o pipeline tabular de ponta a ponta, e o "
                    "main vision orquestra o de imagem. Os notebooks contam a mesma história de "
                    "forma narrada, com as saídas já salvas. E tem a pasta tests, com as provas "
                    "de correção. Eu volto nisso no final, porque é o que sustenta a "
                    "credibilidade dos números. Tem também um Dockerfile, para quem quiser rodar "
                    "sem instalar nada."
                ),
            ),
        ),
    ),
    # ===================================================================== 4
    Bloco(
        numero=4,
        titulo="Análise exploratória",
        cenas=(
            Cena(
                id="b04c01_distribuicoes",
                visual=Visual.FIGURA,
                asset="02_distribuicoes_por_classe.png",
                titulo="Distribuições por classe",
                legenda="As seis features mais correlacionadas com o diagnóstico",
                narracao=(
                    "Começando pela exploração. O balanceamento que eu mostrei já mata a accuracy "
                    "como métrica única: um modelo que chutasse benigno para todo mundo já "
                    "acertaria sessenta e três por cento. "
                    "E aqui está o achado mais forte da exploração. Nas seis features mais "
                    "correlacionadas com o diagnóstico, as duas classes formam duas montanhas "
                    "claramente separadas: o benigno concentrado à esquerda, o maligno deslocado "
                    "para a direita, com uma zona de sobreposição estreita."
                ),
            ),
            Cena(
                id="b04c02_leitura_clinica",
                visual=Visual.FIGURA,
                asset="02_distribuicoes_por_classe.png",
                titulo="Leitura clínica do achado",
                legenda="Tumores malignos têm núcleos maiores e contornos mais irregulares",
                narracao=(
                    "Traduzindo clinicamente: tumores malignos têm núcleos celulares maiores e "
                    "contornos mais irregulares. Isso é exatamente o que a literatura médica "
                    "descreve, e é o que explica por que esse problema é tratável com modelos "
                    "relativamente simples."
                ),
            ),
            Cena(
                id="b04c03_correlacao",
                visual=Visual.FIGURA,
                asset="03_matriz_correlacao.png",
                titulo="Matriz de correlação",
                legenda="21 pares de features com correlação acima de 0,9 — multicolinearidade pesada",
                narracao=(
                    "A matriz de correlação mostra blocos vermelhos muito fortes. Encontrei "
                    "vinte e um pares de features com correlação acima de zero vírgula nove. "
                    "É multicolinearidade pesada, e é esperada: raio, perímetro e área são "
                    "geometricamente a mesma informação. Isso não atrapalha árvores nem o KNN, "
                    "mas espalha os coeficientes da regressão logística entre features "
                    "redundantes. Guarde isso, porque volta na parte de explicabilidade."
                ),
            ),
        ),
    ),
    # ===================================================================== 5
    Bloco(
        numero=5,
        titulo="Pré-processamento e o anti-vazamento",
        cenas=(
            Cena(
                id="b05c01_preprocessing",
                visual=Visual.CODIGO,
                asset="src/preprocessing.py",
                linha_inicial=51,
                linha_final=67,
                destaque=(58, 59, 60, 61, 62, 63),
                titulo="src/preprocessing.py — build_preprocessor",
                narracao=(
                    "O pré-processamento tem três peças. Limpeza defensiva: duplicatas e colunas "
                    "vazias. Imputação pela mediana, que é robusta a outliers. E padronização com "
                    "o StandardScaler, que é obrigatória aqui porque as escalas são absurdamente "
                    "diferentes: mean area está na casa dos milhares e mean smoothness na casa "
                    "dos centésimos. Sem padronizar, o KNN vira lixo."
                ),
            ),
            Cena(
                id="b05c02_antivazamento",
                visual=Visual.CODIGO,
                asset="src/modeling.py",
                linha_inicial=60,
                linha_final=70,
                destaque=(63, 64, 65, 66, 67, 68),
                titulo="src/modeling.py — o scaler vive DENTRO do Pipeline",
                narracao=(
                    "E agora o ponto mais importante do projeto inteiro. Repare que o scaler não é "
                    "aplicado no dataset antes do split. Ele vive dentro de um Pipeline do "
                    "scikit-learn, junto com o classificador. Isso garante que a média e o desvio "
                    "sejam aprendidos só do treino, a cada fold da validação cruzada. Se eu "
                    "normalizasse o dataset inteiro antes, teria vazamento de dados, e os números "
                    "seriam otimistas e falsos. O split é oitenta, vinte, estratificado, para "
                    "manter a proporção de malignos nos dois lados."
                ),
            ),
        ),
    ),
    # ===================================================================== 6
    Bloco(
        numero=6,
        titulo="Rodando o pipeline ao vivo",
        cenas=(
            Cena(
                id="b06c01_carregamento",
                visual=Visual.TERMINAL,
                asset="terminal_main",
                marcador_inicio="1. CARREGAMENTO DOS DADOS",
                marcador_fim="Features mais correlacionadas",
                titulo="python main.py — carregamento e exploração",
                narracao=(
                    "Vou rodar o pipeline completo agora. Ele executa sete etapas em sequência. "
                    "Carregamento e limpeza: quinhentos e sessenta e nove pacientes, trinta "
                    "features. Exploração: balanceamento, valores ausentes (nenhum), estatísticas "
                    "descritivas e correlações."
                ),
            ),
            Cena(
                id="b06c02_split_e_cv",
                visual=Visual.TERMINAL,
                asset="terminal_main",
                marcador_inicio="3. PRÉ-PROCESSAMENTO E SPLIT",
                marcador_fim="5. AVALIAÇÃO NO CONJUNTO DE TESTE",
                titulo="python main.py — split e validação cruzada",
                narracao=(
                    "Split: quatrocentos e cinquenta e cinco de treino, cento e quatorze de teste, "
                    "com a proporção de malignos preservada. E olha a linha que o próprio pipeline "
                    "imprime: a padronização vive dentro do pipeline, sem vazamento de dados. "
                    "Depois, modelagem: quatro técnicas, com validação cruzada estratificada de "
                    "cinco folds."
                ),
            ),
            Cena(
                id="b06c03_avaliacao",
                visual=Visual.TERMINAL,
                asset="terminal_main",
                marcador_inicio="5. AVALIAÇÃO NO CONJUNTO DE TESTE",
                marcador_fim="6. EXPLICABILIDADE",
                titulo="python main.py — avaliação no teste",
                narracao=(
                    "Aqui está a avaliação no conjunto de teste. Repare que ele imprime a matriz "
                    "de confusão detalhada do melhor modelo e destaca os falsos negativos: os "
                    "tumores malignos que passariam despercebidos. Esse é o número que eu mais "
                    "persigo no projeto."
                ),
            ),
            Cena(
                id="b06c04_persistencia",
                visual=Visual.TERMINAL,
                asset="terminal_main",
                marcador_inicio="6. EXPLICABILIDADE",
                titulo="python main.py — explicabilidade e persistência",
                narracao=(
                    "E o pipeline fecha com explicabilidade e persistência: o melhor modelo vai "
                    "para disco em formato joblib, as métricas viram CSV e as sete figuras são "
                    "regravadas em reports, figures. Tudo reprodutível a partir de um único "
                    "comando."
                ),
            ),
        ),
    ),
    # ===================================================================== 7
    Bloco(
        numero=7,
        titulo="Resultados e a escolha da métrica",
        cenas=(
            Cena(
                id="b07c01_qual_metrica",
                visual=Visual.TITULO,
                titulo="Qual métrica importa aqui?",
                subtitulo="Os erros têm custo assimétrico",
                topicos=(
                    "Falso negativo  →  câncer não detectado, tratamento atrasado",
                    "Falso positivo  →  biópsia desnecessária e ansiedade",
                    "Métrica prioritária: RECALL da classe maligna",
                ),
                narracao=(
                    "Antes dos números, a pergunta certa: qual métrica importa aqui? "
                    "Os erros têm custo assimétrico. Um falso negativo, dizer que um tumor "
                    "maligno é benigno, atrasa o tratamento e coloca a vida da paciente em risco. "
                    "Um falso positivo, dizer que um benigno é maligno, gera uma biópsia "
                    "desnecessária e ansiedade. É um custo real, mas incomparavelmente menor. "
                    "Por isso a métrica prioritária do projeto é o recall da classe maligna, com "
                    "F um e precisão como contrapeso, para não virar um alarme que dispara sempre."
                ),
            ),
            Cena(
                id="b07c02_numeros",
                visual=Visual.TERMINAL,
                asset="terminal_main",
                marcador_inicio="5. AVALIAÇÃO NO CONJUNTO DE TESTE",
                marcador_fim="6. EXPLICABILIDADE",
                titulo="Resultados no conjunto de teste (114 pacientes)",
                narracao=(
                    "No conjunto de teste, com cento e quatorze pacientes: a Regressão Logística "
                    "teve noventa e sete vírgula quatro por cento de accuracy e noventa e cinco "
                    "vírgula dois por cento de recall. Ela detectou quarenta dos quarenta e dois "
                    "tumores malignos, com apenas dois falsos negativos e um falso positivo. "
                    "Área sob a curva de zero vírgula nove nove cinco."
                ),
            ),
            Cena(
                id="b07c03_tradeoff",
                visual=Visual.FIGURA,
                asset="04_matriz_confusao_regressao_logistica.png",
                titulo="Matriz de confusão — Regressão Logística",
                legenda="40 de 42 malignos detectados  ·  2 falsos negativos  ·  1 falso positivo",
                narracao=(
                    "O Random Forest empatou em accuracy e teve a melhor área sob a curva, zero "
                    "vírgula nove nove oito, e precisão de cem por cento: nenhum falso positivo. "
                    "Mas deixou passar três malignos, em vez de dois. "
                    "E aqui está o trade-off explícito: pelo critério do projeto, um câncer a "
                    "menos passando despercebido vale mais do que um alarme falso a menos. "
                    "Por isso o modelo escolhido é a Regressão Logística."
                ),
            ),
            Cena(
                id="b07c04_roc",
                visual=Visual.FIGURA,
                asset="05_curvas_roc.png",
                titulo="Curvas ROC dos quatro modelos",
                legenda="Três modelos colados no canto superior esquerdo; a árvore é a única visivelmente pior",
                narracao=(
                    "KNN e Árvore de Decisão ficam atrás. A árvore em especial, com área sob a "
                    "curva de zero vírgula noventa, mostrando que uma única árvore rasa não "
                    "captura bem essa fronteira. Na curva Erre O Cê, três dos quatro modelos "
                    "ficam colados no canto superior esquerdo. A árvore é a única visivelmente "
                    "pior."
                ),
            ),
        ),
    ),
    # ===================================================================== 8
    Bloco(
        numero=8,
        titulo="Explicabilidade",
        cenas=(
            Cena(
                id="b08c01_feature_importance",
                visual=Visual.FIGURA,
                asset="06_feature_importance.png",
                titulo="Importância das features — Regressão Logística",
                legenda="Coeficientes em valor absoluto (features padronizadas, portanto comparáveis)",
                narracao=(
                    "Explicabilidade é obrigatória em saúde: nenhum médico aceita um modelo que "
                    "diz é maligno sem dizer por quê. "
                    "Este primeiro gráfico são os coeficientes da Regressão Logística em valor "
                    "absoluto. Como as features estão padronizadas, eles são comparáveis. "
                    "No topo aparecem worst texture, radius error e worst symmetry."
                ),
            ),
            Cena(
                id="b08c02_honestidade",
                visual=Visual.FIGURA,
                asset="06_feature_importance.png",
                titulo="Uma ressalva honesta",
                legenda="Sob multicolinearidade, coeficiente linear NÃO é medida confiável de importância",
                narracao=(
                    "E aqui eu preciso ser honesto sobre uma sutileza: isso não significa que raio "
                    "e área não importam. Lembra da multicolinearidade que eu mostrei na matriz de "
                    "correlação? Quando várias features carregam a mesma informação, o modelo "
                    "linear divide o peso entre elas e nenhuma aparece grande sozinha. "
                    "Coeficiente de modelo linear sob multicolinearidade não é uma medida "
                    "confiável de importância. E é exatamente por isso que o SHAP existe."
                ),
            ),
            Cena(
                id="b08c03_shap",
                visual=Visual.FIGURA,
                asset="07_shap_summary.png",
                titulo="SHAP summary — Random Forest",
                legenda="Contribuição de cada feature para cada previsão individual",
                narracao=(
                    "O SHAP resolve isso. Ele vem da teoria dos jogos e atribui a cada feature uma "
                    "contribuição para cada previsão individual. Dá para perguntar: por que esta "
                    "paciente foi classificada como maligno? "
                    "Rodei sobre o Random Forest, e o resultado é limpo: as features que mais "
                    "pesam são worst area, worst perimeter, worst concave points, mean concave "
                    "points e worst radius."
                ),
            ),
            Cena(
                id="b08c04_shap_leitura",
                visual=Visual.FIGURA,
                asset="07_shap_summary.png",
                titulo="O modelo aprendeu o critério clínico",
                legenda="Vermelho = valor alto empurrando para 'maligno'  ·  Azul = valor baixo empurrando para 'benigno'",
                narracao=(
                    "E veja o código de cores: os pontos vermelhos, valores altos dessas medidas, "
                    "estão todos do lado positivo, empurrando a previsão para maligno. Os azuis, "
                    "valores baixos, empurram para benigno. "
                    "Ou seja: o modelo aprendeu exatamente o critério clínico. Núcleo maior e "
                    "contorno mais irregular indica malignidade. Não é uma correlação espúria. "
                    "É isso que dá confiança para colocar o modelo perto de um médico."
                ),
            ),
        ),
    ),
    # ===================================================================== 9
    Bloco(
        numero=9,
        titulo="EXTRA — CNN em imagens de ultrassom",
        cenas=(
            Cena(
                id="b09c01_extra_intro",
                visual=Visual.FIGURA,
                asset="10_cnn_amostras.png",
                titulo="EXTRA — BreastMNIST (ultrassom de mama)",
                legenda="780 imagens derivadas do dataset BUSI, baixadas automaticamente do Zenodo",
                narracao=(
                    "O item extra do enunciado é diagnóstico por imagem com rede neural "
                    "convolucional. Eu usei o BreastMNIST, derivado do dataset BUSI: setecentas e "
                    "oitenta imagens de ultrassom de mama, baixadas automaticamente do Zenodo, sem "
                    "depender do Kaggle, o que mantém o projeto reprodutível."
                ),
            ),
            Cena(
                id="b09c02_arquitetura_cnn",
                visual=Visual.FIGURA,
                asset="08_cnn_treino.png",
                titulo="Treino da CNN",
                legenda="Três blocos convolucionais + classificador denso  ·  ~24 mil parâmetros  ·  treina em CPU",
                narracao=(
                    "A rede é uma CNN compacta: três blocos convolucionais e um classificador "
                    "denso, cerca de vinte e quatro mil parâmetros. Treina em CPU em poucos "
                    "minutos. Mantive a mesma convenção clínica: um igual a maligno, foco em "
                    "recall."
                ),
            ),
            Cena(
                id="b09c03_limiar",
                visual=Visual.TERMINAL,
                asset="terminal_vision",
                marcador_inicio="3. AVALIAÇÃO NO CONJUNTO DE TESTE",
                marcador_fim="4. EXPLICABILIDADE",
                titulo="python main_vision.py — os dois pontos de operação",
                narracao=(
                    "E aqui tem a discussão mais interessante do extra. A CNN devolve uma "
                    "probabilidade, então eu escolho o limiar de decisão conforme a prioridade "
                    "clínica. E calibro esse limiar na validação, nunca no teste. "
                    "No limiar padrão de zero vírgula cinquenta: accuracy de oitenta e cinco por "
                    "cento, recall de sessenta e quatro por cento. Quinze cânceres não detectados."
                ),
            ),
            Cena(
                id="b09c04_triagem",
                visual=Visual.TITULO,
                titulo="O trade-off da triagem",
                subtitulo="O limiar é uma decisão clínica, não um detalhe técnico",
                topicos=(
                    "Limiar 0,50 (padrão):   accuracy 85%  ·  recall 64%  ·  15 falsos negativos",
                    "Limiar 0,29 (clínico):  accuracy 72%  ·  recall 79%  ·   9 falsos negativos",
                    "Falso positivo custa um exame a mais",
                    "Falso negativo custa um câncer não tratado",
                ),
                narracao=(
                    "No ponto de operação clínico, limiar zero vírgula vinte e nove, o recall sobe "
                    "para setenta e nove por cento e os falsos negativos caem de quinze para nove. "
                    "O preço é a precisão cair: mais alarmes falsos. "
                    "Em triagem, esse é o trade-off certo. Um falso positivo custa um exame a "
                    "mais; um falso negativo custa um câncer não tratado."
                ),
            ),
            Cena(
                id="b09c05_gradcam",
                visual=Visual.FIGURA,
                asset="11_cnn_gradcam.png",
                titulo="Grad-CAM — auditando o que a rede olhou",
                legenda="Em vários exemplos o calor está espalhado pela textura, não concentrado no nódulo",
                narracao=(
                    "E a explicabilidade da imagem é o Grad-CAM, que é o análogo visual do SHAP: "
                    "ele destaca as regiões que a rede olhou para decidir. "
                    "E aqui eu vou ser honesto na leitura: em vários exemplos o mapa de calor está "
                    "espalhado pela textura do tecido, e não concentrado no nódulo. Isso é um sinal "
                    "de alerta legítimo. Indica que a rede está se apoiando em textura geral e "
                    "ruído de speckle, e não na lesão. É exatamente para isso que o Grad-CAM "
                    "serve: ele permite auditar o modelo antes de confiar nele."
                ),
            ),
            Cena(
                id="b09c06_leitura_critica",
                visual=Visual.FIGURA,
                asset="09_cnn_matriz_confusao.png",
                titulo="Leitura crítica do extra",
                legenda="AUC 0,85 (imagem) contra 0,99 (tabular) — uma prova de conceito honesta",
                narracao=(
                    "O modelo de imagem é honestamente mais fraco que o tabular. Área sob a curva "
                    "de zero vírgula oitenta e cinco contra zero vírgula noventa e nove. E isso é "
                    "esperado: ele resolve um problema muito mais difícil, aprendendo direto dos "
                    "pixels, com pouquíssimos dados e imagens de baixa resolução, enquanto o "
                    "tabular recebe features que especialistas já extraíram. "
                    "Ele é uma prova de conceito, e o caminho de evolução é claro: transfer "
                    "learning com ResNet ou EfficientNet, imagens maiores e mais dados."
                ),
            ),
        ),
    ),
    # ==================================================================== 10
    Bloco(
        numero=10,
        titulo="Provas de correção",
        cenas=(
            Cena(
                id="b10c01_pytest",
                visual=Visual.TERMINAL,
                asset="terminal_pytest",
                # Corta antes do bloco de warnings (ruído de bibliotecas de
                # terceiros) e traz de volta a linha do veredito final.
                marcador_fim="warnings summary",
                linhas_finais=1,
                titulo="python -m pytest -v",
                narracao=(
                    "Por último, o que sustenta tudo que eu falei: os testes. "
                    "São dezenove testes: doze do pipeline tabular e sete da CNN."
                ),
            ),
            Cena(
                id="b10c02_teste_vazamento",
                visual=Visual.CODIGO,
                asset="tests/test_pipeline.py",
                linha_inicial=82,
                linha_final=108,
                destaque=(82, 100, 101, 102, 103, 104, 105, 106, 107),
                titulo="tests/test_pipeline.py — a prova do anti-vazamento",
                narracao=(
                    "E o mais importante é este aqui: teste scaler ajustado somente no treino. "
                    "Ele prova que o StandardScaler aprendeu a média do conjunto de treino, e não "
                    "a do dataset completo. Se esse teste falhasse, haveria vazamento de dados e "
                    "todos os números que eu mostrei seriam inválidos. "
                    "Tem também o teste que prova que o remapeamento do rótulo está correto. Se o "
                    "maligno não fosse a classe positiva, todo o recall que eu discuti estaria "
                    "invertido e sem sentido."
                ),
            ),
        ),
    ),
    # ==================================================================== 11
    Bloco(
        numero=11,
        titulo="Discussão crítica e encerramento",
        cenas=(
            Cena(
                id="b11c01_pode_usar",
                visual=Visual.TITULO,
                titulo="O modelo pode ser usado na prática?",
                subtitulo="Sim — como ferramenta de apoio, nunca de decisão autônoma",
                topicos=(
                    "Priorização de fila: sinalizar casos de alto risco para revisão rápida",
                    "Segunda opinião: alertar quando o modelo diverge do laudo",
                ),
                narracao=(
                    "Fechando com a pergunta que o enunciado faz: esse modelo pode ser usado na "
                    "prática? Sim, mas como ferramenta de apoio, nunca de decisão autônoma. "
                    "Dois usos concretos: priorização de fila, sinalizando casos de alto risco "
                    "para revisão rápida; e segunda opinião, alertando quando o modelo diverge do "
                    "laudo. Uma rede de segurança."
                ),
            ),
            Cena(
                id="b11c02_limitacoes",
                visual=Visual.TITULO,
                titulo="Limitações, com honestidade",
                subtitulo="O que este projeto NÃO é",
                topicos=(
                    "Base pequena e de fonte única",
                    "Features já extraídas por especialistas — não substitui o exame",
                    "Não é um dispositivo médico certificado",
                    "Uso real exigiria validação externa, regulação e monitoramento de viés",
                ),
                narracao=(
                    "As limitações, com honestidade: a base é pequena e de fonte única; as "
                    "features já foram extraídas por especialistas, então o modelo não substitui "
                    "o exame; e isso não é um dispositivo médico certificado. Um uso real exigiria "
                    "validação externa e prospectiva, aprovação regulatória e monitoramento de "
                    "viés entre subgrupos de pacientes."
                ),
            ),
            Cena(
                id="b11c03_encerramento",
                visual=Visual.TITULO,
                titulo="Probabilidade + explicação",
                subtitulo="A conduta é do profissional",
                topicos=(
                    "O médico tem sempre a palavra final.",
                    "",
                    "Obrigado!",
                ),
                narracao=(
                    "O sistema entrega probabilidade mais explicação. A conduta é do profissional. "
                    "O médico tem sempre a palavra final. Obrigado!"
                ),
            ),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Helpers de consulta
# ---------------------------------------------------------------------------
def todas_as_cenas(blocos: tuple[Bloco, ...] = BLOCOS) -> list[tuple[Bloco, Cena]]:
    """Achata o roteiro em pares (bloco, cena), na ordem de exibição."""
    return [(bloco, cena) for bloco in blocos for cena in bloco.cenas]


def filtrar_blocos(numeros: list[int] | None) -> tuple[Bloco, ...]:
    """Devolve só os blocos pedidos (para iteração rápida com --blocos)."""
    if not numeros:
        return BLOCOS
    escolhidos = tuple(b for b in BLOCOS if b.numero in set(numeros))
    if not escolhidos:
        disponiveis = ", ".join(str(b.numero) for b in BLOCOS)
        raise SystemExit(
            f"Nenhum bloco corresponde a {numeros}. Disponíveis: {disponiveis}"
        )
    return escolhidos


def contar_palavras(blocos: tuple[Bloco, ...] = BLOCOS) -> int:
    """Total de palavras narradas — estimativa grosseira de duração."""
    return sum(len(cena.narracao.split()) for _, cena in todas_as_cenas(blocos))


if __name__ == "__main__":  # pragma: no cover - inspeção manual
    palavras = contar_palavras()
    print(f"{len(BLOCOS)} blocos, {len(todas_as_cenas())} cenas, {palavras} palavras")
    # ~165 palavras/minuto é a cadência típica do edge-tts em pt-BR.
    print(f"Estimativa grosseira: {palavras / 165:.1f} min")
    for bloco in BLOCOS:
        p = sum(len(c.narracao.split()) for c in bloco.cenas)
        print(f"  Bloco {bloco.numero:2d} — {bloco.titulo:42s} "
              f"{len(bloco.cenas)} cenas, {p:4d} palavras")
