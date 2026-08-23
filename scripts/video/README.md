# Gerador automatizado do vídeo de demonstração

Produz, com **um único comando**, o vídeo de entrega do Tech Challenge — Fase 1:
um MP4 1920x1080 a 30 fps, com narração em pt-BR, mais o arquivo de legendas
`.srt` pronto para subir junto no YouTube.

```
video/tech_challenge_fase1_demo.mp4
video/tech_challenge_fase1_demo.srt
```

O conteúdo vem de `docs/ROTEIRO_VIDEO.md`, transcrito para dados em
`roteiro.py`. A saída de terminal exibida é **real**, capturada da execução de
verdade de `main.py`, `pytest` e `main_vision.py` — nada é encenado.

---

## Como rodar

Sempre com o Python do `.venv` do projeto:

```powershell
.venv\Scripts\python.exe scripts\video\gerar_video.py
```

Na primeira execução o script roda `main.py`, `pytest` e `main_vision.py` para
capturar a saída (≈ 2 min), gera 36 narrações pelo edge-tts (≈ 3 min, precisa
de internet) e codifica o vídeo (≈ 6 min). Nas execuções seguintes, tudo que
não mudou vem do cache.

### Dependências

O `.venv` do projeto já tem tudo, exceto dois pacotes que o gerador instala
uma vez:

```powershell
.venv\Scripts\python.exe -m pip install edge-tts imageio-ffmpeg
```

* **edge-tts** — vozes neurais em pt-BR (usa a rede).
* **imageio-ffmpeg** — traz um ffmpeg estático dentro do venv. **Não é preciso
  ter ffmpeg no PATH nem instalar nada com winget/admin.**

Os frames são desenhados com Pillow. Não há browser, Selenium ou editor de
vídeo envolvido.

### Flags

| Flag | O que faz |
|---|---|
| *(nenhuma)* | Vídeo completo, voz padrão. |
| `--voz pt-BR-FranciscaNeural` | Troca a voz (veja abaixo). |
| `--rate "+10%"` | Acelera ou desacelera a fala. |
| `--recapturar` | Re-executa `main.py`, `pytest` e `main_vision.py` em vez de usar o cache. |
| `--pular-vision` | Não roda `main_vision.py` (o mais lento); reaproveita o cache. |
| `--so-audio` | Só gera a narração e o `.srt`. Serve para **revisar o texto ouvindo**, antes de gastar tempo codificando. |
| `--previa` | Gera 1 PNG por cena em `_cache/previa/` e sai. Sem TTS, sem vídeo — é o jeito barato de conferir o visual. |
| `--blocos 6,7,8` | Renderiza só alguns blocos. A saída ganha o sufixo `_parcial`. Ótimo para iterar num bloco específico. |
| `--tts-offline` | Usa o TTS do Windows em vez do edge-tts (sem internet). |
| `--refazer-audio` | Ignora o cache de áudio e regera todas as narrações. |
| `--manter-clipes` | Não apaga os clipes por cena em `_cache/clipes/`. |

O script imprime a duração de cada bloco, o total, e **avisa se passar de 15
minutos**, dizendo quais blocos cortar primeiro.

### Ciclo de trabalho recomendado

```powershell
# 1. conferir o visual (segundos, sem rede)
.venv\Scripts\python.exe scripts\video\gerar_video.py --previa

# 2. conferir o texto narrado e a duração total (minutos, com rede)
.venv\Scripts\python.exe scripts\video\gerar_video.py --so-audio

# 3. iterar num bloco específico
.venv\Scripts\python.exe scripts\video\gerar_video.py --blocos 7

# 4. render final
.venv\Scripts\python.exe scripts\video\gerar_video.py
```

---

## Arquitetura

| Módulo | Responsabilidade |
|---|---|
| `roteiro.py` | O roteiro como dado: 11 blocos, 36 cenas, texto narrado e tela. **É aqui que se edita o conteúdo.** |
| `captura.py` | Executa os comandos do projeto e grava o stdout real em `_cache/*.txt`. |
| `visuais.py` | Desenha os frames com Pillow (título, figura, terminal, código, árvore). |
| `narracao.py` | TTS pt-BR, cache por hash, medição da duração real do áudio. |
| `montagem.py` | ffmpeg: um clipe por cena, concatenação, `.srt`. |
| `gerar_video.py` | Orquestra tudo e imprime o relatório. |

