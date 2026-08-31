"""Agente LangGraph de supervisao do Processo Bayer.

Fluxo: coleta -> analise -> calcular_controle -> [HITL se critico] -> executar.

Correcoes aplicadas vs. roteiro original:
  A3: um controlador AdaptiveFuzzyController POR tanque (PA e PB sao
      independentes e intencionalmente desbalanceados).
  A4: o limiar critico usa o nivel filtrado por EMA, nao o bruto (com spike).
  M6: historico/tendencia/ema sao copiados (nao mutados in-place) no estado.
"""
import time
from typing import Dict, List, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from bayer_process_simulator import PlantaBayerSimulada
from adaptive_fuzzy_controller import AdaptiveFuzzyController
from weather_service import weather_service

try:
    from influx_persister import influx_db
except Exception:  # pragma: no cover
    influx_db = None

# ----------------------------------------------------------------------------
# Instancias globais (Gemeo Digital + controladores)
# ----------------------------------------------------------------------------
planta_bayer = PlantaBayerSimulada(ativar_disturbios=True)

# A3: um controlador fuzzy adaptativo por decantador
fuzzy_ctrl_pa = AdaptiveFuzzyController(taxa_aprendizado=0.001, momentum=0.9, ganho_min=0.5, ganho_max=1.8)
fuzzy_ctrl_pb = AdaptiveFuzzyController(taxa_aprendizado=0.001, momentum=0.9, ganho_min=0.5, ganho_max=1.8)
FUZZY_CTRL = {"PA": fuzzy_ctrl_pa, "PB": fuzzy_ctrl_pb}

ALPHA_EMA = 0.3
LIMITE_ALTO = 80.0   # nivel filtrado acima do qual e critico incondicionalmente
LIMITE_TEND = 70.0   # acima do qual importa a tendencia
TEND_LIMITE = 1.0


# ----------------------------------------------------------------------------
# Estado
# ----------------------------------------------------------------------------
class BayerState(TypedDict):
    telemetria: Dict[str, float]
    niveis_filtrados: Dict[str, float]       # EMA (usado no limiar critico, A4)
    tendencia_suavizada: Dict[str, float]
    historico: Dict[str, List[float]]
    ema_prev: Dict[str, float]
    previsao_chuva: str
    tanques_criticos: list
    acao_necessaria: bool
    setpoint: float
    abertura_recomendada: Dict[str, float]
    chuva_atual_mm_h: float
    descricao_clima: str
    alerta_meteorologico: str
    teor_sio2_atual: float
    soda_perdida: Dict[str, float]
    tc_saida_decantadores: float


FORCA_CLIMA: str | None = None  # demo offline: "Forte" | "Moderada" | "Nenhuma" | None
VERBOSE = True  # False silencia floods de print por ciclo (usado no dashboard)


def obter_chuva():
    """Wraper de leitura do clima. Separado para permitir mock em testes.

    Se FORCA_CLIMA estiver definido, ignora a API e usa um cenário simulado
    (útil para demonstração offline, sem chave OpenWeather).
    """
    if FORCA_CLIMA in ("Forte", "Moderada", "Nenhuma"):
        mapa = {
            "Forte": (12.0, "chuva forte (simulada)", "ALERTA: chuva forte simulada"),
            "Moderada": (0.5, "chuva moderada (simulada)", "chuva moderada simulada"),
            "Nenhuma": (0.0, "tempo seco (simulado)", "sem chuva (simulada)"),
        }
        return mapa[FORCA_CLIMA]
    try:
        return weather_service.get_rain_intensity()
    except Exception:
        return 0.0, "indisponível", "⚠️ Falha na consulta"


# ----------------------------------------------------------------------------
# Utilitario EMA / tendencia
# ----------------------------------------------------------------------------
def atualizar_ema_e_tendencia(nivel_bruto: float, ema_anterior) -> tuple:
    if ema_anterior is None or ema_anterior == 0.0:
        return nivel_bruto, 0.0
    ema_atual = (nivel_bruto * ALPHA_EMA) + (ema_anterior * (1 - ALPHA_EMA))
    tendencia = ema_atual - ema_anterior
    return ema_atual, tendencia


