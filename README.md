# 🏭 Projeto Bayer — Digital Twin + LangGraph + Fuzzy Adaptativo

**Sistema de Controle Preditivo para Processo Bayer** (alumina a partir de bauxita),
com Gêmeo Digital dos decantadores, controlador **Fuzzy Adaptativo** e orquestração
via **LangGraph** com **Human-in-the-Loop (HITL)**.

> **Nota de nomenclatura:** apesar dos títulos originais citarem "Controle Preditivo",
> este módulo implementa um **controlador Fuzzy adaptativo** (não MPC). O MPC está
> listado como evolução futura.

## Topologia modelada

```
Carga Inicial (Bauxita + Soda)
   → [S1] Digestão (série, fechado)
   → [S2] Digestão (série, fechado)
   → Divisão de fluxo
   → [PA] e [PB] Decantadores (paralelo, abertos — sofrem chuva)
```

## Estrutura

```
projeto_bayer/
├── bayer_process_simulator.py   # Gêmeo Digital (tanques, decantadores, distúrbios)
├── fuzzy_controller.py          # Controlador Fuzzy base (Mamdani + centroide)
├── adaptive_fuzzy_controller.py # Fuzzy com ganho adaptativo (gradiente + momentum)
├── weather_service.py           # Integração OpenWeather (opcional, degrada seguro)
├── langgraph_agent.py           # Orquestração LangGraph + HITL
├── influx_persister.py          # Persistência InfluxDB (opcional, vira no-op)
├── dashboard.py                 # Dashboard Streamlit + Plotly
├── test_adaptive_controller.py  # Benchmark reproduzível Padrão vs Adaptativo
├── tests/                       # Suíte pytest
├── requirements.txt
└── .env.example                 # Copie para .env para ativar serviços
```

## Instalação e execução

```bash
cd projeto_bayer
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

# Testes
pytest -v

# Benchmark comparativo (métrica reproduzível: seed fixa + N runs)
python test_adaptive_controller.py

# Dashboard (requer streamlit + plotly)
streamlit run dashboard.py
```

## Correções aplicadas em relação ao roteiro original

- **A2 — Métrica honesta:** o benchmark agora usa **seed fixa + 10 runs**, reportando
  média ± desvio padrão de RMSE (antes: 1 rodada aleatória, alegação não-reproduzível).
- **A3 — Controladores independentes:** **um `AdaptiveFuzzyController` por tanque**
  (PA e PB), pois são independentes e intencionalmente desbalanceados. Antes, um único
  controlador global acoplava o aprendizado entre os dois.
- **A4 — Limiar baseado no nível filtrado:** a decisão de criticidade usa o nível
  **filtrado por EMA**, não o bruto (corrompido por spike de sensor). Isso evita
  alarmes falsos e pausas HITL indevidas por picos isolados.
- **M6 — Estado imutável no LangGraph:** histórico/EMA/tendência são **copiados**
  (não mutados in-place) ao atualizar o estado, compatível com o checkpointing.

## Serviços externos (opcionais)

O núcleo (simulador + controladores + agente) **roda e é testado sem** OpenWeather e
InfluxDB: `weather_service` degrada para "sem chuva" e `influx_persister` vira no-op
quando o pacote/banco não está disponível. Copie `.env.example` para `.env` e preencha
as credenciais para ativar chuva real e persistência.

## Testes

- `tests/test_fuzzy.py` — pertinência, saturação, monotonicidade da abertura.
- `tests/test_adaptive.py` — limites de ganho, reset, métricas.
- `tests/test_simulator.py` — estado inicial, cap de transbordo, efeito da válvula, spikes.
- `tests/test_agent_graph.py` — fluxo sem crash, HITL dispara/aprova, e correções A3/A4
  (controladores separados; limiar usa o nível filtrado). Requer `langgraph`.