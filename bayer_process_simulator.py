"""Gemeo Digital do Processo Bayer (simplificado).

Topologia: [S1] -> [S2] (serie, digestao) -> divisao -> [PA] e [PB] (paralelo, decantadores).

Inclui balanco de volume, teor caustico (TC), perda de soda (mecanica + quimica)
e um gerador de disturbios operacionais.
"""
import math
import random

VERBOSE = True  # False silencia prints por ciclo (dashboard)


class TanqueIndustrial:
    """Tanque de digestao (fechado, sem influencia de chuva)."""

    def __init__(self, nome: str, capacidade: float, nivel_inicial_pct: float,
                 area_exposta_m2: float = 0, tc_inicial: float = 180.0):
        self.nome = nome
        self.capacidade = capacidade
        self.volume = (nivel_inicial_pct / 100.0) * capacidade
        self.area_exposta = area_exposta_m2

        # Valvula modulante
        self.abertura_valvula = 0.0
        self.vazao_drenagem_maxima = 50.0
        self.vazao_saida_normal = 20.0

        # Quimica (Teor Caustico)
        self.tc = tc_inicial
        self.massa_caustica = self.volume * (self.tc / 1000.0)

    def atualizar_volume(self, entrada_l_s: float, chuva_mm_s: float) -> float:
        agua_chuva = self.area_exposta * chuva_mm_s
        total_entrada = entrada_l_s + agua_chuva

        vazao_drenagem = self.vazao_drenagem_maxima * self.abertura_valvula
        total_saida = self.vazao_saida_normal + vazao_drenagem

        self.volume += (total_entrada - total_saida)

        if self.volume > self.capacidade:
            self.volume = self.capacidade
            if VERBOSE:
                print(f"🚨 TRANSBORDAMENTO no {self.nome}!")
        elif self.volume < 0:
            self.volume = 0
            self.vazao_saida_normal = 0

        return self.vazao_saida_normal

    def atualizar_quimica(self, vazao_entrada: float, tc_entrada: float, vazao_saida: float):
        entrada_massa = (vazao_entrada * tc_entrada) / 1000.0
        saida_massa = (vazao_saida * self.tc) / 1000.0
        self.massa_caustica += (entrada_massa - saida_massa)
        if self.volume > 0:
            self.tc = (self.massa_caustica / self.volume) * 1000.0
        else:
            self.tc = 0.0
        self.tc = round(max(0.0, self.tc), 2)

    @property
    def percentual(self) -> float:
        return round((self.volume / self.capacidade) * 100, 2)


