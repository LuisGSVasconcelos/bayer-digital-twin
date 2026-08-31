"""Diagnóstico: mede a evolução do nível e a atividade dos distúrbios."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bayer_process_simulator import PlantaBayerSimulada

def rodar(ativar, chuva, ciclos=600, passo=100):
    p = PlantaBayerSimulada(ativar_disturbios=ativar)
    print(f"\n=== disturbios={ativar} | chuva={chuva} | {ciclos} ciclos ===")
    for c in range(1, ciclos + 1):
        p.rodar_ciclo_fisica(chuva)
        if c in (1, 10) or c % passo == 0 or c == ciclos:
            s = p.obter_status_sensores()
            print(f" ciclo {c:4d}  S1={s['S1']:6.2f}%  S2={s['S2']:6.2f}%  "
                  f"PA={s['PA']:6.3f}%  PB={s['PB']:6.3f}%  "
                  f"vqS1={p.t_serie1.vazao_saida_normal:5.2f}  fator={p.gerador.fator_divisao:.3f}  "
                  f"tcS2={p.t_serie2.tc:6.1f}  sio2={p.gerador.config['silica']['base'] + 0.0:.1f}")

print("Sem chuva, com disturbios:")
rodar(True, "Nenhuma")
print("\nSem chuva, SEM disturbios:")
rodar(False, "Nenhuma")
print("\nCom chuva Forte e disturbios (cenário de risco):")
rodar(True, "Forte", ciclos=300, passo=50)