**A duração de cada cena vem da medição do MP3 narrado.** Não existe duração
fixa em lugar nenhum: escrever uma frase a mais alonga a cena e o vídeo;
apagar uma frase encurta. É por isso que o roteiro é a única fonte de verdade.

Cenas estáticas viram **uma** imagem que o ffmpeg segura por `-loop 1 -t`; só
as cenas de terminal são geradas frame a frame, e os frames vão direto para o
stdin do ffmpeg — nenhum PNG intermediário toca o disco.

---

## Como editar o roteiro

Tudo em `roteiro.py`, na tupla `BLOCOS`. Cada `Cena` tem:

```python
Cena(
    id="b07c03_tradeoff",             # id estável: nomeia os arquivos de cache
    visual=Visual.FIGURA,             # titulo | figura | terminal | codigo | arvore
    asset="04_matriz_confusao_regressao_logistica.png",
    titulo="Matriz de confusão — Regressão Logística",
    legenda="40 de 42 malignos detectados · 2 falsos negativos",
    narracao="O Random Forest empatou em accuracy e teve a melhor área sob a curva...",
)
```

Regras do texto de `narracao`:

* **sem markdown** — o TTS leria `**`, crases e hifens de lista em voz alta;
* **números por extenso** quando a leitura mecânica ficaria ruim: escreva
  `"noventa e cinco vírgula dois por cento"`, não `"95,2%"`;
* **siglas soletradas**: `"Erre O Cê"`, `"área sob a curva"` em vez de `ROC-AUC`.

Mudou o texto de uma cena? Só o áudio dela é regerado (o cache é indexado por
hash do texto + voz). Mudou o `id`? Regera aquela cena e deixa o áudio antigo
órfão em `_cache/audio/` — apague à mão se incomodar.

### Por tipo de tela

* **`titulo`** — preencha `titulo`, `subtitulo` e `topicos` (tupla de strings;
  string vazia vira um respiro).
* **`figura`** — `asset` é o nome do PNG dentro de `reports/figures/`.
* **`terminal`** — `asset` é o id da captura (`terminal_main`,
  `terminal_pytest`, `terminal_vision`). Recorte o trecho com
  `marcador_inicio` / `marcador_fim` (busca por conteúdo, resistente a
  mudanças no número das linhas) ou com `linha_inicial` / `linha_final`.
  `linhas_finais=N` anexa as N últimas linhas do arquivo depois de um `[...]`
  visível — usado no pytest para mostrar o veredito sem exibir o bloco de
  *warnings* de bibliotecas de terceiros.
* **`codigo`** — `asset` é o caminho do `.py` relativo à raiz do projeto;
  `linha_inicial` / `linha_final` recortam e `destaque=(63, 64, 65)` pinta as
  linhas de amarelo.
* **`arvore`** — não precisa de `asset`; a árvore é lida do disco de verdade.
  Ajuste `_IGNORAR_DIRS`, `_COLAPSAR` e `_COMENTARIOS_ARVORE` em `visuais.py`.

---

## Como trocar a voz

```powershell
.venv\Scripts\python.exe scripts\video\gerar_video.py --voz pt-BR-FranciscaNeural
```

Vozes pt-BR sugeridas: `pt-BR-AntonioNeural` (masculina, padrão) e
`pt-BR-FranciscaNeural` (feminina). Para listar todas as disponíveis:

```powershell
.venv\Scripts\python.exe scripts\video\narracao.py
```

Trocar a voz invalida o cache inteiro (o hash inclui a voz), então o TTS roda
de novo para as 36 cenas — cerca de 3 minutos.

Sem internet, `--tts-offline` usa o `System.Speech.Synthesis.SpeechSynthesizer`
do Windows via PowerShell. **A qualidade é bem inferior** (voz concatenativa,
prosódia pobre, sem os limites de sentença que dão precisão ao `.srt` — nesse
modo os tempos das legendas são estimados pelo tamanho de cada frase). Use só
como último recurso.

