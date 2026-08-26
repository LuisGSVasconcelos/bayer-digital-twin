"""Testes do controlador fuzzy adaptativo."""
from adaptive_fuzzy_controller import AdaptiveFuzzyController


def test_ganho_fica_dentro_dos_limites():
    ctrl = AdaptiveFuzzyController(taxa_aprendizado=0.05, momentum=0.9,
                                   ganho_min=0.3, ganho_max=2.5)
    for _ in range(500):
        ctrl.calcular_abertura(12.0, 2.0)
        assert ctrl.ganho_min - 1e-9 <= ctrl.ganho <= ctrl.ganho_max + 1e-9


def test_reset():
    ctrl = AdaptiveFuzzyController()
    ctrl.calcular_abertura(10.0, 2.0)
    assert ctrl.ciclo > 0
    ctrl.reset()
    assert ctrl.ciclo == 0
    assert ctrl.ganho == 1.0
    assert ctrl.historico_erro == []
    assert ctrl.get_metricas()["ganho_final"] == 1.0


def test_saida_dominio():
    ctrl = AdaptiveFuzzyController()
    u = ctrl.calcular_abertura(8.0, 1.5)
    assert 0.0 <= u <= 1.0


def test_metricas():
    ctrl = AdaptiveFuzzyController()
    for i in range(20):
        ctrl.calcular_abertura(float(i), 1.0)
    m = ctrl.get_metricas()
    assert m["ciclos"] == 20
    assert m["erro_medio_abs"] > 0
    assert m["ganho_maximo"] >= m["ganho_final"]