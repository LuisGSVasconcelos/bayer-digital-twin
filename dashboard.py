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
import bayer_process_simulator as sim
import adaptive_fuzzy_controller as afc
from weather_service import weather_service

st.set_page_config(page_title="Bayer Process Control Room", page_icon="🏭", layout="wide")

SETPOINT = 65.0
SUBSTEPS_PER_TICK = 10  # A) varios ciclos fisicos por tick (relogio acelerado, leve)

# Inicializacao do estado da sessao
if "agente" not in st.session_state:
    st.session_state.planta = planta_bayer
    # B) cenário demo: decantadores ACIMA do limiar (80.5%) -> HITL ja no 1o ciclo.
    #    Aprovar libera a valvula; o controle modulante regula ate o setpoint e segura.
    planta_bayer.t_paralelo_a.volume = planta_bayer.t_paralelo_a.capacidade * 0.805
    planta_bayer.t_paralelo_b.volume = planta_bayer.t_paralelo_b.capacidade * 0.803
    # demo: o painel "Distúrbios" do sidebar controla quais estao ativos. Todos podem
    # ficar ligados: com balanco corrigido + PI, o nivel segura no setpoint.
    planta_bayer.gerador.ativo = True
    planta_bayer.gerador.config.pop("only_chemistry", None)
    lga.VERBOSE = False
    sim.VERBOSE = False
    afc.VERBOSE = False
    lga.FORCA_CLIMA = "Forte"  # chuva simulada (demo offline) para ativar o ramo critico
    st.session_state.agente = build_app()
    st.session_state.config_agente = {"configurable": {"thread_id": "dashboard"}}
    st.session_state.estado_atual = dict(estado_inicial)
    st.session_state.executando = False
    st.session_state.historico = pd.DataFrame(columns=[
        "timestamp", "nivel_PA", "nivel_PB", "nivel_S1", "nivel_S2",
        "abertura_PA", "abertura_PB", "makeup_PA", "makeup_PB", "tc_saida", "soda_perdida_pa", "soda_perdida_pb",
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
            "makeup_PA": planta.t_paralelo_a.abertura_makeup * 100,
            "makeup_PB": planta.t_paralelo_b.abertura_makeup * 100,
            "tc_saida": dados.get("tc_saida_decantadores", 0),
            "soda_perdida_pa": (dados.get("soda_perdida", {}) or {}).get("PA", 0),
            "soda_perdida_pb": (dados.get("soda_perdida", {}) or {}).get("PB", 0),
            "chuva_mm_h": dados.get("chuva_atual_mm_h", 0),
            "vazao_diluicao": planta.vazao_diluicao_tc,
            "teor_sio2": dados.get("teor_sio2_atual", 5.0),
            "alerta_agente": alerta,
        }
        novo_df = pd.DataFrame([novo])
        if st.session_state.historico.empty:
            st.session_state.historico = novo_df
        else:
            st.session_state.historico = pd.concat(
                [st.session_state.historico, novo_df], ignore_index=True).tail(200)
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
speed = st.sidebar.slider("Velocidade (ciclos/s)", 1, 12, 3)

st.sidebar.markdown("---")
st.sidebar.subheader("🌤️ Clima (demo)")
lga.FORCA_INTENSIDADE_MM_S = None  # reseta manual a cada rerun
cenario = st.sidebar.selectbox(
    "Cenário de clima",
    ["Forte", "Moderada", "Nenhuma", "Manual...", "Real (API)"],
    index=0,
    help="Forte/Moderada forçam chuva fixa; \"Manual...\" ajusta a chuva de forma contínua "
         "(slider); \"Real\" usa a API OpenWeather.",
)
if cenario == "Manual...":
    mm_s = st.sidebar.slider(
        "Intensidade da chuva (mm/s)", 0.0, 0.30, 0.12, 0.01,
        help="Chuva contínua: varia suavemente entre 0 e 0,30 mm/s (além dos 3 estados fixos).")
    lga.FORCA_INTENSIDADE_MM_S = float(mm_s)
    lga.FORCA_CLIMA = None
    st.sidebar.caption(f"Chuva: {mm_s:.2f} mm/s")
elif cenario == "Real (API)":
    lga.FORCA_CLIMA = None
    try:
        mmh, desc, alerta = weather_service.get_rain_intensity()
        st.sidebar.metric("Chuva (API)", f"{mmh:.1f} mm/h", delta=desc)
    except Exception:
        st.sidebar.error("Clima offline")
else:
    lga.FORCA_CLIMA = cenario
    mm = {"Forte": 0.25, "Moderada": 0.05, "Nenhuma": 0.0}[cenario]
    st.sidebar.metric("Chuva (simulada)", f"{mm} mm/s", delta=cenario)

st.sidebar.markdown("---")
st.sidebar.subheader("🌩️ Distúrbios")
_hab = {
    "alimentacao": st.sidebar.checkbox("Variação de alimentação", value=True),
    "desgaste": st.sidebar.checkbox("Desgaste da bomba", value=True),
    "stiction": st.sidebar.checkbox("Atrito da válvula (stiction)", value=True),
    "desbalanceamento": st.sidebar.checkbox("Desbalanceamento PA/PB", value=True),
    "tc_diluicao": st.sidebar.checkbox("Diluição de TC", value=True),
    "silica": st.sidebar.checkbox("Sílica (perda de soda)", value=True),
}
planta_bayer.gerador.config["disturbios_habilitados"] = _hab
planta_bayer.gerador.config.pop("only_chemistry", None)
planta_bayer.gerador.config["spike_sensor"]["probabilidade"] = (
    0.02 if st.sidebar.checkbox("Picos de sensor (ruído de leitura)", value=False,
                                help="Adiciona picos esporádicos na leitura dos níveis") else 0.0)

st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Controlador")
_modo = st.sidebar.radio(
    "Estratégia de controle",
    ["PI (drenagem + makeup)", "Fuzzy Adaptativo"],
    index=0,
    help="PI: drenagem + makeup (segura o setpoint, bidirecional). Fuzzy: controlador adaptativo "
         "(só drenagem) para comparar.")
lga.MODO_CONTROLE = "fuzzy" if str(_modo).startswith("Fuzzy") else "pi"

st.sidebar.caption(f"Simulação acelerada: {SUBSTEPS_PER_TICK} ciclos/tick")

st.sidebar.markdown("---")
st.sidebar.subheader("🕹️ Válvula de saída (manual)")
lga.FORCA_ABERTURA = {}  # reseta manual a cada rerun
manual_val = st.sidebar.checkbox(
    "Atuação manual da válvula",
    value=False,
    help="Define a abertura da válvula de drenagem manualmente, sobrepondo o controle PI.")
if manual_val:
    v_pa = st.sidebar.slider("Abertura PA (%)", 0, 100, 0, 5)
    v_pb = st.sidebar.slider("Abertura PB (%)", 0, 100, 0, 5)
    lga.FORCA_ABERTURA = {"PA": v_pa / 100.0, "PB": v_pb / 100.0}
    st.sidebar.caption("Controle automático sobreposto. Desligue p/ voltar ao PI.")
    # Modo manual = operador acionando a valvula diretamente: a acao manual ja e a
    # "aprovacao" humana, entao libera qualquer HITL pendente (nao congela a simulacao).
    _snap = st.session_state.agente.get_state(st.session_state.config_agente)
    if _snap and _snap.next:
        st.session_state.agente.update_state(
            st.session_state.config_agente, {"emergencia_aprovada": True},
            as_node="aguardar_operador")
        for _ in st.session_state.agente.stream(None, st.session_state.config_agente):
            pass
        st.session_state.executando = True

# ------------------------------ KPIs ------------------------------
st.title("🏭 Digital Twin - Processo Bayer")
df = st.session_state.historico

# HITL proeminente no corpo: quando ha aprovacao pendente, mostra banner + botao grande
try:
    _snap_h = st.session_state.agente.get_state(st.session_state.config_agente)
    if _snap_h and _snap_h.next:
        st.error("⚠️ **Ação Emergencial pendente de aprovação humana** — o loop pausou "
                 "automaticamente (não é travamento). Aprove para liberar a ação.")
        _aprov = st.button("✅ Aprovar Ação Emergencial (libera o loop)", type="primary")
        if _aprov:
            st.session_state.agente.update_state(
                st.session_state.config_agente, {"emergencia_aprovada": True},
                as_node="aguardar_operador")
            for _ in st.session_state.agente.stream(None, st.session_state.config_agente):
                pass
            st.session_state.executando = True
except Exception:
    pass

if not df.empty:
    ultimo = df.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Nível PA", f"{ultimo['nivel_PA']:.2f}%",
              "Crítico!" if ultimo["nivel_PA"] > 80 else "OK")
    c2.metric("📊 Nível PB", f"{ultimo['nivel_PB']:.2f}%")
    c3.metric("🧪 TC Saída", f"{ultimo['tc_saida']:.1f} g/L")
    c4.metric("💧 Perda Soda", f"{ultimo['soda_perdida_pa'] + ultimo['soda_perdida_pb']:.2f} kg/s")

    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Scatter(x=df["timestamp"], y=df["nivel_PA"], name="Nível PA", line=dict(color="red")))
    fig1.add_trace(go.Scatter(x=df["timestamp"], y=df["nivel_PB"], name="Nível PB", line=dict(color="orange")))
    fig1.add_trace(go.Scatter(x=df["timestamp"], y=[SETPOINT] * len(df), name="Setpoint",
                              line=dict(color="green", dash="dash")))
    fig1.add_trace(go.Bar(x=df["timestamp"], y=df["abertura_PA"], name="Abertura PA (dreno)",
                          marker_color="orange", opacity=0.5), secondary_y=True)
    fig1.add_trace(go.Bar(x=df["timestamp"], y=df["abertura_PB"], name="Abertura PB (dreno)",
                          marker_color="teal", opacity=0.4), secondary_y=True)
    fig1.add_trace(go.Scatter(x=df["timestamp"], y=df["makeup_PA"], name="Makeup PA",
                              line=dict(color="green", dash="dot")), secondary_y=True)
    fig1.add_trace(go.Scatter(x=df["timestamp"], y=df["makeup_PB"], name="Makeup PB",
                              line=dict(color="lime", dash="dashdot")), secondary_y=True)
    fig1.update_layout(title="Controle de Nível (PV x SP x MV)", height=300, hovermode="x unified",
                       legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    fig1.update_yaxes(title_text="Nível (%)", secondary_y=False)
    fig1.update_yaxes(title_text="Abertura (%)", secondary_y=True, range=[0, 100])
    st.plotly_chart(fig1, width="stretch", config={"displayModeBar": False})

    fig2 = make_subplots(specs=[[{"secondary_y": True}]])
    fig2.add_trace(go.Scatter(x=df["timestamp"], y=df["tc_saida"], name="TC (g/L)",
                              line=dict(color="purple")))
    fig2.add_trace(go.Scatter(x=df["timestamp"], y=df["soda_perdida_pa"] + df["soda_perdida_pb"],
                              name="Perda Soda", line=dict(color="red", dash="dot")), secondary_y=True)
    fig2.add_trace(go.Bar(x=df["timestamp"], y=df["chuva_mm_h"], name="Chuva (mm/s)",
                          marker_color="blue", opacity=0.3), secondary_y=True)
    fig2.update_layout(title="Química e Distúrbios", height=300)
    st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})

    with st.expander("📋 Log de Eventos"):
        st.dataframe(df.tail(10)[["timestamp", "alerta_agente", "nivel_PA", "tc_saida"]])
else:
    st.warning("Aguardando dados. Clique em Iniciar.")

# ------------------------------ LOOP ------------------------------
status_placeholder = st.sidebar.empty()
if st.session_state.executando:
    alerta = executar_ciclo()
    if "Humana" in alerta:
        # HITL: PAUSA o loop (sem rerun) p/ deixar o bloco HITL renderizar o botao de aprovar.
        st.session_state.executando = False
        status_placeholder.warning("⏸️ HITL: aguardando aprovação. Aprove no painel HITL ao lado.")
    else:
        status_placeholder.success("🟢 Executando...")
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
            # trava a aprovacao: continua drenando ate o nivel sair do critico,
            # sem re-pedir aprovacao a cada ciclo
            st.session_state.agente.update_state(
                st.session_state.config_agente, {"emergencia_aprovada": True},
                as_node="aguardar_operador")
            for _ in st.session_state.agente.stream(None, st.session_state.config_agente):
                pass
            st.session_state.executando = True  # retoma automaticamente (drena o nivel)
            st.rerun()
    else:
        st.sidebar.success("✅ Nenhuma ação pendente.")
except Exception:
    pass