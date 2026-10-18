"""
Controle mínimo de um navegador Chromium (Microsoft Edge ou Chrome) pelo
**Chrome DevTools Protocol**, para capturar telas reais do painel e da API.

Por que não Selenium/Playwright: o Selenium precisa do ``selenium-manager.exe``
(e de um *driver*), e o Playwright baixa um navegador próprio — binários que o
Smart App Control do Windows desta máquina bloqueia. O CDP fala direto com o
Edge já instalado (assinado pela Microsoft) via WebSocket, com o pacote
``websocket-client`` (Python puro).

Uso::

    with Navegador(1920, 1080) as nav:
        nav.ir("http://localhost:8501")
        nav.esperar("document.querySelectorAll('button[role=tab]').length > 0")
        nav.clicar_texto("button[role=tab]", "Evolução do GA")
        nav.foto("tela.png")
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

CANDIDATOS = [
    Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
]


def achar_navegador() -> Path:
    for c in CANDIDATOS:
        if c.exists():
            return c
    achado = shutil.which("msedge") or shutil.which("chrome") or shutil.which("chromium")
    if achado:
        return Path(achado)
    raise SystemExit("Nenhum navegador Chromium (Edge/Chrome) encontrado para capturar as telas.")


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Navegador:
    def __init__(self, largura: int = 1920, altura: int = 1080, headless: bool = True) -> None:
        import websocket  # websocket-client

        self.largura, self.altura = largura, altura
        self.porta = porta_livre()
        self.perfil = tempfile.mkdtemp(prefix="medroute_cdp_")
        args = [str(achar_navegador()), f"--remote-debugging-port={self.porta}",
                f"--user-data-dir={self.perfil}", f"--window-size={largura},{altura}",
                "--remote-allow-origins=*", "--hide-scrollbars", "--no-first-run",
                "--no-default-browser-check", "--disable-extensions", "--disable-gpu",
                "--force-device-scale-factor=1", "--lang=pt-BR", "about:blank"]
        if headless:
            args.insert(1, "--headless=new")
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        url_ws = self._alvo_pagina()
        self.ws = websocket.create_connection(url_ws, timeout=120, suppress_origin=True,
                                              max_size=None)
        self._id = 0
        self.enviar("Page.enable")
        self.enviar("Runtime.enable")
        self.enviar("Emulation.setDeviceMetricsOverride", width=largura, height=altura,
                    deviceScaleFactor=1, mobile=False)
        # Tema claro (o vídeo inteiro é claro; o Windows pode estar em modo escuro).
        self.enviar("Emulation.setEmulatedMedia",
                    features=[{"name": "prefers-color-scheme", "value": "light"}])

    # ------------------------------------------------------------- protocolo
    def _alvo_pagina(self, timeout: float = 30.0) -> str:
        fim = time.time() + timeout
        while time.time() < fim:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.porta}/json", timeout=2) as r:
                    alvos = json.loads(r.read())
                for a in alvos:
                    if a.get("type") == "page" and a.get("webSocketDebuggerUrl"):
                        return a["webSocketDebuggerUrl"]
            except OSError:
                pass
            time.sleep(0.3)
        raise RuntimeError("o navegador não abriu a porta de depuração a tempo")

    def enviar(self, metodo: str, **params):
        self._id += 1
        meu = self._id
        self.ws.send(json.dumps({"id": meu, "method": metodo, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == meu:
                if "error" in msg:
                    raise RuntimeError(f"{metodo}: {msg['error']}")
                return msg.get("result", {})

    # ------------------------------------------------------------------ ações
    def ir(self, url: str, espera: float = 1.5) -> None:
        self.enviar("Page.navigate", url=url)
        time.sleep(espera)

    def js(self, expressao: str):
        r = self.enviar("Runtime.evaluate", expression=expressao, awaitPromise=True,
                        returnByValue=True)
        return r.get("result", {}).get("value")

    def esperar(self, condicao_js: str, timeout: float = 90.0, intervalo: float = 0.5) -> bool:
        fim = time.time() + timeout
        while time.time() < fim:
            try:
                if self.js(condicao_js):
                    return True
            except RuntimeError:
                pass
            time.sleep(intervalo)
        raise TimeoutError(f"condição não satisfeita em {timeout:.0f}s: {condicao_js}")

    def clicar_texto(self, seletor: str, texto: str) -> bool:
        expr = (f"(() => {{ const el = Array.from(document.querySelectorAll({json.dumps(seletor)}))"
                f".find(e => (e.innerText || '').includes({json.dumps(texto)}));"
                f" if (el) {{ el.scrollIntoView({{block: 'center'}}); el.click(); return true; }} return false; }})()")
        return bool(self.js(expr))

    def digitar(self, seletor: str, texto: str) -> None:
        self.js(f"document.querySelector({json.dumps(seletor)}).focus()")
        self.enviar("Input.insertText", text=texto)

    def enter(self) -> None:
        for tipo in ("keyDown", "keyUp"):
            self.enviar("Input.dispatchKeyEvent", type=tipo, key="Enter", code="Enter",
                        windowsVirtualKeyCode=13, nativeVirtualKeyCode=13,
                        **({"text": "\r"} if tipo == "keyDown" else {}))

    def rolar(self, seletor: str, y: int) -> None:
        self.js(f"(() => {{ const e = document.querySelector({json.dumps(seletor)});"
                f" if (e) e.scrollTo(0, {int(y)}); else window.scrollTo(0, {int(y)}); }})()")

    def foto(self, caminho: str | Path) -> Path:
        dados = self.enviar("Page.captureScreenshot", format="png")["data"]
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(base64.b64decode(dados))
        return caminho

    # --------------------------------------------------------------- recursos
    def fechar(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.perfil, ignore_errors=True)

    def __enter__(self) -> "Navegador":
        return self

    def __exit__(self, *exc) -> None:
        self.fechar()
