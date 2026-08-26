"""Testes do Gemeo Digital do Processo Bayer."""
import random

from bayer_process_simulator import PlantaBayerSimulada
from bayer_process_simulator import GeradorDisturbios


def test_estado_inicial():
    p = PlantaBayerSimulada(ativar_disturbios=False)
    sensores = p.obter_status_sensores()
    assert set(sensores) == {"S1", "S2", "PA", "PB"}
    assert sensores["PA"] == 75.0
    assert sensores["PB"] == 78.0
    assert 0 <= p.t_paralelo_a.percentual <= 100


def test_sem_chuva_e_deterministico():
    """Sem disturbios e sem chuva, o nivel nao explode em poucos ciclos."""
    p = PlantaBayerSimulada(ativar_disturbios=False)
    for _ in range(20):
        p.rodar_ciclo_fisica("Nenhuma")
    pct = p.obter_status_sensores()
    for tid in ("PA", "PB", "S1", "S2"):
        assert 0 <= pct[tid] <= 100


def test_transbordamento_cap():
    """Nivel nunca ultrapassa a capacidade."""
    p = PlantaBayerSimulada(ativar_disturbios=False)
    p.t_paralelo_b.volume = p.t_paralelo_b.capacidade  # cheio
    p.t_paralelo_b.abertura_valvula = 0.0
    p.rodar_ciclo_fisica("Forte")
    assert p.t_paralelo_b.volume <= p.t_paralelo_b.capacidade


def test_valvula_aberta_reduz_nivel():
    """Com a valvula de drenagem aberta, um decantador sob chuva tende a nao subir tanto."""
    random.seed(7)
    p_a = PlantaBayerSimulada(ativar_disturbios=False)
    p_b = PlantaBayerSimulada(ativar_disturbios=False)
    p_b.t_paralelo_a.abertura_valvula = 1.0  # totalmente aberta

    for _ in range(30):
        p_a.rodar_ciclo_fisica("Moderada")
        p_b.rodar_ciclo_fisica("Moderada")

    assert p_b.t_paralelo_a.percentual < p_a.t_paralelo_a.percentual


def test_perda_de_soda_positiva():
    p = PlantaBayerSimulada(ativar_disturbios=False)
    p.rodar_ciclo_fisica("Forte")
    assert p.t_paralelo_a.soda_perdida_lama >= 0.0


def test_spike_dentro_da_amplitude():
    g = GeradorDisturbios(ativo=False)
    amostras = []
    # forcamos sempre spike usando probabilidade alta
    g.config["spike_sensor"]["probabilidade"] = 1.0
    random.seed(1)
    for _ in range(50):
        amostras.append(g.aplicar_spike_sensor(50.0))
    maior = max(amostras) - 50.0
    assert g.config["spike_sensor"]["amplitude"] * 1.0 >= maior >= g.config["spike_sensor"]["amplitude"] * 0.5