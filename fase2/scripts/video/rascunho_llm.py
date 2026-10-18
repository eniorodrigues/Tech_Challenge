"""
Rascunho da narração do vídeo escrito pela LLM gratuita da OpenRouter.

    python scripts/video/rascunho_llm.py            # 4 requisições (3 blocos cada)
    python scripts/video/rascunho_llm.py --blocos 1,2

Para cada grupo de blocos do roteiro, envia os **pontos** (fatos já
verificados) de cada cena e pede um texto falado, em pt-BR, no tamanho certo
para a duração alvo. O resultado vai para ``docs/ROTEIRO_RASCUNHO_LLM.md`` e é a
base da narração final (``narracao_texto.py``), que passa por revisão humana:
conferir números, ajustar ritmo e escrever siglas/números para leitura em voz
alta.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from medroute.llm.client import OpenRouterClient  # noqa: E402
from roteiro import BLOCOS, NOME_APRESENTADOR, PROJECT_ROOT, filtrar_blocos  # noqa: E402

DESTINO = PROJECT_ROOT / "docs" / "ROTEIRO_RASCUNHO_LLM.md"

SISTEMA = f"""Você é roteirista de vídeos técnicos em português do Brasil. Escreve a narração \
falada de um vídeo de demonstração de um projeto acadêmico de pós-graduação (FIAP), apresentado \
em primeira pessoa por {NOME_APRESENTADOR}.

Regras:
1. Use SOMENTE os fatos dos pontos de cada cena. Não invente números nem afirmações.
2. Texto para ser OUVIDO: frases curtas e diretas, tom profissional e natural, sem jargão vazio.
3. Sem Markdown, sem listas, sem emojis, sem aspas desnecessárias.
4. Escreva números e siglas como devem ser lidos em voz alta quando a leitura automática ficaria \
estranha (ex.: "duzentos e cinquenta e três vírgula cinco quilômetros"; "R$ 1.178" vira "mil cento \
e setenta e oito reais").
5. Respeite o tamanho: cerca de 2,4 palavras por segundo da duração alvo de cada cena.
6. As cenas são contínuas: não repita saudações nem resumos entre cenas."""


def _pedido(blocos) -> str:
    cenas = [{"bloco": f"{b.numero}. {b.titulo}", "id": c.id, "tela": c.titulo or c.visual.value,
              "duracao_alvo_segundos": c.alvo_seg, "palavras_alvo": int(c.alvo_seg * 2.4),
              "pontos": list(c.pontos)}
             for b in blocos for c in b.cenas]
    numeros = ", ".join(str(b.numero) for b in blocos)
    return (f"Trecho do vídeo com os blocos {numeros}.\n\n<cenas>\n"
            f"{json.dumps(cenas, ensure_ascii=False, indent=1)}\n</cenas>\n\n"
            "Escreva a narração de cada cena. Responda APENAS com um JSON no formato "
            '{"cenas": [{"id": "...", "narracao": "..."}]}.')


def _extrair_json(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto, flags=re.S)
    if not m:
        raise ValueError("resposta sem JSON")
    return json.loads(m.group(0))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocos", help="ex.: 1,2,3 (padrão: todos)")
    a = ap.parse_args()
    numeros = [int(x) for x in a.blocos.split(",")] if a.blocos else None
    cliente = OpenRouterClient()
    if not cliente.available:
        raise SystemExit("Configure OPENROUTER_API_KEY no .env para gerar o rascunho.")

    saida = ["# Rascunho da narração escrito pela LLM", "",
             f"Modelo: `{cliente.models[0]}` (OpenRouter, gratuito). Gerado por "
             "`scripts/video/rascunho_llm.py` a partir dos pontos de cada cena em "
             "`scripts/video/roteiro.py`. A narração final (`narracao_texto.py`) é a revisão "
             "deste rascunho: números conferidos com os resultados e ritmo ajustado para a voz.",
             ""]
    rascunhos: dict[str, str] = {}
    blocos = list(filtrar_blocos(numeros) if numeros else BLOCOS)
    # 3 blocos por requisição: a cota gratuita é de ~50 requisições por dia.
    for i in range(0, len(blocos), 3):
        grupo = blocos[i:i + 3]
        print(f"Blocos {[b.numero for b in grupo]} ...", flush=True)
        msgs = [{"role": "system", "content": SISTEMA},
                {"role": "user", "content": _pedido(grupo)}]
        resp = cliente.chat(msgs, temperature=0.5, max_tokens=6000)
        try:
            for c in _extrair_json(resp.text).get("cenas", []):
                rascunhos[c["id"]] = c["narracao"].strip()
        except (ValueError, json.JSONDecodeError, KeyError) as exc:
            print(f"  aviso: não consegui ler o JSON ({exc}); guardando o texto bruto")
            rascunhos[f"blocos_{grupo[0].numero}_bruto"] = resp.text
        for bloco in grupo:
            saida += [f"## Bloco {bloco.numero} — {bloco.titulo}",
                      f"_origem: {resp.model} ({'cache' if resp.cached else 'chamada real'})_", ""]
            for c in bloco.cenas:
                txt = rascunhos.get(c.id, "(sem rascunho)")
                saida += [f"**{c.id}** — {c.titulo or c.visual.value} "
                          f"(alvo {c.alvo_seg} s, {len(txt.split())} palavras)", "", f"> {txt}", ""]
    DESTINO.write_text("\n".join(saida) + "\n", encoding="utf-8")
    DESTINO.with_suffix(".json").write_text(json.dumps(rascunhos, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    print(f"rascunho: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
