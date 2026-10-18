"""
Gerador automatizado do vídeo de demonstração — Tech Challenge Fase 2 (MedRoute).

Evolução do gerador da Fase 1. Módulos importados de forma plana (o próprio
diretório entra no ``sys.path``):

``roteiro``     o roteiro como dado (blocos, cenas, texto narrado, tela)
``captura``     roda o sistema de verdade e guarda a saída do terminal
``telas``       captura telas reais do painel, da API e do mapa (Edge via CDP)
``evolucao``    quadros da evolução do GA (rotas + curva de convergência)
``visuais``     desenha os quadros com Pillow (inclui Markdown, chat e zoom)
``narracao``    voz pt-BR (edge-tts), cache e medição de duração
``montagem``    ffmpeg: clipes, concatenação e legendas .srt
``rascunho_llm`` rascunho da narração pela LLM gratuita da OpenRouter
``gerar_video`` orquestra tudo com um comando
"""
