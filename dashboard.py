"""Dashboard interativo (Streamlit + Plotly) do Digital Twin Bayer.

Uso: streamlit run dashboard.py
Dependencias: streamlit, plotly, pandas (ver requirements.txt).
"""
import time
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import langgraph_agent as lga
from langgraph_agent import build_app, planta_bayer, estado_inicial
from weather_service import weather_service

st.set_page_config(page_title="Bayer Process Control Room", page_icon="🏭", layout="wide")

SETPOINT = 65.0
SUBSTEPS_PER_TICK = 10  # A) varios ciclos fisicos por tick (relogio acelerado)

# Inicializacao do estado da sessao
if "agente" not in st.session_state:
    st.session_state.planta = planta_bayer
    # B) cenário demo: decantadores acima do limiar critico → dispara HITL visível
    planta_bayer.t_paralelo_a.volume = planta_bayer.t_paralelo_a.capacidade * 0.805
    planta_bayer.t_paralelo_b.volume = planta_bayer.t_paralelo_b.capacidade * 0.802
    lga.FORCA_CLIMA = "Forte"  # chuva simulada (demo offline) para ativar o ramo critico
    st.session_state.agente = build_app()
    st.session_state.config_agente = {"configurable": {"thread_id": "dashboard"}}
    st.session_state.estado_atual = dict(estado_inicial)
    st.session_state.executando = False
    st.session_state.historico = pd.DataFrame(columns=[
        "timestamp", "nivel_PA", "nivel_PB", "nivel_S1", "nivel_S2",
        "abertura_PA", "abertura_PB", "tc_saida", "soda_perdida_pa", "soda_perdida_pb",
        "chuva_mm_h", "vazao_diluicao", "teor_sio2", "alerta_agente",
    ])


def executar_ciclo():
    try:
        # Seguranca: se ja ha HITL pendente, NAO re-stream (evita burlar a aprovacao)
        snap0 = st.session_state.agente.get_state(st.session_state.config_agente)
        if snap0 and snap0.next:
            return "⚠️ Aprovação Humana Necessária!"

        snap = None
        alerta = "Normal"
        for _ in range(SUBSTEPS_PER_TICK):
            for _ev in st.session_state.agente.stream(
                    st.session_state.estado_atual, st.session_state.config_agente):
                pass
            snap = st.session_state.agente.get_state(st.session_state.config_agente)
            if snap.next:
                alerta = "⚠️ Aprovação Humana Necessária!"
                break
        dados = snap.values

        planta = st.session_state.planta
        novo = {
            "timestamp": datetime.now(),
            "nivel_PA": planta.t_paralelo_a.percentual,
            "nivel_PB": planta.t_paralelo_b.percentual,
            "nivel_S1": planta.t_serie1.percentual,
            "nivel_S2": planta.t_serie2.percentual,
            "abertura_PA": planta.t_paralelo_a.abertura_valvula * 100,
            "abertura_PB": planta.t_paralelo_b.abertura_valvula * 100,
            "tc_saida": dados.get("tc_saida_decantadores", 0),
            "soda_perdida_pa": (dados.get("soda_perdida", {}) or {}).get("PA", 0),
            "soda_perdida_pb": (dados.get("soda_perdida", {}) or {}).get("PB", 0),
            "chuva_mm_h": dados.get("chuva_atual_mm_h", 0),
            "vazao_diluicao": planta.vazao_diluicao_tc,
            "teor_sio2": dados.get("teor_sio2_atual", 5.0),
            "alerta_agente": alerta,
        }
        st.session_state.historico = pd.concat(
            [st.session_state.historico, pd.DataFrame([novo])], ignore_index=True).tail(200)
        return alerta
    except Exception as e:
        st.error(f"Erro: {e}")
        return "Erro"


# ------------------------------ SIDEBAR ------------------------------
st.sidebar.title("🏭 Sala de Controle")
if st.sidebar.button("▶️ Iniciar"):
    st.session_state.executando = True
if st.sidebar.button("⏹️ Parar"):
    st.session_state.executando = False
speed = st.sidebar.slider("Velocidade (ciclos/s)", 1, 20, 5)

