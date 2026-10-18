"""
Capturas de tela REAIS do sistema em execução (painel, API e mapa).

Sobe o painel Streamlit e a API FastAPI em portas livres, abre o Microsoft
Edge em modo *headless* via DevTools Protocol (:mod:`cdp`) e fotografa as
telas em 1920x1080. As respostas da LLM vêm do cache (o plano padrão é o
mesmo do pipeline), então nenhuma requisição nova é feita.

    python scripts/video/telas.py            # usa o que já existe
    python scripts/video/telas.py --recapturar
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Navegador, porta_livre  # noqa: E402
from roteiro import PROJECT_ROOT, TELAS_DIR  # noqa: E402

PERGUNTAS = (
    "Qual veículo leva a insulina do paciente PD-05 e a que horas chega?",
    "Alguma entrega crítica corre risco de atraso? O que fazer?",
    "Quais entregas de medicamentos controlados existem hoje e em quais veículos?",
    "Qual é o telefone do paciente PD-08?",
)
ARQUIVOS = ("painel_mapa.png", "painel_dados.png", "painel_evolucao.png", "painel_llm.png",
            "painel_chat.png", "api_docs.png", "mapa_popup.png")


def _esperar_http(url: str, timeout: float = 180) -> None:
    fim = time.time() + timeout
    while time.time() < fim:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"{url} não respondeu")


def _servidor(args: list[str]) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, *args], cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def _rolar_ate(nav: Navegador, js_elemento: str, bloco: str = "start") -> None:
    nav.js(f"(() => {{ const e = {js_elemento}; if (e) e.scrollIntoView({{block: '{bloco}'}}); }})()")


def capturar_painel(nav: Navegador, porta: int) -> None:
    nav.ir(f"http://127.0.0.1:{porta}/", espera=3)
    nav.esperar("document.querySelectorAll('[role=tab]').length >= 5", timeout=240)
    nav.esperar("document.querySelector('iframe') !== null", timeout=60)
    time.sleep(9)                                            # tiles do mapa
    nav.foto(TELAS_DIR / "painel_mapa.png")

    nav.clicar_texto("[role=tab]", "Evolução do GA")
    time.sleep(5)
    nav.foto(TELAS_DIR / "painel_evolucao.png")

    nav.clicar_texto("[role=tab]", "Dados")
    time.sleep(4)
    nav.foto(TELAS_DIR / "painel_dados.png")

    nav.clicar_texto("[role=tab]", "Assistente (LLM)")
    time.sleep(3)
    nav.clicar_texto("button", "Gerar instruções")
    nav.esperar("document.body.innerText.includes('Antes de sair')", timeout=300)
    nav.clicar_texto("button", "Relatório diário")
    nav.esperar("document.body.innerText.includes('Resumo executivo')", timeout=300)
    time.sleep(2)
    _rolar_ate(nav, "Array.from(document.querySelectorAll('h3')).find(e => "
                    "e.innerText.includes('Instruções para motoristas'))")
    time.sleep(1.5)
    nav.foto(TELAS_DIR / "painel_llm.png")

    seletor = "[data-testid=stChatInput] textarea"
    for i, pergunta in enumerate(PERGUNTAS, start=1):
        nav.esperar(f"document.querySelector('{seletor}') !== null", timeout=60)
        nav.digitar(seletor, pergunta)
        time.sleep(0.4)
        nav.enter()
        nav.esperar("document.querySelectorAll('[data-testid=stChatMessage]').length >= "
                    f"{2 * i}", timeout=300)
        nav.esperar("!document.body.innerText.includes('Consultando a LLM')", timeout=300)
        time.sleep(1.0)
    _rolar_ate(nav, "Array.from(document.querySelectorAll('[data-testid=stChatMessage]'))"
                    ".slice(-4)[0]")
    time.sleep(1.5)
    nav.foto(TELAS_DIR / "painel_chat.png")


def capturar_api(nav: Navegador, porta: int) -> None:
    nav.ir(f"http://127.0.0.1:{porta}/docs", espera=3)
    nav.esperar("document.querySelectorAll('.opblock').length >= 8", timeout=120)
    time.sleep(1.5)
    nav.foto(TELAS_DIR / "api_docs.png")


def capturar_mapa(nav: Navegador) -> None:
    html = PROJECT_ROOT / "reports" / "maps" / "mapa_rotas_ga.html"
    nav.ir(html.resolve().as_uri(), espera=3)
    nav.esperar("document.querySelectorAll('.leaflet-tile-loaded').length > 8", timeout=90)
    time.sleep(3)
    # Abre o popup da 3ª parada da moto V4 (a insulina com atraso previsto).
    nav.js("""(() => {
        const m = Array.from(document.querySelectorAll('.leaflet-marker-icon'))
            .find(e => e.innerHTML.includes('#eda100') && e.innerHTML.includes('>3</text>'));
        if (m) m.dispatchEvent(new MouseEvent('click', {bubbles: true}));
    })()""")
    time.sleep(2)
    nav.foto(TELAS_DIR / "mapa_popup.png")


def capturar_telas(recapturar: bool = False) -> None:
    TELAS_DIR.mkdir(parents=True, exist_ok=True)
    if not recapturar and all((TELAS_DIR / a).exists() for a in ARQUIVOS):
        print("  [cache] telas do painel, da API e do mapa")
        return
    p_painel, p_api = porta_livre(), porta_livre()
    painel = _servidor(["-m", "streamlit", "run", "app/dashboard.py", "--server.port", str(p_painel),
                        "--server.headless", "true", "--browser.gatherUsageStats", "false"])
    api = _servidor(["-m", "uvicorn", "medroute.api.app:app", "--port", str(p_api)])
    try:
        _esperar_http(f"http://127.0.0.1:{p_painel}/_stcore/health")
        _esperar_http(f"http://127.0.0.1:{p_api}/health")
        with Navegador(1920, 1080) as nav:
            print("  capturando o painel (Streamlit)...", flush=True)
            capturar_painel(nav, p_painel)
            print("  capturando a API (Swagger)...", flush=True)
            capturar_api(nav, p_api)
            print("  capturando o mapa interativo (folium)...", flush=True)
            capturar_mapa(nav)
    finally:
        for proc in (painel, api):
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
    for a in ARQUIVOS:
        print(f"  {'ok ' if (TELAS_DIR / a).exists() else 'FALTOU'} {a}")


if __name__ == "__main__":  # pragma: no cover
    import argparse

    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--recapturar", action="store_true")
    capturar_telas(ap.parse_args().recapturar)