# ----------------------------------------------------------------------------
# Nos do grafo
# ----------------------------------------------------------------------------
def ler_sensores_planta(state: BayerState) -> Dict:
    intensidade, desc, alerta = obter_chuva()
    if VERBOSE:
        print(f"\n🌦️ Chuva: {intensidade} mm/h | {desc}")

    if intensidade == 0:
        clima = "Nenhuma"
    elif intensidade < 1.0:
        clima = "Moderada"
    else:
        clima = "Forte"

    planta_bayer.rodar_ciclo_fisica(clima)
    niveis = planta_bayer.obter_status_sensores()

    nivel_pa_bruto = planta_bayer.gerador.aplicar_spike_sensor(niveis["PA"])
    nivel_pb_bruto = planta_bayer.gerador.aplicar_spike_sensor(niveis["PB"])

    prev = state.get("ema_prev", {}) or {}
    ema_pa, tend_pa = atualizar_ema_e_tendencia(nivel_pa_bruto, prev.get("PA"))
    ema_pb, tend_pb = atualizar_ema_e_tendencia(nivel_pb_bruto, prev.get("PB"))

    # M6: copia do historico (sem mutar a lista no estado do LangGraph)
    hist = state.get("historico", {}) or {}
    hist_pa = list(hist.get("PA", [])) + [nivel_pa_bruto]
    hist_pb = list(hist.get("PB", [])) + [nivel_pb_bruto]
    hist_pa = hist_pa[-10:]
    hist_pb = hist_pb[-10:]

    aberturas = {"PA": planta_bayer.t_paralelo_a.abertura_valvula,
                 "PB": planta_bayer.t_paralelo_b.abertura_valvula}
    if influx_db is not None:
        try:
            influx_db.persistir_estado(int(time.time()), state, niveis, aberturas, intensidade, alerta)
        except Exception as e:
            print(f"  ⚠️ InfluxDB indisponível: {e}")

    return {
        "telemetria": dict(niveis),
        "niveis_filtrados": {"PA": round(ema_pa, 3), "PB": round(ema_pb, 3)},
        "tendencia_suavizada": {"PA": round(tend_pa, 3), "PB": round(tend_pb, 3)},
        "historico": {"PA": hist_pa, "PB": hist_pb},
        "ema_prev": {"PA": round(ema_pa, 3), "PB": round(ema_pb, 3)},
        "previsao_chuva": clima,
        "chuva_atual_mm_h": intensidade,
        "descricao_clima": desc,
        "alerta_meteorologico": alerta,
        "soda_perdida": {"PA": planta_bayer.t_paralelo_a.soda_perdida_lama,
                         "PB": planta_bayer.t_paralelo_b.soda_perdida_lama},
        "tc_saida_decantadores": round((planta_bayer.t_paralelo_a.tc + planta_bayer.t_paralelo_b.tc) / 2.0, 2),
        "teor_sio2_atual": planta_bayer.gerador.config["silica"]["base"],
    }


def avaliar_risco_bayer(state: BayerState) -> Dict:
    """A4: limiar critico usa a ENTRADA FILTRADA por EMA (nao o bruto com spike)."""
    chuva = state.get("previsao_chuva", "Nenhuma")
    filtrados = state.get("niveis_filtrados", {}) or {}
    tend = state.get("tendencia_suavizada", {}) or {}

    criticos = []
    for tid in ["PA", "PB"]:
        nivel_f = filtrados.get(tid, 0.0)
        tend_t = tend.get(tid, 0.0)
        if (nivel_f > LIMITE_TEND and tend_t > TEND_LIMITE) or nivel_f > LIMITE_ALTO:
            criticos.append(tid)

    acao = len(criticos) > 0 and chuva in ("Moderada", "Forte")
    return {"tanques_criticos": criticos, "acao_necessaria": acao}


