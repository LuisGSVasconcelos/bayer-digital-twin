"""Persistencia em InfluxDB (Time Series).

O cliente influxdb-client e opcional: sem ele, a persistencia vira um no-op
silencioso, permitindo que o resto do sistema rode (e seja testado) sem a
infraestrutura de series temporais.
"""
import os

try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUX_OK = True
except Exception:  # pragma: no cover
    INFLUX_OK = False

try:
    from dotenv import load_dotenv
    load_dotenv()  # noqa
except Exception:  # pragma: no cover
    pass


class InfluxPersister:
    def __init__(self):
        self.url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
        self.token = os.getenv("INFLUXDB_TOKEN", "")
        self.org = os.getenv("INFLUXDB_ORG", "minha_planta")
        self.bucket = os.getenv("INFLUXDB_BUCKET", "processo_bayer")
        self.client = None
        self.write_api = None
        if INFLUX_OK:
            try:
                self.client = InfluxDBClient(url=self.url, token=self.token or "no-token", org=self.org)
                self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            except Exception as e:  # pragma: no cover
                print(f"⚠️ InfluxDB nao conectado: {e}")

    def persistir_estado(self, timestamp, state: dict, niveis: dict, aberturas: dict,
                         chuva_mm: float, alerta: str):
        if self.write_api is None:
            return  # no-op sem InfluxDB

        points = []
        setpoint = state.get("setpoint", 65.0)

        for nome, nivel in niveis.items():
            tend = state.get(f"tendencia_suavizada_{nome.lower()}", 0.0)
            ema = state.get(f"ema_{nome.lower()}", 0.0)
            soda = state.get(f"soda_perdida_{nome.lower()}", 0.0)

            point = Point("medicao_tanque") \
                .tag("tanque_id", nome) \
                .tag("planta", "Bayer_Sim") \
                .field("nivel_bruto", float(nivel)) \
                .field("nivel_filtrado_ema", ema) \
                .field("tendencia_suavizada", tend) \
                .field("abertura_valvula_mv", aberturas.get(nome, 0.0)) \
                .field("setpoint_sp", setpoint) \
                .field("erro_controle", float(nivel - setpoint)) \
                .field("chuva_mm_h", chuva_mm) \
                .field("alerta_meteorologico", alerta) \
                .field("soda_perdida_kg_s", soda) \
                .field("tc_licor", state.get("tc_saida_decantadores", 0.0)) \
                .time(timestamp, WritePrecision.S)
            points.append(point)

        self.write_api.write(bucket=self.bucket, org=self.org, record=points)
        print(f"💾 {len(points)} registros no InfluxDB")


influx_db = InfluxPersister()