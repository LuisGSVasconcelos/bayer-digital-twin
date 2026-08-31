"""Controlador Fuzzy com ganho adaptativo (gradiente descendente + momentum)."""
from fuzzy_controller import FuzzyController

VERBOSE = True  # False silencia os prints por ciclo (dashboard)


class AdaptiveFuzzyController(FuzzyController):
    def __init__(self, taxa_aprendizado: float = 0.001, momentum: float = 0.9,
                 ganho_min: float = 0.3, ganho_max: float = 2.5):
        super().__init__()
        self.eta = taxa_aprendizado
        self.mom = momentum
        self.ganho = 1.0
        self.ultima_variacao = 0.0
        self.ganho_min = ganho_min
        self.ganho_max = ganho_max
        self.ciclo = 0
        self.historico_ganho = []
        self.historico_erro = []

    def calcular_abertura(self, erro: float, derivada: float) -> float:
        self.ciclo += 1
        u_fuzzy = super().calcular_abertura(erro, derivada)

        # Acao real escalada pelo ganho adaptativo
        u_real = self.ganho * u_fuzzy
        u_real = max(0.0, min(1.0, u_real))

        # Atualizacao do ganho (gradiente descendente com momentum)
        gradiente = erro * u_fuzzy
        variacao = (self.eta * gradiente) + (self.mom * self.ultima_variacao)
        self.ganho = max(self.ganho_min, min(self.ganho_max, self.ganho + variacao))
        self.ultima_variacao = variacao

        self.historico_ganho.append(self.ganho)
        self.historico_erro.append(erro)

        if abs(variacao) > 0.01 and VERBOSE:
            print(f"🔄 [ADAPT] Ciclo {self.ciclo}: Erro={erro:.2f}%, u_fuzzy={u_fuzzy:.3f}, Ganho={self.ganho:.3f}")

        return round(u_real, 3)

    def reset(self):
        self.ganho = 1.0
        self.ultima_variacao = 0.0
        self.historico_ganho = []
        self.historico_erro = []
        self.ciclo = 0

    def get_metricas(self):
        if not self.historico_erro:
            return {"erro_medio": 0, "ganho_final": 1.0}
        return {
            "erro_medio_abs": sum(abs(e) for e in self.historico_erro) / len(self.historico_erro),
            "ganho_final": self.ganho,
            "ganho_maximo": max(self.historico_ganho) if self.historico_ganho else 1.0,
            "ganho_minimo": min(self.historico_ganho) if self.historico_ganho else 1.0,
            "ciclos": self.ciclo,
        }