class DecantadorIndustrial(TanqueIndustrial):
    """Decantador aberto (sofre acumulo de chuva na area exposta)."""

    def __init__(self, nome: str, capacidade: float, nivel_inicial_pct: float,
                 area_exposta_m2: float = 0, tc_inicial: float = 170.0):
        super().__init__(nome, capacidade, nivel_inicial_pct, area_exposta_m2, tc_inicial)
        self.teor_solidos_alimentacao = 0.15
        self.umidade_lama = 0.30
        self.soda_perdida_lama = 0.0
        self.vazao_lama = 0.0
        self.vazao_licor_clarificado = 0.0
        self.tc_licor_saida = 0.0
        # Atuador de ENTRADA (makeup/agua de reposicao) - controles bidirecional do nivel.
        # Abre quando o nivel esta ABAIXO do setpoint, injetando volume (corrige a queda
        # que a valvula de drenagem, so-remocao, nao consegue). Agua fresca (dilui TC).
        self.vazao_makeup_maxima = 40.0   # L/s
        self.abertura_makeup = 0.0
        self.vazao_makeup = 0.0

    def atualizar_volume_e_separar(self, vazao_entrada: float, chuva_mm_s: float,
                                   tc_entrada: float, teor_sio2: float = 5.0) -> float:
        agua_chuva = self.area_exposta * chuva_mm_s
        vazao_massica_entrada = vazao_entrada * 1.2
        vazao_solidos_entrada = vazao_massica_entrada * self.teor_solidos_alimentacao

        fator_sio2 = teor_sio2 * 0.008
        perda_quimica_kg_s = vazao_solidos_entrada * fator_sio2

        vazao_solidos_saida = vazao_solidos_entrada
        licor_preso_kg_s = (vazao_solidos_saida * self.umidade_lama) / (1 - self.umidade_lama)
        licor_preso_l_s = licor_preso_kg_s / 1.1

        soda_perdida_mecanica = (licor_preso_l_s * tc_entrada) / 1000.0
        soda_perdida_quimica = perda_quimica_kg_s
        self.soda_perdida_lama = soda_perdida_mecanica + soda_perdida_quimica

        vazao_licor_entrada = vazao_entrada * (1 - self.teor_solidos_alimentacao)
        # Balanço corrigido: o licor clarificado sai apenas o licor SEPARADO (sem a chuva).
        # A chuva ACUMULA no decantador (levanta o nivel); so sai por drenagem/overflow.
        self.vazao_licor_clarificado = max(0.0, vazao_licor_entrada - licor_preso_l_s)
        self.vazao_lama = licor_preso_l_s + (vazao_solidos_saida / 1.5)

        soda_entrada_kg_s = (vazao_licor_entrada * tc_entrada) / 1000.0
        # Conservacao de caustica: sai no licor CLARIFICADO (produto, no TC do tanque)
        # e na lama. Estabiliza o TC (nao sobe/desce sem fim).
        soda_clarificado_kg_s = (self.vazao_licor_clarificado * self.tc) / 1000.0
        self.massa_caustica += (soda_entrada_kg_s - soda_clarificado_kg_s - self.soda_perdida_lama)

        # Correcao: a culvula de drenagem (abertura_valvula) conta no balanco
        # de volume do decantador. Sem isso, a variavel manipulada nao tem
        # efeito no nivel controlado (o loop de controle era inocuo).
        vazao_drenagem = self.vazao_drenagem_maxima * self.abertura_valvula
        vazao_makeup = self.vazao_makeup_maxima * self.abertura_makeup
        self.vazao_makeup = vazao_makeup

        variacao_volume = (vazao_entrada + agua_chuva + vazao_makeup
                           - (self.vazao_licor_clarificado + self.vazao_lama + vazao_drenagem))
        self.volume += variacao_volume
        if self.volume > self.capacidade:
            self.volume = self.capacidade
            if VERBOSE:
                print(f"🚨 TRANSBORDAMENTO CRÍTICO no {self.nome}!")
        elif self.volume < 0:
            self.volume = 0

        if self.volume > 0:
            self.tc = (self.massa_caustica / self.volume) * 1000.0
        else:
            self.tc = 0.0
        self.tc_licor_saida = self.tc
        self.tc = round(max(0.0, self.tc), 2)

        if self.soda_perdida_lama > 0.5 and VERBOSE:
            print(f"🧪 [PERDA DE SODA] {self.nome}: {self.soda_perdida_lama:.2f} kg/s")
        return self.vazao_licor_clarificado


