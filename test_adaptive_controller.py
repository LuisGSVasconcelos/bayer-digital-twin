"""Benchmark reproduzivel: Fuzzy Padrao vs Fuzzy Adaptativo.

Correcao A2 do roteiro original: em vez de 1 rodada sem seed (nao-reproduzivel),
roda NUM_RUNS simulacoes com seeds fixas e reporta media +/- desvio padrao.

Uso:  python test_adaptive_controller.py
"""
import random
import statistics

from fuzzy_controller import FuzzyController
from adaptive_fuzzy_controller import AdaptiveFuzzyController
from bayer_process_simulator import PlantaBayerSimulada

DURACAO = 100
SETPOINT = 65.0
CHUVA = "Forte"
NUM_RUNS = 10
SEED_BASE = 42


def simular_um_run(controlador, seed):
    """Roda uma simulacao deterministica do controlador sobre a planta."""
    random.seed(seed)
    planta = PlantaBayerSimulada(ativar_disturbios=True)
    erro_quad = 0.0
    hist_nivel = []
    for _ in range(DURACAO):
        planta.rodar_ciclo_fisica(CHUVA)
        nivel = planta.t_paralelo_a.percentual
        deriv = nivel - (hist_nivel[-1] if hist_nivel else nivel)
        hist_nivel.append(nivel)

        erro = nivel - SETPOINT
        abertura = controlador.calcular_abertura(erro, deriv)
        planta.t_paralelo_a.abertura_valvula = abertura

        erro_quad += erro * erro
    return (erro_quad / DURACAO) ** 0.5


def main():
    rmses_pad, rmses_adapt = [], []
    for run in range(NUM_RUNS):
        seed = SEED_BASE + run
        rmses_pad.append(simular_um_run(FuzzyController(), seed))
        rmses_adapt.append(simular_um_run(AdaptiveFuzzyController(0.002, 0.85), seed))

    mp, dp = statistics.mean(rmses_pad), statistics.pstdev(rmses_pad)
    ma, da = statistics.mean(rmses_adapt), statistics.pstdev(rmses_adapt)
    melhoria = (1 - ma / mp) * 100 if mp else 0.0

    print(f"\nResultado ({NUM_RUNS} runs reproduciveis, seeds {SEED_BASE}..{SEED_BASE + NUM_RUNS - 1}):")
    print(f"  Fuzzy Padrão:     RMSE {mp:6.2f}% ± {dp:.2f}")
    print(f"  Fuzzy Adaptativo: RMSE {ma:6.2f}% ± {da:.2f}")
    print(f"  Melhoria: {melhoria:+5.1f}%")
    print()
    ok = ma < mp
    print("✅ Adaptativo supera Padrão (média)" if ok else "⚠️ Adaptativo NÃO superou Padrão nesta média.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())