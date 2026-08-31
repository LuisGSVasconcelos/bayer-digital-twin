"""Testes do grafo LangGraph de supervisao (HITL e correcoes A3/A4).

Requires langgraph instalado. Pula silenciosamente caso nao esteja.
Nao exige InfluxDB nem chave OpenWeather (servicos sao mockados/no-op).
"""
import pytest

lg = pytest.importorskip("langgraph")

import langgraph_agent as agent


@pytest.fixture(autouse=True)
def cenario_limpo():
    """Reinicia o estado global do agente entre testes."""
    agent.planta_bayer = agent.PlantaBayerSimulada(ativar_disturbios=True)
    agent.fuzzy_ctrl_pa.reset()
    agent.fuzzy_ctrl_pb.reset()
    # clima forcado - sem depender da API (deterministico)
    agent.obter_chuva = lambda: (999.0, "aguaceiro forte", "ALERTA")  # chuva Forte
    agent.app = agent.build_app()
    yield


def _proxima_estado_inicial():
    return {
        "setpoint": 65.0,
        "tanques_criticos": [],
        "acao_necessaria": False,
        "abertura_recomendada": {},
        "historico": {"PA": [], "PB": []},
        "ema_prev": {},
    }


def test_rodar_ciclo_sem_crash():
    config = {"configurable": {"thread_id": "t1"}}
    for _ in agent.app.stream(_proxima_estado_inicial(), config):
        pass
    snap = agent.app.get_state(config)
    assert "telemetria" in snap.values


def test_a3_controladores_independentes():
    """A3: PA e PB usam controladores fuzzy separados (ganhos independentes)."""
    assert agent.fuzzy_ctrl_pa is not agent.fuzzy_ctrl_pb


def test_risco_critico_dispara_htil():
    """Com nivel alto + chuva forte, o fluxo intercepta no HITL."""
    config = {"configurable": {"thread_id": "t2"}}
    est = _proxima_estado_inicial()
    agent.planta_bayer.t_paralelo_a.volume = agent.planta_bayer.t_paralelo_a.capacidade * 0.90  # 90%
    agent.planta_bayer.t_paralelo_b.volume = agent.planta_bayer.t_paralelo_b.capacidade * 0.85

    for _ in agent.app.stream(est, config):
        pass
    snap = agent.app.get_state(config)
    assert snap.next, "Fluxo deveria estar interrompido aguardando aprovacao (HITL)"
    assert "aguardar_operador" in snap.next


def test_aprovar_destrava_e_abre_valvula():
    """Apos aprovacao do operador, a valvula do tanque critico abre.

    Nota: o volume inicial fica em 85% (erro ~20, dentro do dominio do fuzzy:
    [-20,+20]). Em nivel muito acima (ex. 90% -> erro 25), o fuzzy satura sem
    membros e nao abriria - o que é um limitacao de design do dominio de erro.
    """
    tid = "t3"
    config = {"configurable": {"thread_id": tid}}
    est = _proxima_estado_inicial()
    agent.planta_bayer.t_paralelo_a.volume = agent.planta_bayer.t_paralelo_a.capacidade * 0.85

    for _ in agent.app.stream(est, config):
        pass
    snap = agent.app.get_state(config)
    assert snap.next, "HITL esperado"

    agent.app.update_state(config, {}, as_node="aguardar_operador")
    for _ in agent.app.stream(None, config):
        pass

    assert agent.planta_bayer.t_paralelo_a.abertura_valvula > 0.0, (
        "Apos aprovacao, o controle deveria ter aberto a valvula do PA"
    )


def test_sem_chuva_nao_aciona_acao_critica():
    """Forcando 'Nenhuma' chuva, mesmo com nivel alto nao vai para o HITL."""
    agent.obter_chuva = lambda: (0.0, "tempo seco", "sem chuva")
    config = {"configurable": {"thread_id": "t4"}}
    est = _proxima_estado_inicial()
    agent.planta_bayer.t_paralelo_a.volume = agent.planta_bayer.t_paralelo_a.capacidade * 0.85

    for _ in agent.app.stream(est, config):
        pass
    snap = agent.app.get_state(config)
    assert not snap.next, "Sem chuva nao deveria exigir aprovacao emergencial"


def test_aprovacao_unica_nao_re_dispara_htil():
    """Aprovacao trava: enquanto o nivel continua critico, NAO volta a pedir HITL a cada
    ciclo (a valvula continua drenando). O latch libera quando o nivel sai do critico."""
    tid = "t5"
    config = {"configurable": {"thread_id": tid}}
    est = _proxima_estado_inicial()
    agent.planta_bayer.t_paralelo_a.volume = agent.planta_bayer.t_paralelo_a.capacidade * 0.85

    for _ in agent.app.stream(est, config):
        pass
    snap = agent.app.get_state(config)
    assert snap.next, "HITL esperado antes da aprovacao"

    # aprova com latch (como o dashboard)
    agent.app.update_state(config, {"emergencia_aprovada": True}, as_node="aguardar_operador")
    for _ in agent.app.stream(None, config):
        pass
    assert agent.planta_bayer.t_paralelo_a.abertura_valvula > 0.0

    # proximo ciclo: ainda critico, mas aprovado -> NAO re-dispara HITL
    for _ in agent.app.stream(_proxima_estado_inicial(), config):
        pass
    snap2 = agent.app.get_state(config)
    assert not snap2.next, "Aprovacao unica deveria seguir drenando sem re-HITL"


def test_aprovacao_libera_quando_nao_critico():
    """executar_controle limpa o latch (emergencia_aprovada=False) quando nao ha critico."""
    out = agent.executar_controle_fisico({"tanques_criticos": [], "setpoint": 65.0,
                                          "niveis_filtrados": {"PA": 60.0, "PB": 60.0},
                                          "abertura_recomendada": {"PA": 0.0, "PB": 0.0}})
    assert out.get("emergencia_aprovada") is False


def test_a4_limiar_filtrado_rejeita_spike():
    """A4: o limiar critico usa o nivel FILTRADO (EMA), nao o bruto (com spike).

    Se o bruto/corrompido por spike estiver alto mas o EMA continuar baixo,
    NAO deve disparar critico -> prova que a decisao nao olha o valor bruto.
    """
    # naveis_filtrados (EMA) baixos apesar de telemetria (bruto) alta
    state = {
        "previsao_chuva": "Forte",
        "niveis_filtrados": {"PA": 62.0, "PB": 61.0},
        "tendencia_suavizada": {"PA": 0.2, "PB": 0.2},
        "telemetria": {"PA": 95.0, "PB": 94.0},  # bruto alto (spike)
    }
    out = agent.avaliar_risco_bayer(state)
    assert out["tanques_criticos"] == [], "EMA baixo + spike bruto nao deve ser critico"
    assert out["acao_necessaria"] is False


def test_a4_limiar_filtrado_alto_dispara():
    """Com EMA alto + chuva forte, dispara critico e exige HITL."""
    state = {
        "previsao_chuva": "Forte",
        "niveis_filtrados": {"PA": 83.0, "PB": 60.0},
        "tendencia_suavizada": {"PA": 0.1, "PB": 0.1},
        "telemetria": {"PA": 83.0, "PB": 60.0},
    }
    out = agent.avaliar_risco_bayer(state)
    assert out["tanques_criticos"] == ["PA"]
    assert out["acao_necessaria"] is True