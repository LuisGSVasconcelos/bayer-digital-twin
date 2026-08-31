"""Valida regulação pós-aprovação: nivel assenta no setpoint (~65), sem esvaziar/re-alarme."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import langgraph_agent as agent
import bayer_process_simulator as sim
import adaptive_fuzzy_controller as afc

agent.VERBOSE = False; sim.VERBOSE = False; afc.VERBOSE = False
agent.FORCA_CLIMA = "Forte"
p = agent.planta_bayer
p.gerador.config["spike_sensor"]["probabilidade"] = 0.0
p.t_paralelo_a.volume = p.t_paralelo_a.capacidade * 0.805
p.t_paralelo_b.volume = p.t_paralelo_b.capacidade * 0.803
agent.fuzzy_ctrl_pa.reset(); agent.fuzzy_ctrl_pb.reset()
agent.app = agent.build_app()
cfg = {"configurable": {"thread_id": "settle"}}
INIT = dict(agent.estado_inicial)

# HITL no 1o ciclo (PA 80.5 > 80)
for _e in agent.app.stream(INIT, cfg): pass
assert agent.app.get_state(cfg).next, "HITL esperado no 1o ciclo"
print("HITL no 1o ciclo ✓")

# aprovar
agent.app.update_state(cfg, {}, as_node="aguardar_operador")
for _ in agent.app.stream(None, cfg): pass
print("aprovado, abertura inicial:", round(p.t_paralelo_a.abertura_valvula, 2))

# rodar muitos ciclos (regulacao) ate assentar no setpoint; printar a cada 40
hist = []
for i in range(400):
    for _e in agent.app.stream(INIT, cfg): pass
    hist.append((i, p.t_paralelo_a.percentual, p.t_paralelo_a.abertura_valvula))
    if i % 40 == 0:
        print(f"  cyc{i}: PA={p.t_paralelo_a.percentual:.2f}% abertura={p.t_paralelo_a.abertura_valvula:.2f}")

final = p.t_paralelo_a.percentual
minlvl = min(h[1] for h in hist)
print(f"FINAL PA={final:.2f}% | minimo observado={minlvl:.2f}%")
assert minlvl > 45, "FALHA: esvaziou (controle nao deveria drenar abaixo de 45)"
assert 58 <= final <= 68, f"FALHA: nao assentou perto do setpoint (final={final:.1f})"
assert not agent.app.get_state(cfg).next, "FALHA: re-disparou HITL"
print("PASS: controle regula ate ~setpoint e segura (sem esvaziar, sem re-alarme)")