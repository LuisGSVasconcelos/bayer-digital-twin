"""Estabilidade com TODOS os disturbios ativos (chuva Forte)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import langgraph_agent as agent
import bayer_process_simulator as sim
import adaptive_fuzzy_controller as afc

agent.VERBOSE = False; sim.VERBOSE = False; afc.VERBOSE = False
agent.FORCA_CLIMA = "Forte"; agent.FORCA_INTENSIDADE_MM_S = None
p = agent.planta_bayer
p.gerador.ativo = True
p.gerador.config.pop("only_chemistry", None)
p.gerador.config["disturbios_habilitados"] = {}   # todos ligados
p.gerador.config["spike_sensor"]["probabilidade"] = 0.0
p.t_paralelo_a.volume = p.t_paralelo_a.capacidade * 0.805
p.t_paralelo_b.volume = p.t_paralelo_b.capacidade * 0.70
p.t_paralelo_a._integ = 0.0; p.t_paralelo_b._integ = 0.0
agent.fuzzy_ctrl_pa.reset(); agent.fuzzy_ctrl_pb.reset()
agent.app = agent.build_app()
cfg = {"configurable": {"thread_id": "todos"}}
INIT = dict(agent.estado_inicial)

for _e in agent.app.stream(INIT, cfg): pass
agent.app.update_state(cfg, {"emergencia_aprovada": True}, as_node="aguardar_operador")
for _ in agent.app.stream(None, cfg): pass

vals = []; lvls = []
for i in range(4000):
    for _e in agent.app.stream(INIT, cfg): pass
    vals.append(p.t_paralelo_a.abertura_valvula)
    lvls.append(p.t_paralelo_a.percentual)
# transicoes em todo o horizonte
t_all = sum(1 for a, b in zip(vals, vals[1:]) if (a < 0.2) != (b < 0.2))
s = lvls[-1500:]
print(f"Nivel PA: media={sum(s)/len(s):.2f} min={min(s):.2f} max={max(s):.2f} (ult.1500)")
print(f"Valvula: transicoes={t_all}/{len(vals)} | ult.500 zebra min={min(vals[-500:]):.2f} max={max(vals[-500:]):.2f}")
print("ESTAVEL" if min(lvls) > 55 else "INESTAVEL (nivel baixou muito)")