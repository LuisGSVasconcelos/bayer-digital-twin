"""Conferencia no regime estabilizado: a valvula oscila sob chuva? Conta transicoes 0<->aberto."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import langgraph_agent as agent
import bayer_process_simulator as sim
import adaptive_fuzzy_controller as afc

for cen in ["Forte", "Moderada", "Nenhuma"]:
    agent.VERBOSE = False; sim.VERBOSE = False; afc.VERBOSE = False
    agent.FORCA_CLIMA = cen
    p = agent.planta_bayer
    p.gerador.ativo = False
    p.gerador.config["spike_sensor"]["probabilidade"] = 0.0
    p.t_paralelo_a.volume = p.t_paralelo_a.capacidade * 0.805
    p.t_paralelo_b.volume = p.t_paralelo_b.capacidade * 0.70
    p.t_paralelo_a._integ = 0.0
    p.t_paralelo_b._integ = 0.0
    agent.fuzzy_ctrl_pa.reset(); agent.fuzzy_ctrl_pb.reset()
    agent.app = agent.build_app()
    cfg = {"configurable": {"thread_id": "s" + cen}}
    INIT = dict(agent.estado_inicial)

    for _e in agent.app.stream(INIT, cfg): pass
    agent.app.update_state(cfg, {"emergencia_aprovada": True}, as_node="aguardar_operador")
    for _ in agent.app.stream(None, cfg): pass

    N = 1800
    vals = []; lvls = []
    for i in range(N):
        for _e in agent.app.stream(INIT, cfg): pass
        vals.append(p.t_paralelo_a.abertura_valvula)
        lvls.append(p.t_paralelo_a.percentual)
    # regime estabilizado = ultimos 300 ciclos
    settle = vals[-300:]; lvls_settle = lvls[-300:]
    # transicoes 0<->aberto >0.5 = oscilacao bang-bang
    trans = sum(1 for a, b in zip(settle, settle[1:]) if (a < 0.2) != (b < 0.2))
    print(f"[{cen:8s}] valvula regime=({min(settle):.2f},{max(settle):.2f}) "
          f"transicoes(0<->aberto)={trans}/299 | nivel media={sum(lvls_settle)/len(lvls_settle):.2f} "
          f"min={min(lvls_settle):.2f}")