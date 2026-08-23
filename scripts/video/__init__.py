"""
Gerador automatizado do vídeo de demonstração do Tech Challenge — Fase 1.

Os módulos são pensados para rodar como scripts (``python scripts/video/
gerar_video.py``), com o próprio diretório no ``sys.path``, e por isso se
importam de forma plana (``import roteiro``, ``import visuais``, ...).

Divisão de responsabilidades:

``roteiro``
    O roteiro como dado: onze blocos, suas cenas, o texto narrado e a tela.
``captura``
    Executa ``main.py`` / ``pytest`` / ``main_vision.py`` e guarda a saída real.
``visuais``
    Desenha os frames com Pillow (título, figura, terminal, código, árvore).
``narracao``
    Text-to-speech em pt-BR (edge-tts), com cache e medição de duração.
``montagem``
    ffmpeg (via imageio-ffmpeg): clipes por cena, concatenação e ``.srt``.
``gerar_video``
    Orquestra tudo com um único comando.
"""

__all__ = ["roteiro", "captura", "visuais", "narracao", "montagem"]
