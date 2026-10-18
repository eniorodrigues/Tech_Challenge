# API REST do MedRoute

```bash
uvicorn medroute.api.app:app --reload        # a partir de fase2/, com o .venv ativo
```

* Documentação interativa (Swagger): <http://127.0.0.1:8000/docs>
* ReDoc: <http://127.0.0.1:8000/redoc>
* Especificação OpenAPI 3.1: [`docs/openapi.json`](openapi.json)
  (regerar: `python -c "import json; from medroute.api.app import app; print(json.dumps(app.openapi(), ensure_ascii=False, indent=1))" > docs/openapi.json`)

Os planos ficam em memória no processo da API (demonstração — sem banco).
Os endpoints de LLM aceitam `?modo=auto|llm|offline` (padrão `auto`: usa a
OpenRouter e cai para o modo offline se faltar chave, rede ou cota).

## Endpoints

| Método | Caminho | O que faz |
|---|---|---|
| GET | `/health` | Estado da API, modelos da LLM configurados e disponibilidade do OR-Tools |
| GET | `/cenarios/padrao` | Cenário de referência (36 entregas, 5 veículos) |
| POST | `/cenarios/gerar` | Gera um cenário sintético (semente, composição, utilização alvo) |
| POST | `/otimizar` | Roda o algoritmo genético; devolve `plano_id`, plano, economia vs. processo atual |
| POST | `/comparar` | Roda abordagens de comparação no mesmo cenário |
| GET | `/planos/{plano_id}` | Plano completo do GA e do processo atual |
| GET | `/planos/{plano_id}/mapa` | Mapa interativo (HTML/Leaflet); `?processo_atual=true` mostra o plano atual |
| POST | `/planos/{plano_id}/instrucoes/{veiculo}` | Instruções para o(a) motorista (LLM) |
| POST | `/planos/{plano_id}/relatorio` | Relatório diário de eficiência (LLM) |
| POST | `/planos/{plano_id}/sugestoes` | Sugestões de melhoria com simulações "e se" (LLM) |
| POST | `/planos/{plano_id}/perguntar` | Pergunta em linguagem natural, com histórico (LLM) |

## Exemplos

```bash
# 1. Otimizar o dia padrão (configuração do GA opcional)
curl -s -X POST http://127.0.0.1:8000/otimizar \
  -H "Content-Type: application/json" \
  -d '{"config": {"geracoes": 300, "seed": 42}, "pesos": {"prioridade": 1.0, "atraso": 1.0}}'
# -> {"plano_id": "3f9c1a2b7e", "plano": {...}, "comparacao_processo_atual": {"km_economizados": 46.0, ...}}

# 2. Mapa interativo (abra no navegador)
http://127.0.0.1:8000/planos/3f9c1a2b7e/mapa

# 3. Instruções do motorista da Van Refrigerada (V1)
curl -s -X POST "http://127.0.0.1:8000/planos/3f9c1a2b7e/instrucoes/V1?modo=auto"

# 4. Pergunta em linguagem natural (com histórico)
curl -s -X POST http://127.0.0.1:8000/planos/3f9c1a2b7e/perguntar \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Que horas a insulina do paciente PD-05 chega?", "historico": []}'
```

Resposta típica de um endpoint de LLM:

```json
{
  "task": "pergunta",
  "text": "A insulina do paciente PD-05 (Jabaquara) vai na Moto 01 (V4), parada 3, com chegada prevista às 09:03...",
  "source": "llm",
  "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
  "latency_s": 3.5,
  "validation": {"nota": 100.0, "ids_inexistentes": [], "horarios_inventados": [],
                 "numeros_nao_rastreaveis": [], "requisitos_inventados": [], "observacoes": []},
  "warning": null,
  "extra": {"usage": {...}, "prompt_version": "2026.10-v2"}
}
```

`source` vale `llm` (chamada real), `cache` (mesma pergunta já respondida) ou
`offline` (template, com `warning` explicando o motivo).

## Corpo de `POST /otimizar`

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `cenario` | objeto | cenário padrão | Mesmo formato de `GET /cenarios/padrao` |
| `config.geracoes` | int | 400 | Máximo de gerações |
| `config.populacao` | int | 120 | Tamanho da população |
| `config.seed` | int | 42 | Semente |
| `config.crossover` | `mix`·`ox`·`pmx`·`erx`·`bcrc` | `mix` | Operador de cruzamento |
| `config.selecao` | `tournament`·`roulette`·`rank`·`truncation` | `tournament` | Seleção |
| `config.taxa_mutacao` | float | 0,4 | Probabilidade de mutar cada filho |
| `config.elitismo` | int | 2 | Indivíduos preservados |
| `config.sementes_heuristicas` | bool | true | Heurísticas na população inicial |
| `config.busca_local` | bool | true | 2-opt/relocate (memético) |
| `config.paciencia` | int | 250 | Para após N gerações sem melhora |
| `config.tempo_limite_s` | float | — | Limite de tempo |
| `pesos.distancia` / `prioridade` / `atraso` / `custo` | float | 1 / 1 / 1 / 0 | Pesos da fitness |
| `incluir_historico` | bool | false | Devolve a curva de convergência |

Erros: `404` (plano ou veículo inexistente), `422` (cenário/configuração inválidos — a resposta lista os problemas encontrados).
