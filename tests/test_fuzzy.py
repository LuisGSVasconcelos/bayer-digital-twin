"""Testes do controlador fuzzy base."""
import pytest

from fuzzy_controller import FuzzyController


@pytest.fixture
def ctrl():
    return FuzzyController()


def test_saida_no_dominio(ctrl):
    """A saida deve estar sempre em [0, 1]."""
    for erro in (-20, -5, 0, 5, 20):
        for deriv in (-5, 0, 5):
            u = ctrl.calcular_abertura(erro, deriv)
            assert 0.0 <= u <= 1.0


def test_zero_saturado(ctrl):
    """Erro maximo negativo com tendencia negativa deve ficar praticamente fechado."""
    u = ctrl.calcular_abertura(-20, -5)
    assert u <= 0.1  # pertinencia em FC (quase fechado); nao exatamente 0 por causa do centroide


def test_maximo_saturado(ctrl):
    """Erro maximo positivo com tendencia positiva abre totalmente (~1.0)."""
    u = ctrl.calcular_abertura(20, 5)
    assert u >= 0.9


def test_saturacao_em_erro_alto_padronizado(ctrl):
    """Regressao: erro acima do antigo dominio (+20) agora abre a valvula.

    Antes o dominio terminava em +20; em nivel 95% vs setpoint 65 (erro 30) a
    pertinencia era nula e a abertura voltava a 0 (falha de controle).
    """
    assert ctrl.calcular_abertura(30, 2.0) >= 0.9
    assert ctrl.calcular_abertura(35, 2.0) >= 0.9


def test_manda_torna_mais_agressivo_que_erro_so(ctrl):
    """Com erro ZE, subir rapido (SR) deve abrir mais do que descer (DN)."""
    u_down = ctrl.calcular_abertura(0, -3)
    u_up = ctrl.calcular_abertura(0, 3)
    assert u_up >= u_down


def test_trapezoid_plato():
    ctrl = FuzzyController()
    assert ctrl._trapezoid(0.5, 0, 0.5, 1, 1.5) == 1.0
    assert ctrl._trapezoid(0.0, 0, 0.5, 1, 1.5) == 0.0 or ctrl._trapezoid(0.0, 0, 0.5, 1, 1.5) == 1.0
    assert ctrl._trapezoid(2.0, 0, 0.5, 1, 1.5) == 0.0