def calcular_controle(state: BayerState) -> Dict:
    """A3: controlador independente por tanque (PA/PB) usando nivel filtrado."""
    setpoint = state.get("setpoint", 65.0)
    filtrados = state.get("niveis_filtrados", {}) or {}
    tend = state.get("tendencia_suavizada", {}) or {}

    aberturas = {}
    for tid, ctrl in FUZZY_CTRL.items():
        nivel = filtrados.get(tid, 0.0)
        deriv = tend.get(tid, 0.0)
        erro = nivel - setpoint
        abertura = ctrl.calcular_abertura(erro, deriv)
        aberturas[tid] = round(abertura, 3)
        if VERBOSE:
            print(f"🎛️ [FUZZY ADAPT {tid}] Erro={erro:.1f}% Deriv={deriv:.2f} "
                  f"-> Abertura={abertura * 100:.1f}% (Ganho={ctrl.ganho:.3f})")

    return {"abertura_recomendada": aberturas}


def executar_controle_fisico(state: BayerState) -> Dict:
    aberturas = state.get("abertura_recomendada", {}) or {}
    if VERBOSE:
        print("\n⚙️ [AUTOMAÇÃO] Controle modulante das válvulas de drenagem...")
    # Regulador proporcional: abre a valvula conforme o erro (nivel - setpoint)
    # e fecha no/nas setpoint. HITL (ramo critico) gateia apenas a emergência.
    planta_bayer.t_paralelo_a.abertura_valvula = aberturas.get("PA", 0.0)
    planta_bayer.t_paralelo_b.abertura_valvula = aberturas.get("PB", 0.0)
    if VERBOSE:
        print(f"  ✅ PA: {aberturas.get('PA', 0.0) * 100:.1f}% "
              f"| PB: {aberturas.get('PB', 0.0) * 100:.1f}%")
    return {}


def rotear_fluxo(state: BayerState) -> str:
    # Critico + chuva -> HITL; caso contrario vai ao controle modulante (valvulares).
    if state.get("acao_necessaria", False):
        return "aguardar_operador"
    return "executar_controle"


# ----------------------------------------------------------------------------
# Construcao do grafo
# ----------------------------------------------------------------------------
def build_app():
    builder = StateGraph(BayerState)
    builder.add_node("coleta", ler_sensores_planta)
    builder.add_node("analise", avaliar_risco_bayer)
    builder.add_node("calcular_controle", calcular_controle)
    builder.add_node("aguardar_operador", lambda state: {})
    builder.add_node("executar_controle", executar_controle_fisico)

    builder.set_entry_point("coleta")
    builder.add_edge("coleta", "analise")
    builder.add_edge("analise", "calcular_controle")
    builder.add_conditional_edges(
        "calcular_controle", rotear_fluxo,
        {"aguardar_operador": "aguardar_operador", "executar_controle": "executar_controle"},
    )
    builder.add_edge("aguardar_operador", "executar_controle")
    builder.add_edge("executar_controle", END)

    return builder.compile(checkpointer=MemorySaver(), interrupt_before=["aguardar_operador"])


app = build_app()
config = {"configurable": {"thread_id": "default_plant"}}
estado_inicial = {
    "setpoint": 65.0,
    "tanques_criticos": [],
    "acao_necessaria": False,
    "abertura_recomendada": {},
    "historico": {"PA": [], "PB": []},
    "ema_prev": {},
}


if __name__ == "__main__":
    # Demonstracao: roda alguns ciclos e, se houver interrupcao HITL,
    # pede aprovacao para destravar a execucao fisica.
    for ciclo in range(1, 6):
        print(f"\n⏱️ Ciclo de Operação {ciclo}")
        for _ in app.stream(estado_inicial, config):
            pass

        snap = app.get_state(config)
        if snap.next:
            print("\n🚨 [SALA DE CONTROLE] Aprovação humana necessária!")
            decisao = input("Autorizar abertura emergencial das válvulas? (s/n): ").strip().lower()
            if decisao == "s":
                app.update_state(config, {}, as_node="aguardar_operador")
                for _ in app.stream(None, config):
                    pass
            else:
                print("🛑 Operador recusou a ação.")
                break
        time.sleep(0.5)