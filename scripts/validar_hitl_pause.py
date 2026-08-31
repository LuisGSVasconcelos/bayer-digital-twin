"""Valida o fluxo HITL do dashboard: PB>80 -> pausa (loop) -> aprovar -> retoma -> drena.
Espelha a lógica real do dashboard (guard, pause/executando, approve, resume)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import langgraph_agent as agent
import bayer_process_simulator as sim
import adaptive_fuzzy_controller as afc

agent.VERBOSE = False; sim.VERBOSE = False; afc.VERBOSE = False
agent.FORCA_CLIMA = "Forte"
p = agent.planta_bayer
p.gerador.config["spike_sensor"]["probabilidade"] = 0.0
p.t_paralelo_a.volume = p.t_paralelo_a.capacidade * 0.798
p.t_paralelo_b.volume = p.t_paralelo_b.capacidade * 0.796
agent.fuzzy_ctrl_pa.reset(); agent.fuzzy_ctrl_pb.reset()
agent.app = agent.build_app()
cfg = {"configurable": {"thread_id": "dash_hitl"}}
INIT = dict(agent.estado_inicial)

def executar_ciclo():
    snap0 = agent.app.get_state(cfg)
    if snap0 and snap0.next:
        return "⚠️ Aprovação Humana Necessária!"
    snap = None; alerta = "Normal"
    for _ in range(10):
        for _e in agent.app.stream(INIT, cfg):
            pass
        snap = agent.app.get_state(cfg)
        if snap.next:
            alerta = "⚠️ Aprovação Humana Necessária!"
            break
    return alerta

# 1) roda ate PB>80 (HITL), como faria o dashboard com executando=True
executando = True
passos = 0
alerta = "Normal"
while executando and "Humana" not in alerta and passos < 200:
    alerta = executar_ciclo()
    if "Humana" in alerta:
        executando = False  # o dashboard pausa o loop (nova correcao)
        break
    passos += 1

pb = p.t_paralelo_b.percentual
print(f"HITL apos {passos} passos | PB={pb:.2f}%")
assert "Humana" in alerta, "FALHA: HITL nao disparou"
assert pb > 70.0, "FALHA: HITL longe do estado critico"  # 70%+tendencia OU >80

# 2) bloco HITL: botao de aprovar deve estar visivel (snap.next truthy)
snap = agent.app.get_state(cfg)
print("Botao Aprovar visivel (snap.next truthy):", bool(snap.next))
assert snap.next, "FALHA: aprovacao nao pendente"

# 3) user clica Aprovar -> retoma, abre valvula, executando=True
agent.app.update_state(cfg, {}, as_node="aguardar_operador")
for _ in agent.app.stream(None, cfg):
    pass
print(f"Abertura valvula PB apos aprovar: {p.t_paralelo_b.abertura_valvula*100:.1f}%")
assert p.t_paralelo_b.abertura_valvula > 0.0, "FALHA: valvula nao abriu"

# 4) retoma (executando=True): proximo ciclo drena PB abaixo de 80 sem HITL
executando = True
for _ in range(30):
    if "Humana" in executar_ciclo():
        executando = False
        break
print(f"Apos retomar: PB={p.t_paralelo_b.percentual:.2f}% | exec re-pausada={not executando}")
assert p.t_paralelo_b.percentual < 80.0, "FALHA: nao drenou abaixo de 80 apos retomar"
print("PASS: HITL pausa -> aprovar -> retoma -> drena (sem congelar)")