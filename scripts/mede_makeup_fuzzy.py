"""Mede oscilacao do makeup no controle fuzzy (transicoes 0<->aberto)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import langgraph_agent as agent
import bayer_process_simulator as sim
import adaptive_fuzzy_controller as afc

def mede(desc, clima, N=3000):
    agent.VERBOSE = False; sim.VERBOSE = False; afc.VERBOSE = False
    agent.FORCA_CLIMA = clima; agent.FORCA_INTENSIDADE_MM_S = None; agent.MODO_CONTROLE = "fuzzy"
    p = agent.planta_bayer
    p.gerador.ativo = True
    p.gerador.config.pop("only_chemistry", None)
    p.gerador.config["disturbios_habilitados"] = {}
    p.gerador.config["spike_sensor"]["probabilidade"] = 0.0
    p.t_paralelo_a.volume = p.t_paralelo_a.capacidade * 0.70   # forca cenarios
    p.t_paralelo_b.volume = p.t_paralelo_b.capacidade * 0.70
    for t_ in (p.t_paralelo_a, p.t_paralelo_b):
        t_._integ = 0.0; t_._integ_mk = 0.0; t_._prev_erro = 0.0
        t_._fuzz_d = 0.0; t_._fuzz_mk = 0.0
    agent.fuzzy_ctrl_pa.reset(); agent.fuzzy_ctrl_pb.reset()
    agent.fuzzy_mk_pa.reset(); agent.fuzzy_mk_pb.reset()
    agent.app = agent.build_app()
    cfg = {"configurable": {"thread_id": desc}}
    INIT = dict(agent.estado_inicial)
    for _e in agent.app.stream(INIT, cfg): pass
    agent.app.update_state(cfg, {"emergencia_aprovada": True}, as_node="aguardar_operador")
    for _ in agent.app.stream(None, cfg): pass
    mk = []; lv = []
    for _ in range(N):
        for _e in agent.app.stream(INIT, cfg): pass
        mk.append(p.t_paralelo_a.abertura_makeup)
        lv.append(p.t_paralelo_a.percentual)
    s = mk[-1200:]
    trans = sum(1 for a, b in zip(s, s[1:]) if (a < 0.2) != (b < 0.2))
    lvs = lv[-1200:]
    print(f"{desc:16s} makeup regime: min={min(s):.2f} max={max(s):.2f} media={sum(s)/len(s):.2f} "
          f"transicoes(0<->aberto)={trans}/1199 | nivel media={sum(lvs)/len(lvs):.2f} min={min(lvs):.2f}")

mede("fuzzy chuva Forte", "Forte")
mede("fuzzy sem chuva", "Nenhuma")