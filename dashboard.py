"""Dashboard interativo (Streamlit + Plotly) do Digital Twin Bayer.

Uso: streamlit run dashboard.py
Dependencias: streamlit, plotly, pandas (ver requirements.txt).
"""
import time
from datetime import datetime, timedelta

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

# Colunas canonicas do historico. Usado para reindexar e garantir que sessao antiga
# (sem as colunas mais recentes, ex.: vazao_alimentacao) nao quebre os graficos.
COLS_HIST = [
    "timestamp", "nivel_PA", "nivel_PB", "nivel_S1", "nivel_S2",
    "abertura_PA", "abertura_PB", "makeup_PA", "makeup_PB", "tc_saida",
    "soda_perdida_pa", "soda_perdida_pb", "chuva_mm_h", "vazao_diluicao",
    "vazao_alimentacao", "teor_sio2", "alerta_agente",
]

# Relogio FICTICIO e independente do computador: cada ciclo de processo conta como
# DT_CICLO segundos a partir de uma epoca fixa. Usado em modo continuo e manual (ticks).
DT_CICLO = 1.0           # s de processo por ciclo (vazoes em L/s => 1 ciclo ~ 1 s)
EPOCH_SIM = datetime(2024, 1, 1, 0, 0, 0)

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
    st.session_state.tick = 0  # total de ciclos de processo (relogio ficticio)
    st.session_state.epoca = EPOCH_SIM
    st.session_state.historico = pd.DataFrame(columns=COLS_HIST)


def anexar_linha_historico(planta, snap, n_ciclos=1):
    """Anexa uma linha (fotografia do tick) ao historico do dashboard.

    O tempo e FICTICIO: avanca n_ciclos x DT_CICLO a partir da epoca da sessao,
    independente do relogio do computador (funciona em modo continuo e manual).
    """
    S = st.session_state
    S.tick += n_ciclos
    t_sim = S.epoca + timedelta(seconds=S.tick * DT_CICLO)
    dados = snap.values
    novo = {
        "timestamp": t_sim,
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
        "vazao_alimentacao": round(planta.vazao_alimentacao, 2),
        "teor_sio2": dados.get("teor_sio2_atual", 5.0),
        "alerta_agente": "Normal",
    }
    novo_df = pd.DataFrame([novo])
    if st.session_state.historico.empty:
        st.session_state.historico = novo_df
    else:
        st.session_state.historico = pd.concat(
            [st.session_state.historico, novo_df], ignore_index=True).tail(200)


def aplicar_clima():
    """Re-aplica o clima escolhido (persistido em session_state) a cada tick.

    Fix: antes o lga.FORCA_CLIMA era setado só no script completo (sidebar). Nos ticks
    seguintes (fragmento run_every), o sidebar nao roda e nada reaplicava -> voltava ao
    padrao 'Forte'. Este helper roda no inicio de cada ciclo e usa o cenario persistido.
    """
    c = st.session_state.get("cenario_clima", "Forte")
    lga.FORCA_INTENSIDADE_MM_S = None
    if c == "Manual...":
        lga.FORCA_CLIMA = None
        lga.FORCA_INTENSIDADE_MM_S = float(st.session_state.get("chuva_manual", 0.12))
    elif c == "Real (API)":
        lga.FORCA_CLIMA = None
    elif c in ("Forte", "Moderada", "Nenhuma"):
        lga.FORCA_CLIMA = c
    else:
        lga.FORCA_CLIMA = "Forte"


def aplicar_valvula():
    """Re-aplica a atuação manual da válvula (persistida) em cada tick.

    Fix (mesmo padrão do clima): lga.FORCA_ABERTURA era setado só no sidebar; nos ticks
    seguintes (fragmento) isso se perdia. Aqui relemos do session_state a cada ciclo.
    """
    if st.session_state.get("manual_valvula", False):
        lga.FORCA_ABERTURA = {
            "PA": float(st.session_state.get("abertura_pa", 0)) / 100.0,
            "PB": float(st.session_state.get("abertura_pb", 0)) / 100.0,
        }
    else:
        lga.FORCA_ABERTURA = {}


