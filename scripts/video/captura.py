"""
Captura da saída REAL do sistema.

Este módulo executa os comandos do projeto de verdade (``main.py``,
``pytest``, ``main_vision.py``) e grava o ``stdout`` bruto em
``scripts/video/_cache/``. O vídeo mostra esses arquivos — nunca texto
inventado. Se o pipeline mudar, basta recapturar e o vídeo acompanha.

Cuidados de Windows tratados aqui:

* ``encoding="utf-8"`` + ``errors="replace"`` na leitura dos pipes;
* ``PYTHONIOENCODING=utf-8`` no ambiente do subprocesso — sem isso o console
  do Windows usa cp1252 e a saída sai corrompida (ex.: ``PIPELINE CONCLU?DO``);
* ``PYTHONUTF8=1`` como cinto de segurança extra.

Todas as capturas são cacheadas: se o ``.txt`` já existe e ``recapturar``
é falso, o comando não roda de novo (``main_vision.py`` leva minutos).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from roteiro import CACHE_DIR, PROJECT_ROOT

# Interpretador usado nos subprocessos: o mesmo que roda este script, ou seja,
# o Python do .venv do projeto. Evita depender de "python" estar no PATH.
PYTHON = sys.executable


@dataclass(frozen=True)
class Comando:
    """Um comando capturável.

    Attributes
    ----------
    id:
        Identificador usado pelas cenas do roteiro (``asset`` das cenas
        ``terminal``). Vira o nome do arquivo: ``<id>.txt``.
    argv:
        Argumentos passados ao Python do venv.
    rotulo:
        Como o comando aparece escrito no prompt falso do terminal renderizado.
    lento:
        Marca comandos caros; usados para decidir se podem ser pulados.
    """

    id: str
    argv: tuple[str, ...]
    rotulo: str
    lento: bool = False


COMANDOS: dict[str, Comando] = {
    "terminal_main": Comando(
        id="terminal_main",
        argv=("main.py",),
        rotulo="python main.py",
    ),
    "terminal_pytest": Comando(
        id="terminal_pytest",
        argv=("-m", "pytest", "-v"),
        rotulo="python -m pytest -v",
    ),
    "terminal_vision": Comando(
        id="terminal_vision",
        argv=("main_vision.py",),
        rotulo="python main_vision.py",
        lento=True,
    ),
}


def _env_utf8() -> dict[str, str]:
    """Ambiente do subprocesso forçando UTF-8 na saída padrão."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # Desliga cores ANSI do pytest: o renderizador de terminal é texto puro e
    # os códigos de escape apareceriam como lixo na tela.
    env["NO_COLOR"] = "1"
    env["PY_COLORS"] = "0"
    return env


def caminho_captura(cmd_id: str) -> Path:
    """Caminho do ``.txt`` de uma captura."""
    return CACHE_DIR / f"{cmd_id}.txt"


def capturar(cmd_id: str, recapturar: bool = False, verboso: bool = True) -> Path:
    """Executa (ou reaproveita do cache) um comando e devolve o ``.txt``.

    Parameters
    ----------
    cmd_id:
        Chave em :data:`COMANDOS`.
    recapturar:
        Se ``True``, ignora o cache e roda o comando de novo.
    """
    cmd = COMANDOS[cmd_id]
    destino = caminho_captura(cmd_id)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if destino.exists() and not recapturar:
        if verboso:
            print(f"  [cache] {cmd.rotulo}  ->  {destino.name}")
        return destino

    if verboso:
        print(f"  [rodando] {cmd.rotulo} ...", flush=True)
    inicio = time.perf_counter()
    proc = subprocess.run(
        [PYTHON, *cmd.argv],
        cwd=PROJECT_ROOT,
        env=_env_utf8(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    decorrido = time.perf_counter() - inicio

    saida = proc.stdout or ""
    if proc.returncode != 0:
        # Mesmo com falha gravamos o que veio, mas avisamos alto e bom som:
        # mostrar saída de erro no vídeo seria pior do que falhar aqui.
        saida += "\n" + (proc.stderr or "")
        print(
            f"  [ATENCAO] '{cmd.rotulo}' terminou com codigo {proc.returncode}. "
            f"A captura foi gravada mesmo assim: {destino}",
            file=sys.stderr,
        )

    destino.write_text(_limpar(saida), encoding="utf-8")
    if verboso:
        n_linhas = len(saida.splitlines())
        print(f"  [ok] {cmd.rotulo}  ->  {destino.name} "
              f"({n_linhas} linhas, {decorrido:.1f}s)")
    return destino


def _limpar(texto: str) -> str:
    """Normaliza a saída para renderização: sem CR, sem tabs, sem ANSI."""
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = texto.replace("\t", "    ")
    # Remoção defensiva de sequências ANSI (se alguma escapar do NO_COLOR).
    import re

    texto = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", texto)
    return texto


def ler_captura(cmd_id: str) -> list[str]:
    """Lê uma captura já feita como lista de linhas (sem ``\\n``)."""
    caminho = caminho_captura(cmd_id)
    if not caminho.exists():
        raise FileNotFoundError(
            f"Captura '{cmd_id}' não existe em {caminho}. "
            "Rode o gerador sem --pular-vision ou com --recapturar."
        )
    return caminho.read_text(encoding="utf-8").splitlines()


def capturar_tudo(
    recapturar: bool = False,
    incluir_vision: bool = True,
    verboso: bool = True,
) -> dict[str, Path]:
    """Garante que todas as capturas necessárias existam.

    ``main_vision.py`` é opcional porque leva minutos; se for pulado e não
    houver cache, um placeholder honesto é gravado avisando que a captura
    não foi feita (nunca uma saída inventada).
    """
    resultado: dict[str, Path] = {}
    for cmd_id, cmd in COMANDOS.items():
        if cmd.lento and not incluir_vision and not caminho_captura(cmd_id).exists():
            _placeholder(cmd_id, cmd)
            resultado[cmd_id] = caminho_captura(cmd_id)
            continue
        if cmd.lento and not incluir_vision:
            if verboso:
                print(f"  [pulado] {cmd.rotulo} (cache reaproveitado)")
            resultado[cmd_id] = caminho_captura(cmd_id)
            continue
        resultado[cmd_id] = capturar(cmd_id, recapturar=recapturar, verboso=verboso)
    return resultado


def _placeholder(cmd_id: str, cmd: Comando) -> None:
    """Grava um aviso explícito quando uma captura lenta foi pulada."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    caminho_captura(cmd_id).write_text(
        f"$ {cmd.rotulo}\n"
        "\n"
        "[captura nao realizada nesta execucao]\n"
        f"Rode:  python scripts/video/gerar_video.py --recapturar\n"
        "para executar o comando de verdade e gravar a saida real.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":  # pragma: no cover - utilitário de linha de comando
    import argparse

    parser = argparse.ArgumentParser(description="Captura a saída real do projeto.")
    parser.add_argument("--recapturar", action="store_true")
    parser.add_argument("--pular-vision", action="store_true")
    args = parser.parse_args()
    capturar_tudo(recapturar=args.recapturar, incluir_vision=not args.pular_vision)
