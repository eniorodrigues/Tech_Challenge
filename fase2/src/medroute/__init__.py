"""
MedRoute — otimização de rotas para distribuição de medicamentos e insumos.

Tech Challenge — Fase 2 (Projeto 2). O pacote evolui o código base de TSP
fornecido no enunciado (um algoritmo genético para o caixeiro viajante) até um
problema de roteamento de veículos (VRP) com as restrições de um hospital
universitário: prioridade das entregas, capacidade de carga, autonomia,
frota heterogênea, cadeia fria, medicamentos controlados, janelas de horário e
jornada dos motoristas. Uma LLM transforma as rotas em instruções, relatórios
e respostas em linguagem natural.

Módulos principais:

``domain``       entidades (entrega, veículo, cenário)
``scenario``     gerador do cenário sintético de São Paulo
``problem``      instância compilada + função de avaliação (fitness)
``ga``           algoritmo genético (representação, operadores, motor)
``baselines``    heurísticas clássicas e OR-Tools para comparação
``plan``         plano de rotas pronto para consumo (KPIs, JSON)
``viz``          mapas (folium/PNG) e gráficos
``llm``          integração com LLM (OpenRouter) + modo offline
``api``          API REST (FastAPI)
"""

__version__ = "2.0.0"
