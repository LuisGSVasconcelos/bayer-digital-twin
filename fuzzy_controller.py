"""Controlador Fuzzy base (Mamdani + defuzzificacao por centroide).

Entradas: erro (Nivel - Setpoint) e derivada (tendencia).
Saida: abertura da valvula normalizada em [0, 1].
"""
import math


class FuzzyController:
    def __init__(self):
        self.sets_erro = {
            'NG': (-30, -30, -18, -6),
            'NP': (-15, -5, -5, 0),
            'ZE': (-2, 0, 0, 2),
            'PP': (0, 5, 5, 15),
            'PG': (6, 18, 35, 40),
        }
        self.sets_derivada = {
            'DN': (-5, -5, -3, -1),
            'DL': (-3, -1, -1, 0),
            'ZE': (-0.5, 0, 0, 0.5),
            'SL': (0, 1, 1, 3),
            'SR': (1, 3, 5, 5),
        }
        self.sets_saida = {
            'FC': (0, 0, 5, 15),
            'PA': (10, 20, 30, 40),
            'MA': (35, 45, 55, 65),
            'AA': (60, 70, 80, 90),
            'TA': (85, 95, 100, 100),
        }
        self.regras = {
            'NG': {'DN': 'FC', 'DL': 'FC', 'ZE': 'PA', 'SL': 'PA', 'SR': 'MA'},
            'NP': {'DN': 'FC', 'DL': 'PA', 'ZE': 'MA', 'SL': 'MA', 'SR': 'AA'},
            'ZE': {'DN': 'PA', 'DL': 'MA', 'ZE': 'MA', 'SL': 'AA', 'SR': 'TA'},
            'PP': {'DN': 'MA', 'DL': 'AA', 'ZE': 'AA', 'SL': 'TA', 'SR': 'TA'},
            'PG': {'DN': 'AA', 'DL': 'TA', 'ZE': 'TA', 'SL': 'TA', 'SR': 'TA'},
        }

    def _trapezoid(self, x, a, b, c, d):
        """Funcao de pertinencia trapezoidal (trata bordas degeneradas a==b / c==d)."""
        if x < a or x > d:
            return 0.0
        # Rampa de subida [a, b): 0 -> 1  (desvio: se a==b, sobe direto)
        if a <= x < b:
            return 1.0 if b == a else (x - a) / (b - a)
        # Topo [b, c]
        if b <= x <= c:
            return 1.0
        # Rampa de descida (c, d]: 1 -> 0  (desvio: se c==d, desce direto)
        if c < x <= d:
            return 1.0 if d == c else (d - x) / (d - c)
        return 0.0

    def _fuzzifica(self, valor, conjuntos):
        return {nome: self._trapezoid(valor, *params) for nome, params in conjuntos.items()}

    def _centroide(self, regras_ativadas):
        """Centro de gravidade das saidas fuzzy ponderadas pelo grau de ativacao."""
        num = 0.0
        den = 0.0
        for nome, grau in regras_ativadas:
            a, b, c, d = self.sets_saida[nome]
            centro = (a + b + c + d) / 4.0
            area = ((d - a) + (c - b)) / 2.0
            peso = grau * area
            num += centro * peso
            den += peso
        return num / den if den != 0 else 0.0

    def calcular_abertura(self, erro: float, derivada: float) -> float:
        """Retorna abertura da valvula normalizada em [0, 1]."""
        erro_fuzzy = self._fuzzifica(erro, self.sets_erro)
        deriv_fuzzy = self._fuzzifica(derivada, self.sets_derivada)

        regras_ativadas = []
        for ce, ge in erro_fuzzy.items():
            if ge == 0:
                continue
            for cd, gd in deriv_fuzzy.items():
                if gd == 0:
                    continue
                saida = self.regras.get(ce, {}).get(cd)
                if saida:
                    regras_ativadas.append((saida, min(ge, gd)))

        abertura = self._centroide(regras_ativadas)
        return round(max(0.0, min(100.0, abertura)) / 100.0, 3)