st.sidebar.markdown("---")
st.sidebar.subheader("🌤️ Clima (demo)")
cenario = st.sidebar.selectbox(
    "Cenário de clima",
    ["Forte", "Moderada", "Nenhuma", "Real (API)"],
    index=0,
    help="Forte/Moderada forçam chuva simulada (funcionam offline). \"Real\" usa a API OpenWeather.",
)
lga.FORCA_CLIMA = None if cenario == "Real (API)" else cenario
if cenario == "Real (API)":
    try:
        chuva, desc, alerta = weather_service.get_rain_intensity()
        st.sidebar.metric("Chuva (API)", f"{chuva} mm/h", delta=desc)
    except Exception:
        st.sidebar.error("Clima offline")
else:
    mm = {"Forte": 12.0, "Moderada": 0.5, "Nenhuma": 0.0}[cenario]
    st.sidebar.metric("Chuva (simulada)", f"{mm} mm/h", delta=cenario)
st.sidebar.caption(f"Simulação acelerada: {SUBSTEPS_PER_TICK} ciclos/tick")

# ------------------------------ KPIs ------------------------------
st.title("🏭 Digital Twin - Processo Bayer")
df = st.session_state.historico

if not df.empty:
    ultimo = df.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Nível PA", f"{ultimo['nivel_PA']:.1f}%",
              "Crítico!" if ultimo["nivel_PA"] > 80 else "OK")
    c2.metric("📊 Nível PB", f"{ultimo['nivel_PB']:.1f}%")
    c3.metric("🧪 TC Saída", f"{ultimo['tc_saida']:.1f} g/L")
    c4.metric("💧 Perda Soda", f"{ultimo['soda_perdida_pa'] + ultimo['soda_perdida_pb']:.2f} kg/s")

    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Scatter(x=df["timestamp"], y=df["nivel_PA"], name="Nível PA", line=dict(color="red")))
    fig1.add_trace(go.Scatter(x=df["timestamp"], y=[SETPOINT] * len(df), name="Setpoint",
                              line=dict(color="green", dash="dash")))
    fig1.add_trace(go.Bar(x=df["timestamp"], y=df["abertura_PA"], name="Abertura PA",
                          marker_color="orange", opacity=0.5), secondary_y=True)
    fig1.update_layout(title="Controle de Nível (PV x SP x MV)", height=300, hovermode="x unified")
    fig1.update_yaxes(title_text="Nível (%)", secondary_y=False)
    fig1.update_yaxes(title_text="Abertura (%)", secondary_y=True, range=[0, 100])
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = make_subplots(specs=[[{"secondary_y": True}]])
    fig2.add_trace(go.Scatter(x=df["timestamp"], y=df["tc_saida"], name="TC (g/L)",
                              line=dict(color="purple")))
    fig2.add_trace(go.Scatter(x=df["timestamp"], y=df["soda_perdida_pa"] + df["soda_perdida_pb"],
                              name="Perda Soda", line=dict(color="red", dash="dot")), secondary_y=True)
    fig2.add_trace(go.Bar(x=df["timestamp"], y=df["chuva_mm_h"], name="Chuva (mm/h)",
                          marker_color="blue", opacity=0.3), secondary_y=True)
    fig2.update_layout(title="Química e Distúrbios", height=300)
    st.plotly_chart(fig2, use_container_width=True)

    with st.expander("📋 Log de Eventos"):
        st.dataframe(df.tail(10)[["timestamp", "alerta_agente", "nivel_PA", "tc_saida"]])
else:
    st.warning("Aguardando dados. Clique em Iniciar.")

# ------------------------------ LOOP ------------------------------
status_placeholder = st.sidebar.empty()
if st.session_state.executando:
    status_placeholder.success("🟢 Executando...")
    alerta = executar_ciclo()
    if "Humana" in alerta:
        status_placeholder.warning("⏸️ Aguardando Aprovação (HITL)")
    time.sleep(1.0 / speed)
    st.rerun()
else:
    status_placeholder.info("⏹️ Pausado")

# ------------------------------ HITL ------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("👤 HITL")
try:
    snap = st.session_state.agente.get_state(st.session_state.config_agente)
    if snap.next:
        if st.sidebar.button("✅ Aprovar Ação Emergencial"):
            st.session_state.agente.update_state(
                st.session_state.config_agente, {}, as_node="aguardar_operador")
            for _ in st.session_state.agente.stream(None, st.session_state.config_agente):
                pass
            st.rerun()
    else:
        st.sidebar.success("✅ Nenhuma ação pendente.")
except Exception:
    pass