def executar_ciclo():
    try:
        aplicar_clima()   # garante o cenário escolhido em cada tick (nao volta ao padrao)
        aplicar_valvula() # garante a atuação manual da válvula a cada tick
        # Seguranca: se ja ha HITL pendente, NAO re-stream (evita burlar a aprovacao)
        snap0 = st.session_state.agente.get_state(st.session_state.config_agente)
        if snap0 and snap0.next:
            return "⚠️ Aprovação Humana Necessária!"

        snap = None
        alerta = "Normal"
        cont = 0
        for _ in range(st.session_state.get("ciclos_render", SUBSTEPS_PER_TICK)):
            for _ev in st.session_state.agente.stream(
                    st.session_state.estado_atual, st.session_state.config_agente):
                pass
            snap = st.session_state.agente.get_state(st.session_state.config_agente)
            cont += 1
            if snap.next:
                alerta = "⚠️ Aprovação Humana Necessária!"
                break
        anexar_linha_historico(st.session_state.planta, snap, n_ciclos=cont)
        return alerta
    except Exception as e:
        st.error(f"Erro: {e}")
        return "Erro"


def avancar_ticks(n):
    """Avança EXATAMENTE n ciclos (passo manual), capturando cada tick no historico."""
    S = st.session_state
    try:
        aplicar_clima()   # garante o cenário escolhido em cada tick manual também
        aplicar_valvula() # garante a atuação manual da válvula a cada tick manual
        for _ in range(n):
            # bloqueia se houver HITL pendente (nao burla a aprovacao humana)
            snap0 = S.agente.get_state(S.config_agente)
            if snap0 and snap0.next:
                S.executando = False
                break
            for _ev in S.agente.stream(S.estado_atual, S.config_agente):
                pass
            snap = S.agente.get_state(S.config_agente)
            anexar_linha_historico(S.planta, snap, n_ciclos=1)
    except Exception as e:
        st.error(f"Erro ao avançar: {e}")


# ------------------------------ SIDEBAR ------------------------------
st.sidebar.title("🏭 Sala de Controle")

modo = st.sidebar.radio(
    "Modo de simulação",
    ["▶️ Contínuo", "📖 Manual (ticks)"],
    index=0,
    help="Contínuo: roda sozinho (Iniciar/Parar). Manual: avance exatamente 1/10/30 ciclos "
         "a cada clique nos botões de tick.")

if modo == "▶️ Contínuo":
    if st.sidebar.button("▶️ Iniciar"):
        st.session_state.executando = True
    if st.sidebar.button("⏹️ Parar"):
        st.session_state.executando = False
else:
    # Modo manual: para o loop contínuo e usa somente os botões de passo.
    st.session_state.executando = False
    st.sidebar.caption("Pausado — avance com os botões abaixo:")
    st.sidebar.markdown("**🔢 Passo manual (tick)**")
    if st.sidebar.button("⏪ 1 tick"):
        avancar_ticks(1)
        st.rerun()
    if st.sidebar.button("⏩ 10 ticks"):
        avancar_ticks(10)
        st.rerun()
    if st.sidebar.button("⏭️ 30 ticks"):
        avancar_ticks(30)
        st.rerun()
ciclos_render = st.sidebar.slider("Ciclos por atualização (movimento)", 5, 40, 14)
st.session_state.ciclos_render = ciclos_render