---

## Como substituir um bloco por gravação própria

O gerador não faz webcam nem captura de tela ao vivo. Se você quiser gravar
um bloco com a própria voz e a própria tela — a abertura, por exemplo:

1. **Gere o vídeo sem o bloco**, listando os demais:

   ```powershell
   .venv\Scripts\python.exe scripts\video\gerar_video.py --blocos 2,3,4,5,6,7,8,9,10,11
   ```

   A saída sai como `tech_challenge_fase1_demo_parcial.mp4`.

2. **Grave seu bloco** em 1920x1080 a 30 fps (OBS, Xbox Game Bar, Loom...).

3. **Junte os dois** com o ffmpeg que já veio no venv. O caminho do binário:

   ```powershell
   .venv\Scripts\python.exe -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
   ```

   Como a gravação externa quase certamente tem codec/áudio diferentes,
   re-encode em vez de usar `-c copy`:

   ```powershell
   & $FFMPEG -i meu_bloco.mp4 -i video\tech_challenge_fase1_demo_parcial.mp4 `
     -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" `
     -map "[v]" -map "[a]" -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac saida.mp4
   ```

4. **Ajuste o `.srt`**: os tempos do bloco removido saíram junto, então os
   demais precisam ser deslocados pela duração da sua gravação. Um editor de
   legendas (Subtitle Edit, ou o próprio editor do YouTube) resolve em um
   minuto.

Alternativa mais simples, se você só quer a **sua voz** e não a sua tela:
mantenha os visuais gerados, rode `--so-audio` para ver o texto de cada cena,
grave o áudio você mesmo e substitua os arquivos em `_cache/audio/`
mantendo os nomes (`b01c01_abertura.mp3`, ...). Apague o `.json` ao lado de
cada um para o gerador remedir a duração.

---

## Limitações conhecidas

Sendo honesto sobre o que este gerador **não** entrega:

* **A narração é sintética.** As vozes neurais da Microsoft são boas, mas
  soam mecânicas em trechos com muitos números seguidos e em siglas. O texto
  já escreve números por extenso justamente para reduzir isso, mas não
  elimina. Uma narração humana soaria melhor.
* **Não há webcam nem cursor.** O enunciado permite (a câmera é opcional), mas
  o vídeo é 100% "slides + terminal", sem presença humana na tela.
* **As cenas de figura são estáticas.** Sem zoom, sem pan, sem destacar com o
  mouse a região da figura que a narração está comentando. Em cenas longas —
  há algumas de ~30 s — a tela fica parada bastante tempo. Se incomodar,
  quebre a cena em duas no `roteiro.py`, cada uma com sua própria figura ou
  legenda.
* **A "digitação" do terminal é uma reconstrução do ritmo, não um replay.**
  O texto exibido é real, mas ele aparece numa cadência linear ao longo da
  narração, não no tempo em que o programa de fato levou para imprimir cada
  linha. Um `main.py` que trava 20 s no SHAP aparece aqui como um fluxo
  constante.
* **As transições são um fade simples para o fundo**, apenas entre blocos.
  Não há cross-fade nem qualquer efeito entre cenas do mesmo bloco.
* **Precisa de internet** para o TTS de qualidade. O modo offline funciona,
  mas o resultado é audivelmente pior.
* **A árvore de arquivos é gerada do disco de verdade**, então ela muda se
  você criar ou apagar arquivos. Se ela crescer demais, o renderizador
  encolhe a fonte e, no limite, trunca com `...` — ajuste `_COLAPSAR` em
  `visuais.py` antes de chegar nesse ponto.

## O que fica em cache

`scripts/video/_cache/` (ignorado pelo git):

```
terminal_main.txt      saída real de python main.py
terminal_pytest.txt    saída real de python -m pytest -v
terminal_vision.txt    saída real de python main_vision.py
audio/                 um .mp3 + um .json (duração e tempos) por cena
previa/                PNGs do modo --previa
clipes/                clipes por cena (apagados após a concatenação)
```

Para começar do zero: apague `_cache/` inteiro e rode de novo.