class GeradorDisturbios:
    def __init__(self, ativo=True):
        self.ativo = ativo
        self.tempo_simulacao = 0
        self.config = {
            "variacao_alimentacao": {"amplitude": 8.0, "frequencia": 0.05},
            "desgaste_bomba": {"taxa_decaimento": 0.0005, "max_perda": 30.0},
            "stiction_valvula": {"atraso": 0.3},
            "desbalanceamento_paralelo": {"max_desvio": 0.3},
            "spike_sensor": {"probabilidade": 0.02, "amplitude": 15.0},
            "tc": {
                "setpoint": 180.0,
                "limite_alta": 200.0,
                "limite_critica": 220.0,
                "tc_alimentacao_base": 185.0,
                "variacao_tc_alimentacao": 15.0,
                "vazao_diluicao_maxima": 12.0,
            },
            "silica": {"base": 5.0, "variacao": 8.0, "frequencia": 0.02},
        }
        self.vazao_diluicao_tc = 0.0
        self.alerta_tc_emitido = False
        self.fator_divisao = 0.5

    def aplicar_disturbios(self, planta):
        if not self.ativo:
            return 0.5, 5.0

        self.tempo_simulacao += 1

        # Quais disturbios estao habilitados (padrao: todos). only_chemistry = preset so-quimica.
        hab = dict(self.config.get("disturbios_habilitados", {}))
        if self.config.get("only_chemistry"):
            hab = {"alimentacao": False, "desgaste": False, "stiction": False,
                   "desbalanceamento": False, "tc_diluicao": True, "silica": True}

        def on(nome):
            return hab.get(nome, True)

        if on("alimentacao"):
            self._disturbio_alimentacao(planta)
        if on("desgaste"):
            self._disturbio_desgaste_bomba(planta)
        if on("stiction"):
            self._disturbio_stiction(planta)
        fator = 0.5
        if on("desbalanceamento"):
            fator = self._disturbio_desbalanceamento()
        if on("tc_diluicao"):
            self._disturbio_diluicao_tc(planta)
        sio2 = 5.0
        if on("silica"):
            sio2 = self._disturbio_silica()
        return fator, sio2

    def _disturbio_alimentacao(self, planta):
        amp = self.config["variacao_alimentacao"]["amplitude"]
        freq = self.config["variacao_alimentacao"]["frequencia"]
        ruido = self.config["variacao_alimentacao"].get("ruido", 2.0)  # ruido base (± L/s)
        osc = amp * math.sin(freq * self.tempo_simulacao) + random.uniform(-ruido, ruido)
        planta.disturbio_alimentacao_adicional = osc

    def _disturbio_desgaste_bomba(self, planta):
        taxa = self.config["desgaste_bomba"]["taxa_decaimento"]
        max_perda = self.config["desgaste_bomba"]["max_perda"]
        perda = min(max_perda, self.tempo_simulacao * taxa)
        fator = 1.0 - (perda / 100.0)
        for t in [planta.t_serie1, planta.t_serie2, planta.t_paralelo_a, planta.t_paralelo_b]:
            t.vazao_saida_normal = 20.0 * fator

    def _disturbio_stiction(self, planta):
        for tanque in [planta.t_paralelo_a, planta.t_paralelo_b]:
            if not hasattr(tanque, 'abertura_real'):
                tanque.abertura_real = tanque.abertura_valvula
            diff = tanque.abertura_valvula - tanque.abertura_real
            if abs(diff) < 0.05:
                pass
            else:
                tanque.abertura_real += diff * 0.7
            tanque.abertura_valvula = tanque.abertura_real

    def _disturbio_desbalanceamento(self):
        passo = random.uniform(-0.02, 0.02)
        self.fator_divisao += passo
        self.fator_divisao = max(0.2, min(0.8, self.fator_divisao))
        return self.fator_divisao

    def _disturbio_diluicao_tc(self, planta):
        config = self.config["tc"]
        variacao = random.uniform(-config["variacao_tc_alimentacao"], config["variacao_tc_alimentacao"])
        tc_alim = config["tc_alimentacao_base"] + variacao

        vazao_s1 = planta.disturbio_alimentacao_adicional + 22.0
        vazao_s1_saida = planta.t_serie1.vazao_saida_normal
        planta.t_serie1.atualizar_quimica(vazao_s1, tc_alim, vazao_s1_saida)

        tc_s1 = planta.t_serie1.tc
        vazao_s2_entrada = vazao_s1_saida + self.vazao_diluicao_tc
        vazao_s2_saida = planta.t_serie2.vazao_saida_normal
        planta.t_serie2.atualizar_quimica(vazao_s2_entrada, tc_s1, vazao_s2_saida)

        tc_s2 = planta.t_serie2.tc
        if config["limite_alta"] < tc_s2 < config["limite_critica"]:
            erro_tc = tc_s2 - config["setpoint"]
            self.vazao_diluicao_tc = min(config["vazao_diluicao_maxima"], erro_tc * 0.12) + random.uniform(-0.2, 0.5)
            self.vazao_diluicao_tc = round(max(0.0, self.vazao_diluicao_tc), 2)
            if not self.alerta_tc_emitido and VERBOSE:
                print(f"🧪 [TC - ALERTA] TC elevado! {tc_s2:.1f} g/L -> Diluição: {self.vazao_diluicao_tc:.1f} L/s")
                self.alerta_tc_emitido = True
        elif tc_s2 > config["limite_critica"]:
            self.vazao_diluicao_tc = config["vazao_diluicao_maxima"]
            if VERBOSE:
                print(f"🧪🚨 [TC - EMERGÊNCIA] TC CRÍTICO! {tc_s2:.1f} g/L")
        else:
            self.vazao_diluicao_tc = max(0.0, self.vazao_diluicao_tc - 0.3)
            self.alerta_tc_emitido = False
        planta.vazao_diluicao_tc = self.vazao_diluicao_tc

    def _disturbio_silica(self):
        config = self.config["silica"]
        variacao = config["variacao"] * math.sin(config["frequencia"] * self.tempo_simulacao)
        ruido = random.uniform(-1.0, 1.0)
        return round(max(0.5, min(15.0, config["base"] + variacao + ruido)), 2)

    def aplicar_spike_sensor(self, nivel_atual):
        if random.random() < self.config["spike_sensor"]["probabilidade"]:
            amp = self.config["spike_sensor"]["amplitude"]
            spike = random.uniform(amp * 0.5, amp)
            if VERBOSE:
                print(f"⚡ [SPIKE] Sensor +{spike:.1f}%")
            return nivel_atual + spike
        return nivel_atual


