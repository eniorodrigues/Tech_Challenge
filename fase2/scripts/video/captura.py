"""
Captura da saída REAL do sistema para as cenas de terminal.

Executa os comandos do projeto de verdade e grava o ``stdout`` em
``scripts/video/_cache/<id>.txt``. O vídeo mostra esses arquivos — nunca texto
inventado. O pipeline usa a LLM em modo ``auto``: com o cache das respostas já
geradas, nenhuma requisição nova é feita.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from roteiro import CACHE_DIR, PROJECT_ROOT

PYTHON = sys.executable


@dataclass(frozen=True)
class Comando:
    id: str
    argv: tuple[str, ...]
    rotulo: str
    arquivo: str = ""      # se preenchido, copia este arquivo em vez de executar


COMANDOS: dict[str, Comando] = {
    "terminal_pipeline": Comando("terminal_pipeline", ("main.py",), "python main.py"),
    "terminal_pytest": Comando("terminal_pytest", ("-m", "pytest", "-v", "-p", "no:cacheprovider"),
                               "python -m pytest -v"),
    "terminal_experimentos": Comando("terminal_experimentos", (), "python scripts/run_experiments.py",
                                     arquivo="reports/experimentos/saida_experimentos.txt"),
}


def _env_utf8() -> dict[str, str]:
    env = os.environ.copy()
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "NO_COLOR": "1", "PY_COLORS": "0",
                "MPLBACKEND": "Agg"})
    return env


def caminho_captura(cmd_id: str) -> Path:
    return CACHE_DIR / f"{cmd_id}.txt"


def _limpar(texto: str) -> str:
    texto = texto.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    texto = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", texto)
    # Caminho absoluto da máquina não interessa ao vídeo.
    return texto.replace(str(PROJECT_ROOT) + os.sep, "").replace(str(PROJECT_ROOT), "fase2")


def capturar(cmd_id: str, recapturar: bool = False) -> Path:
    cmd = COMANDOS[cmd_id]
    destino = caminho_captura(cmd_id)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if destino.exists() and not recapturar:
        print(f"  [cache] {cmd.rotulo}")
        return destino
    if cmd.arquivo:
        origem = PROJECT_ROOT / cmd.arquivo
        if not origem.exists():
            raise SystemExit(f"{origem} não existe — rode {cmd.rotulo} antes.")
        shutil.copyfile(origem, destino)
        destino.write_text(_limpar(destino.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"  [arquivo] {cmd.rotulo} <- {cmd.arquivo}")
        return destino
    print(f"  [rodando] {cmd.rotulo} ...", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run([PYTHON, *cmd.argv], cwd=PROJECT_ROOT, env=_env_utf8(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    saida = proc.stdout or ""
    if proc.returncode != 0:
        saida += "\n" + (proc.stderr or "")
        print(f"  [ATENÇÃO] '{cmd.rotulo}' terminou com código {proc.returncode}", file=sys.stderr)
    destino.write_text(_limpar(saida), encoding="utf-8")
    print(f"  [ok] {cmd.rotulo} ({len(saida.splitlines())} linhas, {time.perf_counter() - t0:.0f}s)")
    return destino


def ler_captura(cmd_id: str) -> list[str]:
    caminho = caminho_captura(cmd_id)
    if not caminho.exists():
        raise FileNotFoundError(f"captura '{cmd_id}' inexistente: rode o gerador com --recapturar")
    return caminho.read_text(encoding="utf-8").splitlines()


def capturar_tudo(recapturar: bool = False, ids: list[str] | None = None) -> None:
    for cmd_id in ids or list(COMANDOS):
        capturar(cmd_id, recapturar)


if __name__ == "__main__":  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--recapturar", action="store_true")
    capturar_tudo(ap.parse_args().recapturar)
