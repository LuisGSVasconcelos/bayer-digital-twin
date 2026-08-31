"""Valida o cenário demo corrigido: inicia ABAIXO de 80, sobe livre, cruza 80 (HITL),
aprovação abre a válvula e o nível desce (sem freeze/re-trigger infinito)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import langgraph_agent as agent
from bayer_process_simulator import PlantaBayerSimulada

agent.planta_bayer = PlantaBayerSimulada(ativar_disturbios=True)
agent.planta_bayer.t_paralelo_a.volume = agent.planta_bayer.t_paralelo_a.capacidade * 0.795
agent.planta_bayer.t_paralelo_b.volume = agent.planta_bayer.t_paralelo_b.capacidade * 0.790
agent.planta_bayer.gerador.config["spike_sensor"]["probabilidade"] = 0.0  # demo limpa
agent.fuzzy_ctrl_pa.reset(); agent.fuzzy_ctrl_pb.reset()
agent.FORCA_CLIMA = "Forte"
agent.app = agent.build_app()
config = {"configurable": {"thread_id": "demo2"}}
init = {"setpoint": 65.0, "tanques_criticos": [], "acao_necessaria": False,
        "abertura_recomendada": {}, "historico": {"PA": [], "PB": []}, "ema_prev": {}}

pA = agent.planta_bayer.t_paralelo_a
print(f"Início: PA={pA.percentual:.2f}%")

# 1) primeiro ciclo deve rodar LIVRE (sem HITL) - nao congelado
agent.app = agent.build_app()
for _ in agent.app.stream(init, config):
    pass
snap = agent.app.get_state(config)
print("1º ciclo livre (sem HITL):", not snap.next)
assert not snap.next, "FALHA: deveria rodar livre abaixo de 80"

# 2) rodar ate cruzar 80 (HITL) - com limite
cicl = 0
while not snap.next and cicl < 6000:
    for _ in agent.app.stream(init, config):
        pass
    snap = agent.app.get_state(config)
    cicl += 1
print(f"Após {cicl} ciclos -> HITL? {bool(snap.next)} | PA={pA.percentual:.2f}%")
assert snap.next, "FALHA: nao disparou HITL apos subir"
assert pA.percentual > 80.0, "FALHA: HITL nao veio da subida REAL (nivel >80)"

# 3) guarda (pausa) enquanto pendente
assert agent.app.get_state(config).next, "FALHA: guarda deveria pausar"

# 4) aprovacao
agent.app.update_state(config, {}, as_node="aguardar_operador")
for _ in agent.app.stream(None, config):
    pass
print(f"Abertura válvula PA pós-aprovação: {pA.abertura_valvula*100:.1f}%")
assert pA.abertura_valvula > 0.0, "FALHA: válvula não abriu"

# 5) drenar ate ficar abaixo de 80 (sem re-trigger)
dren = 0
while pA.percentual > 79.9 and dren < 3000:
    for _ in agent.app.stream(init, config):
        pass
    dren += 1
pA_ok = agent.app.get_state(config)
print(f"Dreno: PA={pA.percentual:.2f}% após {dren} ciclos | HITL pendente={bool(pA_ok.next)}")
assert pA.percentual <= 79.9, "FALHA: não drenou abaixo de 80"
print("PASS: demo corrigida (sobe -> HITL 1x -> aprova -> drena)")