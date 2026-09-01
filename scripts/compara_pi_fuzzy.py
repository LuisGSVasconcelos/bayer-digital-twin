"""Compara PI (bidirecional) vs Fuzzy Adaptativo no mesmo cenario (chuva Forte)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import langgraph_agent as agent
import bayer_process_simulator as sim
import adaptive_fuzzy_controller as afc

def roda(desc, modo, N=3000):
    agent.VERBOSE = False; sim.VERBOSE = False; afc.VERBOSE = False
    agent.FORCA_CLIMA = "Forte"; agent.FORCA_INTENSIDADE_MM_S = None; agent.MODO_CONTROLE = modo
    p = agent.planta_bayer
    p.gerador.ativo = True
    p.gerador.config.pop("only_chemistry", None)
    p.gerador.config["disturbios_habilitados"] = {}
    p.gerador.config["spike_sensor"]["probabilidade"] = 0.0
    p.t_paralelo_a.volume = p.t_paralelo_a.capacidade * 0.805
    p.t_paralelo_b.volume = p.t_paralelo_b.capacidade * 0.70
    for t_ in (p.t_paralelo_a, p.t_paralelo_b):
        t_._integ = 0.0; t_._integ_mk = 0.0; t_._prev_erro = 0.0
    agent.fuzzy_ctrl_pa.reset(); agent.fuzzy_ctrl_pb.reset()
    agent.app = agent.build_app()
    cfg = {"configurable": {"thread_id": desc}}
    INIT = dict(agent.estado_inicial)
    for _e in agent.app.stream(INIT, cfg): pass
    agent.app.update_state(cfg, {"emergencia_aprovada": True}, as_node="aguardar_operador")
    for _ in agent.app.stream(None, cfg): pass
    lvls = []; mk = []
    for _ in range(N):
        for _e in agent.app.stream(INIT, cfg): pass
        lvls.append(p.t_paralelo_a.percentual)
        mk.append(p.t_paralelo_a.abertura_makeup)
    print(f"{desc:16s} final={lvls[-1]:5.2f}% min={min(lvls):5.2f}% "
          f"media={sum(lvls[-1000:])/1000:5.2f} | makeup_media={sum(mk[-1000:])/1000:.2f}")

roda("PI", "pi")
roda("Fuzzy", "fuzzy")