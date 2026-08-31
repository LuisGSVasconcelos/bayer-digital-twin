"""Verifica que a chuva acumula e sobe o nivel (balanço corrigido)."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bayer_process_simulator import PlantaBayerSimulada

random.seed(1)
n = PlantaBayerSimulada(ativar_disturbios=False)
f = PlantaBayerSimulada(ativar_disturbios=False)
for _ in range(40):
    n.rodar_ciclo_fisica("Nenhuma")
    f.rodar_ciclo_fisica("Forte")
pa_n = n.t_paralelo_a.percentual
pa_f = f.t_paralelo_a.percentual
print(f"PA sem chuva : {pa_n:.2f}%  (variou {pa_n-75.0:+.2f} pt)")
print(f"PA chuva Forte: {pa_f:.2f}%  (variou {pa_f-75.0:+.2f} pt)")
assert pa_f > pa_n, "chuva deveria subir o nivel"
assert pa_f - 75.0 > 0.5, "chuva deveria subir o nivel de forma significativa"
print("OK: chuva acumula e sobe o nivel")