st.sidebar.markdown("---")
st.sidebar.subheader("🌤️ Clima (demo)")
lga.FORCA_INTENSIDADE_MM_S = None  # reseta manual a cada rerun
cenario = st.sidebar.selectbox(
    "Cenário de clima",
    ["Forte", "Moderada", "Nenhuma", "Manual...", "Real (API)"],
    index=0, key="cenario_clima",
    help="Forte/Moderada forçam chuva fixa; \"Manual...\" ajusta a chuva de forma contínua "
         "(slider); \"Real\" usa a API OpenWeather.",
)
if cenario == "Manual...":
    mm_s = st.sidebar.slider(
        "Intensidade da chuva (mm/s)", 0.0, 0.30, 0.12, 0.01, key="chuva_manual",
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
# Sliders SEMPRE visiveis e habilitados. Quando manual esta OFF, refletem a posicao
# REAL (automatica) da valvula — gravados no session_state ANTES de o widget nascer.
manual_val = st.sidebar.checkbox(
    "Atuação manual da válvula", value=False, key="manual_valvula",
    help="Define a abertura da válvula de drenagem manualmente, sobrepondo o controle PI/fuzzy.")
if not manual_val:
    st.session_state["abertura_pa"] = int(round(planta_bayer.t_paralelo_a.abertura_valvula * 100))
    st.session_state["abertura_pb"] = int(round(planta_bayer.t_paralelo_b.abertura_valvula * 100))
_pa = int(st.session_state.get("abertura_pa", 0))
_pb = int(st.session_state.get("abertura_pb", 0))
v_pa = st.sidebar.slider("Abertura PA (%)", 0, 100, _pa, 5, key="abertura_pa")
v_pb = st.sidebar.slider("Abertura PB (%)", 0, 100, _pb, 5, key="abertura_pb")
if manual_val:
    lga.FORCA_ABERTURA = {"PA": v_pa / 100.0, "PB": v_pb / 100.0}
    st.sidebar.caption("Controle automático sobreposto. Desligue p/ voltar ao automático.")
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

# ------------------------------ CORPO AO VIVO (fragmento) ------------------------------
st.title("🏭 Digital Twin - Processo Bayer")


@st.fragment(run_every=0.4)
def ao_vivo():
    """Atualizacao suave: so este bloco (KPIs+graficos+status+HITL) repinta a cada ~0,4s,
    sem re-renderizar a pagina inteira (evita o flicker de graficos e da msg de status)."""
    S = st.session_state

    # Se estiver executando, avanca a simulacao (varios ciclos) e coleta o alerta.
    alerta_ultimo = "Normal"
    if S.executando:
        alerta_ultimo = executar_ciclo()
        if "Humana" in alerta_ultimo:
            S.executando = False  # pausa e espera aprovacao (banner abaixo)

    df = S.historico
    # Sessao antiga (sem a coluna vazao_alimentacao): zera o historico p/ recomecar
    # com dados reais, em vez de deixar linhas antigas com vazao=0 (grafico 'morto').
    if not set(COLS_HIST).issubset(set(df.columns)):
        S.historico = pd.DataFrame(columns=COLS_HIST)
        df = S.historico
    snap = S.agente.get_state(S.config_agente)
    hitl_pendente = bool(snap and snap.next)

    # Status (msg nao pisca mais: senao so no fragmento, em cadencia calma)
    if S.executando:
        st.success("🟢 **Executando** — atualização a cada ~0,4 s")
    elif hitl_pendente:
        st.info("⏸️ **HITL: aguardando aprovação** (banner/botão abaixo)")
    else:
        st.info("⏹️ Pausado")

    # HITL em destaque no corpo
    if hitl_pendente:
        st.error("⚠️ **Ação Emergencial pendente de aprovação humana** — o loop pausou "
                 "(não é travamento). Aprove para liberar a ação.")
        if st.button("✅ Aprovar Ação Emergencial (libera o loop)", type="primary"):
            S.agente.update_state(S.config_agente, {"emergencia_aprovada": True},
                                  as_node="aguardar_operador")
            for _ in S.agente.stream(None, S.config_agente):
                pass
            S.executando = True

    if not df.empty:
        ultimo = df.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📊 Nível PA", f"{ultimo['nivel_PA']:.2f}%",
                  "Crítico!" if ultimo["nivel_PA"] > 80 else "OK")
        c2.metric("📊 Nível PB", f"{ultimo['nivel_PB']:.2f}%")
        c3.metric("🧪 TC Saída", f"{ultimo['tc_saida']:.1f} g/L")
        c4.metric("💧 Perda Soda",
                  f"{ultimo['soda_perdida_pa'] + ultimo['soda_perdida_pb']:.2f} kg/s")

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

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df["timestamp"], y=df["vazao_alimentacao"],
                                  name="Alimentação (L/s)", line=dict(color="cyan")))
        fig3.update_layout(title="Vazão de Alimentação", height=180, hovermode="x unified")
        st.plotly_chart(fig3, width="stretch", config={"displayModeBar": False})

        with st.expander("📋 Log de Eventos"):
            st.dataframe(df.tail(10)[["timestamp", "alerta_agente", "nivel_PA", "tc_saida"]])
    else:
        st.warning("Aguardando dados. Clique em Iniciar.")


ao_vivo()

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