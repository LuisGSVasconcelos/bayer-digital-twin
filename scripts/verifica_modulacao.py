"""Conferencia: a valvula modula (nao oscila 0-100). Conta saltos 'flicker'."""
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
    if hasattr(p.t_paralelo_a, "_integ"): p.t_paralelo_a._integ = 0.0
    if hasattr(p.t_paralelo_b, "_integ"): p.t_paralelo_b._integ = 0.0
    agent.fuzzy_ctrl_pa.reset(); agent.fuzzy_ctrl_pb.reset()
    agent.app = agent.build_app()
    cfg = {"configurable": {"thread_id": "m" + cen}}
    INIT = dict(agent.estado_inicial)

    for _e in agent.app.stream(INIT, cfg): pass
    agent.app.update_state(cfg, {"emergencia_aprovada": True}, as_node="aguardar_operador")
    for _ in agent.app.stream(None, cfg): pass

    vals = []
    mineralvl = 99.0
    for i in range(700):
        for _e in agent.app.stream(INIT, cfg): pass
        vals.append(p.t_paralelo_a.abertura_valvula)
        mineralvl = min(mineralvl, p.t_paralelo_a.percentual)
    # saltos entre adjacentes: |a-b| > 0.6 = flicker 0<->100
    flick = sum(1 for a, b in zip(vals, vals[1:]) if abs(a - b) > 0.6)
    print(f"[chuva {cen:8s}] abertura_final={vals[-1]:.2f} range=({min(vals):.2f},{max(vals):.2f}) "
          f"flickers(>0.6)={flick} | min nivel={mineralvl:.2f}")