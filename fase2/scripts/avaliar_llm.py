"""
Avaliação objetiva das saídas da LLM salvas em ``reports/llm``.

    python scripts/avaliar_llm.py                  # avalia e imprime a tabela
    python scripts/avaliar_llm.py --rotulo v1      # grava reports/llm/avaliacao_v1.md/.json
    python scripts/avaliar_llm.py --pasta reports/llm/prompt_v1 --rotulo v1   # versão arquivada

Reconstrói o plano do dia (mesma semente do pipeline), relê cada texto gerado
e roda os guardrails: cobertura e ordem das paradas, horários e IDs
inventados, números não rastreáveis e requisitos atribuídos indevidamente
(ex.: tratar um antibiótico comum como medicamento controlado).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import pandas as pd  # noqa: E402

from medroute import config  # noqa: E402
from medroute.cli import _plano_salvo  # noqa: E402
from medroute.llm import context as ctx  # noqa: E402
from medroute.llm import guardrails  # noqa: E402
from medroute.operations import summarize_week  # noqa: E402


def _texto(arq: Path) -> str:
    return re.sub(r"^<!--.*?-->\s*", "", arq.read_text(encoding="utf-8"), flags=re.S)


def avaliar(pasta: Path | None = None) -> pd.DataFrame:
    ga, atual = _plano_salvo()
    pasta = pasta or config.LLM_OUTPUT_DIR
    linhas = []
    for arq in sorted(pasta.glob("instrucoes_V*.md")):
        v = arq.stem.split("_")[1]
        rota = ga.route(v)
        dados = ctx.route_context(rota)
        rep = guardrails.validate_route_text(_texto(arq), rota, ga, dados)
        linhas.append({"arquivo": arq.name, **rep.to_dict()})
    if (pasta / "relatorio_diario.md").exists():
        dados = ctx.comparison_context(ga, atual)
        dados["frota"] = ctx.plan_context(ga, include_stops=False)["veiculos"]
        rep = guardrails.validate_free_text(_texto(pasta / "relatorio_diario.md"), ga, dados)
        linhas.append({"arquivo": "relatorio_diario.md", **rep.to_dict()})
    semana_csv = config.REPORTS_DIR / "operacao_semanal.csv"
    if (pasta / "relatorio_semanal.md").exists() and semana_csv.exists():
        dados = summarize_week(pd.read_csv(semana_csv))
        rep = guardrails.validate_free_text(_texto(pasta / "relatorio_semanal.md"), ga, dados)
        linhas.append({"arquivo": "relatorio_semanal.md", **rep.to_dict()})
    sims = pasta / "simulacoes_e_se.json"
    if (pasta / "sugestoes_melhoria.md").exists() and sims.exists():
        dados = json.loads(sims.read_text(encoding="utf-8"))
        dados["indicadores"] = ctx.kpi_context(ga)
        rep = guardrails.validate_free_text(_texto(pasta / "sugestoes_melhoria.md"), ga, dados)
        linhas.append({"arquivo": "sugestoes_melhoria.md", **rep.to_dict()})
    if (pasta / "perguntas_e_respostas.md").exists():
        rep = guardrails.validate_free_text(_texto(pasta / "perguntas_e_respostas.md"), ga,
                                            ctx.plan_context(ga))
        linhas.append({"arquivo": "perguntas_e_respostas.md", **rep.to_dict()})
    return pd.DataFrame(linhas)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotulo", help="grava avaliacao_<rotulo>.md/.json em reports/llm")
    ap.add_argument("--pasta", help="pasta com as saídas a avaliar (padrão: reports/llm)")
    a = ap.parse_args()
    df = avaliar(Path(a.pasta).resolve() if a.pasta else None)
    cols = ["arquivo", "nota", "cobertura_paradas", "ordem_correta", "horarios_inventados",
            "ids_inexistentes", "requisitos_inventados", "numeros_nao_rastreaveis"]
    print(df[cols].to_string(index=False))
    print(f"\nNota média: {df['nota'].mean():.1f}/100")
    if a.rotulo:
        destino = config.LLM_OUTPUT_DIR / f"avaliacao_{a.rotulo}"
        df.to_json(destino.with_suffix(".json"), orient="records", force_ascii=False, indent=1)
        md = ["| Arquivo | Nota | Cobertura | Ordem | Horários inventados | Requisitos inventados | Números não rastreáveis |",
              "|---|---|---|---|---|---|---|"]
        for _, r in df.iterrows():
            cob = "—" if pd.isna(r["cobertura_paradas"]) else f"{r['cobertura_paradas']:.0%}"
            ordem = "—" if r["ordem_correta"] is None or pd.isna(r["ordem_correta"]) else ("ok" if r["ordem_correta"] else "trocada")
            md.append(f"| {r['arquivo']} | {r['nota']:.0f} | {cob} | {ordem} | "
                      f"{', '.join(r['horarios_inventados']) or '—'} | "
                      f"{', '.join(r['requisitos_inventados']) or '—'} | "
                      f"{', '.join(r['numeros_nao_rastreaveis']) or '—'} |")
        md.append(f"\n**Nota média:** {df['nota'].mean():.1f}/100")
        destino.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
        print(f"gravado: {destino}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
