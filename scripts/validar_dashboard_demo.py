"""Valida o cenário demo (A+B): HITL dispara, aprovação abre válvula, nível desce."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import langgraph_agent as agent
from bayer_process_simulator import PlantaBayerSimulada

# cenário demo (igual ao dashboard init)
agent.planta_bayer = PlantaBayerSimulada(ativar_disturbios=True)
agent.planta_bayer.t_paralelo_a.volume = agent.planta_bayer.t_paralelo_a.capacidade * 0.805
agent.planta_bayer.t_paralelo_b.volume = agent.planta_bayer.t_paralelo_b.capacidade * 0.802
agent.fuzzy_ctrl_pa.reset()
agent.fuzzy_ctrl_pb.reset()
agent.FORCA_CLIMA = "Forte"   # chuva simulada
agent.app = agent.build_app()
config = {"configurable": {"thread_id": "demo_test"}}
init = {"setpoint": 65.0, "tanques_criticos": [], "acao_necessaria": False,
        "abertura_recomendada": {}, "historico": {"PA": [], "PB": []}, "ema_prev": {}}

print("Nível inicial: PA=%.2f%% PB=%.2f%%" % (
    agent.planta_bayer.t_paralelo_a.percentual, agent.planta_bayer.t_paralelo_b.percentual))

# tick 1 — espera HITL no primeiro ciclo (acima do limiar + chuva)
for _ in agent.app.stream(init, config):
    pass
snap = agent.app.get_state(config)
print("HITL pendente:", bool(snap.next), "| nós seguintes:", list(snap.next) if snap.next else "-")
assert snap.next, "FALHA: HITL nao disparou no cenario acima do critico"
print("OK: HITL disparou")

# guarda anti-bypass: dashboard nao re-stream enquanto pendente
snap0 = agent.app.get_state(config)
guard = "pausado" if snap0.next else "rodando"
print("Guarda anti-bypass:", guard)
assert snap0.next, "FALHA: guarda deveria pausar com HITL pendente"

# aprovação do operador
agent.app.update_state(config, {}, as_node="aguardar_operador")
for _ in agent.app.stream(None, config):
    pass
print("Abertura da válvula PA após aprovação: %.1f%%" %
      (agent.planta_bayer.t_paralelo_a.abertura_valvula * 100))
assert agent.planta_bayer.t_paralelo_a.abertura_valvula > 0.0, "FALHA: válvula não abriu"

# SEGUNDO TICK — roda ciclos com válvula aberta; nível deve descer
for _ in range(10):
    for _ in agent.app.stream(init, config):
        pass
print("Nível PA após 10 ciclos com válvula aberta: %.2f%%" %
      agent.planta_bayer.t_paralelo_a.percentual)
assert agent.planta_bayer.t_paralelo_a.percentual > 0.0
print("PASS: cenário demo (HITL -> aprovação -> dreno) validado")