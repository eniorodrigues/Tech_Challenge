"""
O roteiro do vídeo como dado estruturado (Fase 2 — MedRoute).

Cada :class:`Cena` tem o que aparece na tela (``visual`` + ``asset``), os
**pontos** que a narração precisa cobrir (fatos e números verificados nos
resultados do projeto) e o texto narrado final (``narracao``).

Fluxo de escrita da narração:

1. ``pontos`` foram escritos a partir dos resultados reais (``reports/``);
2. ``python scripts/video/rascunho_llm.py`` pede à LLM gratuita da OpenRouter
   (Nemotron 3 Ultra) um rascunho falado para cada cena, a partir dos pontos
   — saída em ``docs/ROTEIRO_RASCUNHO_LLM.md``;
3. o rascunho foi revisado (números conferidos, siglas e números escritos
   para leitura em voz alta) e colado em ``narracao``.

A duração de cada cena vem da medição do áudio narrado (edge-tts), nunca de
um valor fixo; ``alvo_seg`` é só a meta usada para pedir o rascunho.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
ESTE_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = ESTE_DIR.parents[1]                 # fase2/
CACHE_DIR: Path = ESTE_DIR / "_cache"
AUDIO_DIR: Path = CACHE_DIR / "audio"
PREVIA_DIR: Path = CACHE_DIR / "previa"
CLIPES_DIR: Path = CACHE_DIR / "clipes"
TELAS_DIR: Path = CACHE_DIR / "telas"
EVOLUCAO_DIR: Path = CACHE_DIR / "evolucao"
FIGURES_DIR: Path = PROJECT_ROOT / "reports" / "figures"
LLM_DIR: Path = PROJECT_ROOT / "reports" / "llm"
SAIDA_DIR: Path = PROJECT_ROOT / "video"

NOME_SAIDA: str = "tech_challenge_fase2_demo"
LARGURA: int = 1920
ALTURA: int = 1080
FPS: int = 30
LIMITE_SEGUNDOS: int = 15 * 60

NOME_APRESENTADOR = "Enio Rodrigues"
RODAPE = "Tech Challenge — Fase 2  ·  MedRoute: rotas de medicamentos e insumos"


class Visual(str, Enum):
    TITULO = "titulo"        # cartão de título
    FIGURA = "figura"        # PNG de reports/figures (com zoom opcional)
    TERMINAL = "terminal"    # saída real capturada, "digitada" ao longo da fala
    CODIGO = "codigo"        # trecho de código com destaque
    ARVORE = "arvore"        # árvore de arquivos do projeto
    TELA = "tela"            # captura real do painel/API/mapa (zoom opcional)
    DOCUMENTO = "documento"  # Markdown gerado pela LLM, com rolagem
    CHAT = "chat"            # perguntas e respostas da LLM em balões
    EVOLUCAO = "evolucao"    # animação da evolução do GA


@dataclass(frozen=True)
class Cena:
    id: str
    visual: Visual
    pontos: tuple[str, ...]
    narracao: str = ""
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
    zoom: tuple[float, float, float, float] | None = None   # recorte final (x0,y0,x1,y1 em fração)
    alvo_seg: int = 25


@dataclass(frozen=True)
class Bloco:
    numero: int
    titulo: str
    cenas: tuple[Cena, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Roteiro
# ---------------------------------------------------------------------------
from narracao_texto import NARRACAO  # noqa: E402  (texto final, revisado)


def _n(cid: str) -> str:
    return NARRACAO.get(cid, "")


BLOCOS: tuple[Bloco, ...] = (
    Bloco(1, "Abertura", (
        Cena("b01c01_abertura", Visual.TITULO, alvo_seg=25,
             titulo="Tech Challenge — Fase 2",
             subtitulo="MedRoute: otimização de rotas para distribuição de medicamentos e insumos",
             topicos=("Algoritmo genético para roteamento de veículos (VRP)",
                      "Restrições reais de um hospital universitário",
                      "LLM gratuita para instruções, relatórios e perguntas",
                      "", NOME_APRESENTADOR),
             pontos=("Apresentador: Enio Rodrigues. Tech Challenge da Fase 2, Projeto 2.",
                     "Problema: distribuir medicamentos e insumos do hospital universitário para "
                     "unidades de saúde e para pacientes em atendimento domiciliar.",
                     "Solução: algoritmo genético para as rotas + LLM para instruções, relatórios "
                     "e respostas em linguagem natural."),
             narracao=_n("b01c01_abertura")),
        Cena("b01c02_visao", Visual.FIGURA, asset="00_arquitetura.png", alvo_seg=25,
             titulo="Visão geral da solução",
             pontos=("Pacote Python chamado medroute.",
                     "Entrada: cenário do dia, regras de negócio e distâncias.",
                     "Otimização: função fitness, algoritmo genético e abordagens de comparação.",
                     "Saídas: plano com indicadores, mapas, LLM via OpenRouter e as interfaces: "
                     "linha de comando, API REST, painel Streamlit, notebook e o visualizador "
                     "pygame herdado do código base."),
             narracao=_n("b01c02_visao")),
    )),
    Bloco(2, "O problema", (
        Cena("b02c01_cenario", Visual.TELA, asset="painel_dados.png", alvo_seg=25,
             titulo="O cenário do dia", zoom=(0.17, 0.06, 1.0, 0.94),
             pontos=("Dados sintéticos e reprodutíveis (semente 42) sobre a geografia real de São Paulo.",
                     "36 entregas para UBS, UPA, AME, CAPS, Hospital Dia e 16 pacientes em "
                     "atendimento domiciliar, identificados só por código.",
                     "1.156 kg; 8 entregas críticas, 16 altas e 12 normais.",
                     "6 exigem cadeia fria e 6 são medicamentos controlados da Portaria 344/98."),
             narracao=_n("b02c01_cenario")),
        Cena("b02c02_restricoes", Visual.TITULO, alvo_seg=25,
             titulo="Frota e restrições modeladas",
             topicos=("5 veículos: van refrigerada, van com cofre, van elétrica e duas motos",
                      "Prioridade com prazo: crítica em 2 h, alta em 4 h",
                      "Capacidade de carga e autonomia de cada veículo",
                      "Cadeia fria só em V1 e V4 · controlados só em V1 e V2",
                      "Janelas de recebimento e jornada de 8 horas"),
             pontos=("Frota heterogênea de 5 veículos; a van elétrica tem 70 km de autonomia e as "
                     "motos carregam 25 kg.",
                     "Prioridade com prazo: crítica até 2 horas após a saída, alta até 4 horas.",
                     "Cadeia fria só nos veículos V1 e V4; controlados só em V1 e V2 (cofre).",
                     "Janelas de recebimento e jornada de 8 horas.",
                     "Tensão do problema: oito críticas espalhadas pela cidade, prazo de duas horas "
                     "e só dois veículos refrigerados."),
             narracao=_n("b02c02_restricoes")),
    )),
    Bloco(3, "Ponto de partida: o código base", (
        Cena("b03c01_codigo_base", Visual.CODIGO, asset="legacy/codigo_base_tsp/tsp.py",
             linha_inicial=105, linha_final=130, destaque=(121, 122), alvo_seg=30,
             titulo="Código base: o laço evolutivo do tsp.py",
             pontos=("O código base resolve um TSP: um único caixeiro, distância em pixels, sem "
                     "nenhuma restrição.",
                     "Linha 122: order_crossover(parent1, parent1) — o pai cruza com ele mesmo; o "
                     "filho é uma cópia e não existe recombinação. A linha correta está comentada "
                     "logo acima.",
                     "Outros pontos: a mutação só troca vizinhos, a população inicial é só "
                     "aleatória e o visualizador usa uma função removida do Matplotlib."),
             narracao=_n("b03c01_codigo_base")),
        Cena("b03c02_impacto_base", Visual.TITULO, alvo_seg=20,
             titulo="Partindo do código base",
             topicos=("Bug do crossover corrigido: TSP de 267 km para 221 km (−17%)",
                      "TSP fatiado entre os veículos: 7 violações em média",
                      "e só 31% das entregas críticas no prazo",
                      "", "Conclusão: modelar um VRP com restrições"),
             pontos=("Corrigir o crossover reduz o TSP do código base de 267 para 221 km em média "
                     "(10 sementes, menos 17%).",
                     "Usar a rota única do TSP e fatiá-la entre os veículos gera 7 violações em "
                     "média e só 31% das críticas no prazo.",
                     "Conclusão: o problema precisa ser modelado como roteamento de veículos com "
                     "restrições (VRP)."),
             narracao=_n("b03c02_impacto_base")),
    )),
    Bloco(4, "Representação e função fitness", (
        Cena("b04c01_cromossomo", Visual.FIGURA, asset="00b_cromossomo.png", alvo_seg=25,
             titulo="Representação genética",
             pontos=("Cromossomo: permutação das 36 entregas intercalada com 4 separadores; o "
                     "trecho k é a rota do veículo k.",
                     "Com um único veículo, é exatamente o cromossomo do TSP do código base.",
                     "Toda permutação é uma solução completa e os operadores de permutação "
                     "continuam valendo; o GA decide quantas entregas cada veículo faz movendo "
                     "os separadores."),
             narracao=_n("b04c01_cromossomo")),
        Cena("b04c02_fitness", Visual.CODIGO, asset="src/medroute/problem.py",
             linha_inicial=294, linha_final=325, destaque=(300, 301, 302, 303, 317, 318, 319,
                                                          320, 321, 322, 323, 324),
             alvo_seg=30, titulo="Função fitness (problem.py)",
             pontos=("A fitness é minimizada: quilômetros rodados",
                     "mais o peso da prioridade vezes a hora de chegada (crítica 10, alta 3, normal 1)",
                     "mais o peso vezes os minutos de atraso em relação ao prazo (menor entre o fim "
                     "da janela e o prazo da prioridade)",
                     "mais penalidades de capacidade, autonomia, compatibilidade e jornada: custo "
                     "fixo alto mais um termo proporcional ao excesso.",
                     "Há uma versão rápida e uma detalhada da mesma conta; um teste garante que "
                     "concordam."),
             narracao=_n("b04c02_fitness")),
    )),
    Bloco(5, "Operadores genéticos", (
        Cena("b05c01_ciclo", Visual.FIGURA, asset="00c_ciclo_ga.png", alvo_seg=25,
             titulo="O ciclo evolutivo",
             pontos=("População inicial aleatória mais soluções heurísticas.",
                     "Seleção por torneio; crossover sorteado entre OX, PMX, ERX e BCRC.",
                     "Mutações: troca, inversão, inserção, embaralhamento, prioridade e reparo.",
                     "Elitismo, anti-duplicata e imigrantes quando a população estagna; busca local "
                     "2-opt e relocate no melhor indivíduo."),
             narracao=_n("b05c01_ciclo")),
        Cena("b05c02_bcrc", Visual.CODIGO, asset="src/medroute/ga/operators.py",
             linha_inicial=291, linha_final=314, destaque=(305, 306, 307, 312, 313), alvo_seg=25,
             titulo="Crossover especializado para VRP: BCRC",
             pontos=("BCRC, Best Cost Route Crossover (Ombuki, 2006): herda as rotas do pai 1, "
                     "retira as entregas de uma rota sorteada do pai 2 e reinsere cada uma na "
                     "posição mais barata, respeitando compatibilidade e carga.",
                     "Foi o operador mais importante na ablação."),
             narracao=_n("b05c02_bcrc")),
        Cena("b05c03_mutacoes", Visual.CODIGO, asset="src/medroute/ga/operators.py",
             linha_inicial=382, linha_final=406, destaque=(400, 401, 402, 403, 404, 405),
             alvo_seg=20, titulo="Mutações especializadas: prioridade e reparo",
             pontos=("A mutação de prioridade antecipa uma entrega crítica ou alta dentro da rota.",
                     "A mutação de reparo tira uma entrega de uma rota que viola restrição e a "
                     "reinsere onde é viável — por exemplo, insulina numa moto sem baú térmico "
                     "volta para um veículo refrigerado."),
             narracao=_n("b05c03_mutacoes")),
    )),
    Bloco(6, "O algoritmo genético em execução", (
        Cena("b06c01_terminal", Visual.TERMINAL, asset="terminal_pipeline",
             marcador_inicio="2. OTIMIZAÇÃO", marcador_fim="3. COMPARATIVO", alvo_seg=30,
             titulo="python main.py — otimização",
             pontos=("O pipeline completo roda com python main.py.",
                     "Geração 0: melhor indivíduo ainda inviável; geração 5: primeira solução viável.",
                     "Geração 100: fitness 502; para por paciência após 351 gerações, cerca de 36 mil "
                     "avaliações e 6 segundos.",
                     "Resultado: 253,5 km, 97% das entregas no prazo e zero violações."),
             narracao=_n("b06c01_terminal")),
        Cena("b06c02_evolucao", Visual.EVOLUCAO, alvo_seg=25,
             titulo="Evolução das rotas geração a geração",
             pontos=("Animação de um GA puro partindo de uma população totalmente aleatória (sem "
                     "sementes heurísticas).",
                     "No início as rotas cruzam a cidade e violam restrições; em poucas dezenas de "
                     "gerações se organizam por região e ficam viáveis."),
             narracao=_n("b06c02_evolucao")),
        Cena("b06c03_convergencia", Visual.FIGURA, asset="04_convergencia_ga.png", alvo_seg=15,
             titulo="Convergência",
             pontos=("Escala logarítmica: o melhor indivíduo cai de milhares (penalidades) para "
                     "cerca de 500 em 100 gerações.",
                     "A média da população continua alta de propósito: crossover e mutação "
                     "exploram regiões inviáveis."),
             narracao=_n("b06c03_convergencia")),
    )),
    Bloco(7, "As rotas otimizadas", (
        Cena("b07c01_painel", Visual.TELA, asset="painel_mapa.png", alvo_seg=30,
             titulo="Painel interativo (Streamlit)", zoom=(0.17, 0.33, 0.99, 0.94),
             pontos=("Painel: 253,5 km, 46 km a menos que o processo atual; custo de R$ 1.178, "
                     "399 reais a menos; 97% no prazo, 39 pontos a mais; zero violações.",
                     "Mapa interativo: uma camada por veículo, número da ordem de visita, forma "
                     "pela prioridade e janela com os detalhes de cada entrega."),
             narracao=_n("b07c01_painel")),
        Cena("b07c02_gantt", Visual.FIGURA, asset="05_linha_do_tempo_ga.png", alvo_seg=25,
             titulo="Linha do tempo dos veículos",
             pontos=("A van refrigerada V1 entrega as três críticas com vacinas e trombolítico às "
                     "7h25, 8h15 e 8h58 — antes do prazo das 9h.",
                     "A moto com baú térmico V4 leva três insulinas; a terceira chega às 9h03, 2,5 "
                     "minutos depois do prazo — o único atraso do dia.",
                     "Todos os veículos voltam até 12h43."),
             narracao=_n("b07c02_gantt")),
        Cena("b07c03_ocupacao", Visual.FIGURA, asset="07_ocupacao_frota.png", alvo_seg=15,
             titulo="Ocupação da frota",
             pontos=("A moto V4 usa 98% da autonomia e 96% da carga: está no limite.",
                     "As restrições estão ativas — não são decorativas."),
             narracao=_n("b07c03_ocupacao")),
    )),
    Bloco(8, "Comparativo com outras abordagens", (
        Cena("b08c01_atual", Visual.FIGURA, asset="02_mapa_rotas_processo_atual.png", alvo_seg=25,
             titulo="Processo atual (despachante)",
             pontos=("Processo atual simulado: o despachante atende primeiro as urgências e depois "
                     "o mais próximo.",
                     "Resultado: 299,5 km, R$ 1.577, só 58% no prazo e 37,5% das críticas no prazo; "
                     "último retorno às 14h57.",
                     "O GA economiza 46 km (15%), 399 reais (25%) e 4,3 horas de rota."),
             narracao=_n("b08c01_atual")),
        Cena("b08c02_comparativo", Visual.FIGURA, asset="10_comparativo_metodos.png", alvo_seg=35,
             titulo="10 abordagens, mesmo cenário, mesma avaliação",
             pontos=("Dez execuções por método estocástico.",
                     "GA: fitness média 504,7 com desvio de 4,7. Simulated Annealing: 520,7 com "
                     "desvio de 48,5 — sem diferença estatística na mediana (Mann-Whitney, p = 0,49), "
                     "mas o GA é dez vezes mais estável.",
                     "OR-Tools roda menos km (225), mas atende as críticas mais tarde porque não "
                     "modela o termo de prioridade: fitness 518.",
                     "As heurísticas construtivas e o TSP do código base ficam com atrasos e "
                     "violações."),
             narracao=_n("b08c02_comparativo")),
        Cena("b08c03_ablacao", Visual.FIGURA, asset="12_ablacao_ga.png", alvo_seg=30,
             titulo="Ablação do algoritmo genético", zoom=(0.0, 0.0, 1.0, 0.62),
             pontos=("21 configurações com 10 sementes cada.",
                     "Crossover BCRC: 502; OX: 754; PMX: 774; ERX: 3.316 — o ERX embaralha os "
                     "separadores e só metade das soluções é viável.",
                     "Torneio é a melhor seleção; truncamento, a seleção original do código base, "
                     "é a pior.",
                     "A configuração do código base nunca chega a uma solução viável (6.013)."),
             narracao=_n("b08c03_ablacao")),
        Cena("b08c04_escala", Visual.FIGURA, asset="14_escalabilidade.png", alvo_seg=20,
             titulo="Escalabilidade",
             pontos=("De 20 a 90 entregas, GA e Simulated Annealing ficam a até 3% do melhor "
                     "resultado conhecido; OR-Tools, de 3% a 17% no nosso objetivo.",
                     "O tempo do GA cresce até cerca de 50 segundos com 90 entregas."),
             narracao=_n("b08c04_escala")),
    )),
    Bloco(9, "Integração com LLM", (
        Cena("b09c01_fluxo", Visual.FIGURA, asset="00d_fluxo_llm.png", alvo_seg=30,
             titulo="Como a LLM foi integrada",
             pontos=("OpenRouter com um modelo gratuito: Nemotron 3 Ultra, da NVIDIA (a conta só "
                     "libera provedores NVIDIA e Z-AI).",
                     "A LLM não calcula nada: recebe um JSON com os números prontos.",
                     "Prompt com papel, regras, dados delimitados, esqueleto de saída e um exemplo; "
                     "temperatura 0,2 para instruções e 0,4 para relatórios.",
                     "Cache em disco por causa da cota de 50 requisições por dia, modo offline e "
                     "guardrails que dão uma nota de 0 a 100 a cada resposta."),
             narracao=_n("b09c01_fluxo")),
        Cena("b09c02_instrucoes", Visual.DOCUMENTO, asset="instrucoes_V4.md", alvo_seg=25,
             titulo="Instruções para o motorista da Moto 01 (V4)",
             pontos=("Instruções geradas pela LLM para o motorista: checklist antes de sair, "
                     "paradas na ordem com horário, cuidados de cadeia fria, alerta do atraso "
                     "previsto e o que fazer em caso de imprevisto.",
                     "Nota de fidelidade: 100."),
             narracao=_n("b09c02_instrucoes")),
        Cena("b09c03_relatorio", Visual.TELA, asset="painel_llm.png", alvo_seg=20,
             titulo="Relatório diário no painel (aba Assistente)", zoom=(0.57, 0.04, 1.0, 0.84),
             pontos=("O relatório diário compara o plano com o processo atual numa tabela.",
                     "Aponta o atraso da entrega E25 e a autonomia da moto V4 no limite."),
             narracao=_n("b09c03_relatorio")),
        Cena("b09c04_sugestoes", Visual.DOCUMENTO, asset="sugestoes_melhoria.md", alvo_seg=30,
             titulo="Sugestões de melhoria (com simulação “e se”)",
             pontos=("As sugestões partem de padrões medidos e de simulações 'e se', em que o "
                     "sistema re-otimiza o dia com a mudança proposta.",
                     "Instalar baú térmico também na Moto 02: críticas no prazo de 87,5% para 100%, "
                     "34,9 km e 77 reais a menos.",
                     "Operar sem a van elétrica piora: 275,8 km, 3 atrasos e uma violação — manter."),
             narracao=_n("b09c04_sugestoes")),
        Cena("b09c05_chat", Visual.CHAT, asset="perguntas_e_respostas.md", alvo_seg=30,
             titulo="Perguntas em linguagem natural",
             pontos=("Perguntas sobre as rotas: quem leva a insulina do paciente PD-05 (V4, parada "
                     "3, 9h03), qual crítica corre risco, quais entregas são controladas.",
                     "Pergunta-armadilha: o telefone de um paciente — a resposta é que a informação "
                     "não está disponível no plano."),
             narracao=_n("b09c05_chat")),
        Cena("b09c06_avaliacao", Visual.TITULO, alvo_seg=30,
             titulo="Avaliação da qualidade da LLM",
             topicos=("Guardrails: paradas, ordem, horários, IDs, números e requisitos",
                      "v1 → ceftriaxona tratada como controlado: nova regra no prompt",
                      "v2 → CAPS listado como controlado no chat: índices pré-calculados",
                      "v3 → nota média {NOTA_V3}/100"),
             pontos=("Cada resposta é conferida contra os dados: cobertura e ordem das paradas, "
                     "horários e IDs inventados, números não rastreáveis e requisitos inventados.",
                     "Na versão 1, a avaliação pegou a LLM chamando ceftriaxona de medicamento "
                     "controlado; entrou uma regra nova no prompt.",
                     "Na versão 2, pegou um CAPS listado como controlado no chat; entraram índices "
                     "pré-calculados por requisito.",
                     "Na versão 3, a nota média ficou em {NOTA_V3} de 100."),
             narracao=_n("b09c06_avaliacao")),
    )),
    Bloco(10, "Semana operacional", (
        Cena("b10c01_semana", Visual.FIGURA, asset="09_semana_km.png", alvo_seg=25,
             titulo="Semana simulada: processo atual × MedRoute",
             pontos=("Semana simulada de segunda a sexta, de 30 a 38 entregas por dia.",
                     "O MedRoute economiza 319 km (24%), 1.845 reais, 18,8 horas e 104 kg de CO2.",
                     "Entregas no prazo sobem de 57,6% para 98,8%.",
                     "A LLM escreve o relatório semanal a partir desses totais."),
             narracao=_n("b10c01_semana")),
    )),
    Bloco(11, "Engenharia", (
        Cena("b11c01_api", Visual.TELA, asset="api_docs.png", alvo_seg=20,
             titulo="API REST (FastAPI) — documentação automática",
             pontos=("API REST com documentação automática: otimizar, comparar, mapa, instruções, "
                     "relatório, sugestões e perguntas.",
                     "Os endpoints de LLM aceitam os modos auto, llm e offline."),
             narracao=_n("b11c01_api")),
        Cena("b11c02_testes", Visual.TERMINAL, asset="terminal_pytest", linhas_finais=3,
             marcador_inicio="test_api.py", alvo_seg=25,
             titulo="python -m pytest -v — {N_TESTES} testes",
             pontos=("{N_TESTES} testes automatizados passando.",
                     "Cobrem as contas exatas da fitness, a concordância das duas implementações, "
                     "a validade dos operadores, a regressão do bug do código base, o GA, as "
                     "heurísticas, a LLM com HTTP simulado (sem rede), os guardrails, a API e as "
                     "visualizações."),
             narracao=_n("b11c02_testes")),
        Cena("b11c03_arvore", Visual.ARVORE, alvo_seg=15,
             titulo="Organização do projeto",
             pontos=("Pacote src/medroute com os módulos ga, llm, viz e api.",
                     "Scripts de experimentos, avaliação da LLM, diagramas, notebook e vídeo; "
                     "documentação em docs; ambiente virtual e pyproject compatível com Poetry."),
             narracao=_n("b11c03_arvore")),
    )),
    Bloco(12, "Encerramento", (
        Cena("b12c01_resultados", Visual.TITULO, alvo_seg=25,
             titulo="Resultados",
             topicos=("Rotas viáveis: zero violações e 97% das entregas no prazo",
                      "Dia: −15% de km e −25% de custo · semana: −24% de km",
                      "GA robusto: 504,7 ± 4,7 em 10 execuções",
                      "LLM auditada: nota média {NOTA_V3}/100 nos guardrails"),
             pontos=("Rotas viáveis, sem violações e com 97% das entregas no prazo.",
                     "Menos 15% de km e 25% de custo no dia; menos 24% de km na semana.",
                     "GA robusto: 504,7 mais ou menos 4,7 em dez execuções.",
                     "LLM auditada automaticamente, com nota média {NOTA_V3} de 100."),
             narracao=_n("b12c01_resultados")),
        Cena("b12c02_proximos", Visual.TITULO, alvo_seg=20,
             titulo="Limitações e próximos passos",
             topicos=("Dados sintéticos e distâncias estimadas → integrar OSRM ou Google Maps",
                      "Uma viagem por veículo → múltiplas viagens e reotimização em tempo real",
                      "LLM gratuita com fila → modelo pago ou local em produção",
                      "Validar com a equipe de logística do hospital"),
             pontos=("Limitações: dados sintéticos e distâncias estimadas por haversine vezes "
                     "1,35; próximos passos: integrar um roteador real.",
                     "Uma viagem por veículo: evoluir para múltiplas viagens e reotimização em "
                     "tempo real.",
                     "A LLM gratuita tem fila e cota: em produção, modelo pago ou local.",
                     "Validar com a equipe de logística do hospital. Agradecimento final."),
             narracao=_n("b12c02_proximos")),
    )),
)


# ---------------------------------------------------------------------------
# Valores lidos dos resultados (não ficam "chumbados" no roteiro)
# ---------------------------------------------------------------------------
def _nota_media(versao: str) -> str:
    import json

    arq = LLM_DIR / f"avaliacao_{versao}.json"
    try:
        notas = [float(x["nota"]) for x in json.loads(arq.read_text(encoding="utf-8"))]
        return f"{sum(notas) / len(notas):.1f}".replace(".", ",")
    except (OSError, ValueError, KeyError, ZeroDivisionError):
        return "?"


def _n_testes() -> str:
    """Número de testes que passaram na execução capturada do pytest."""
    import re

    arq = CACHE_DIR / "terminal_pytest.txt"
    try:
        m = re.findall(r"(\d+) passed", arq.read_text(encoding="utf-8"))
        return m[-1] if m else "?"
    except OSError:
        return "?"


def _por_extenso(n: str) -> str:
    """Número inteiro (até 999) por extenso, para a narração."""
    try:
        v = int(n)
    except ValueError:
        return n
    un = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
          "onze", "doze", "treze", "catorze", "quinze", "dezesseis", "dezessete", "dezoito",
          "dezenove"]
    dz = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta",
          "noventa"]
    ct = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos",
          "setecentos", "oitocentos", "novecentos"]
    if v == 100:
        return "cem"
    partes = []
    if v >= 100:
        partes.append(ct[v // 100])
        v %= 100
    if v >= 20:
        partes.append(dz[v // 10] + (f" e {un[v % 10]}" if v % 10 else ""))
    elif v:
        partes.append(un[v])
    return " e ".join(partes)


def _nota_falada(nota: str) -> str:
    if nota == "?":
        return nota
    inteiro, _, dec = nota.partition(",")
    return f"{_por_extenso(inteiro)} vírgula {_por_extenso(dec)}" if dec and dec != "0" else _por_extenso(inteiro)


def _substituir(texto: str, falado: bool = False) -> str:
    nota, n = _nota_media("v3"), _n_testes()
    if falado:
        return texto.replace("{NOTA_V3}", _nota_falada(nota)).replace("{N_TESTES}", _por_extenso(n))
    return texto.replace("{NOTA_V3}", nota).replace("{N_TESTES}", n)


def _preencher(c: Cena) -> Cena:
    from dataclasses import replace

    return replace(c, titulo=_substituir(c.titulo), subtitulo=_substituir(c.subtitulo),
                   topicos=tuple(_substituir(x) for x in c.topicos),
                   pontos=tuple(_substituir(x) for x in c.pontos),
                   narracao=_substituir(c.narracao, falado=True))


BLOCOS = tuple(Bloco(b.numero, b.titulo, tuple(_preencher(c) for c in b.cenas)) for b in BLOCOS)


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def todas_as_cenas(blocos: tuple[Bloco, ...] = BLOCOS) -> list[tuple[Bloco, Cena]]:
    return [(b, c) for b in blocos for c in b.cenas]


def filtrar_blocos(numeros: list[int] | None) -> tuple[Bloco, ...]:
    if not numeros:
        return BLOCOS
    escolhidos = tuple(b for b in BLOCOS if b.numero in set(numeros))
    if not escolhidos:
        raise SystemExit(f"Nenhum bloco corresponde a {numeros}.")
    return escolhidos


def contar_palavras(blocos: tuple[Bloco, ...] = BLOCOS) -> int:
    return sum(len(c.narracao.split()) for _, c in todas_as_cenas(blocos))


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    alvo = sum(c.alvo_seg for _, c in todas_as_cenas())
    print(f"{len(BLOCOS)} blocos, {len(todas_as_cenas())} cenas, alvo {alvo / 60:.1f} min, "
          f"{contar_palavras()} palavras narradas (~{contar_palavras() / 155:.1f} min)")
    for b in BLOCOS:
        print(f"  {b.numero:2d}. {b.titulo:38s} {sum(c.alvo_seg for c in b.cenas):4d}s  "
              f"{sum(len(c.narracao.split()) for c in b.cenas):4d} palavras")