class PlantaBayerSimulada:
    def __init__(self, ativar_disturbios=True):
        self.t_serie1 = TanqueIndustrial("Reator S1", 50000, 60.0, 0, 180.0)
        self.t_serie2 = TanqueIndustrial("Reator S2", 50000, 65.0, 0, 185.0)
        self.t_paralelo_a = DecantadorIndustrial("Decantador PA", 100000, 75.0, 150, 170.0)
        self.t_paralelo_b = DecantadorIndustrial("Decantador PB", 100000, 78.0, 150, 172.0)

        self.gerador = GeradorDisturbios(ativo=ativar_disturbios)
        self.disturbio_alimentacao_adicional = 0.0
        self.vazao_diluicao_tc = 0.0

    def rodar_ciclo_fisica(self, intensidade_chuva):
        fator_divisao, teor_sio2 = self.gerador.aplicar_disturbios(self)

        if isinstance(intensidade_chuva, (int, float)):
            chuva_mm_s = float(intensidade_chuva)   # chuva CONTINUA (manual)
        else:
            conversoes = {"Nenhuma": 0.0, "Moderada": 0.05, "Forte": 0.25}
            chuva_mm_s = conversoes.get(str(intensidade_chuva), 0.0)

        carga_base = 22.0
        carga_inicial = max(5.0, carga_base + self.disturbio_alimentacao_adicional)

        saida_s1 = self.t_serie1.atualizar_volume(carga_inicial, 0)
        entrada_s2 = saida_s1 + self.vazao_diluicao_tc
        saida_s2 = self.t_serie2.atualizar_volume(entrada_s2, 0)

        tc_s2 = self.t_serie2.tc if self.t_serie2.tc > 0 else 180.0

        carga_pa = saida_s2 * fator_divisao
        carga_pb = saida_s2 * (1 - fator_divisao)

        self.t_paralelo_a.atualizar_volume_e_separar(carga_pa, chuva_mm_s, tc_s2, teor_sio2)
        self.t_paralelo_b.atualizar_volume_e_separar(carga_pb, chuva_mm_s, tc_s2, teor_sio2)

        self.disturbio_alimentacao_adicional = 0.0

    def obter_status_sensores(self) -> dict:
        return {
            "S1": self.t_serie1.percentual,
            "S2": self.t_serie2.percentual,
            "PA": self.t_paralelo_a.percentual,
            "PB": self.t_paralelo_b.percentual,
        }