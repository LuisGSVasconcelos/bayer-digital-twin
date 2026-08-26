"""Integracao com a API OpenWeatherMap (atual + previsao).

Dependencias (requests, python-dotenv) sao opcionais: se nao estiverem
instaladas ou nao houver chave, get_rain_intensity degrada de forma segura.
"""
import os

try:
    import requests
    REQUESTS_OK = True
except Exception:  # pragma: no cover
    REQUESTS_OK = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # pragma: no cover
    pass

OPENWEATHER_BASE_CURRENT = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_BASE_FORECAST = "https://api.openweathermap.org/data/2.5/forecast"


class WeatherService:
    def __init__(self, api_key: str, lat: float, lon: float,
                 units: str = "metric", lang: str = "pt_br"):
        self.api_key = api_key
        self.lat = lat
        self.lon = lon
        self.units = units
        self.lang = lang

    def _get_current(self):
        if not REQUESTS_OK or not self.api_key:
            return None
        params = {"lat": self.lat, "lon": self.lon, "appid": self.api_key,
                  "units": self.units, "lang": self.lang}
        try:
            r = requests.get(OPENWEATHER_BASE_CURRENT, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def _get_forecast(self, hours_ahead=6):
        if not REQUESTS_OK or not self.api_key:
            return None
        cnt = min(8, max(1, hours_ahead // 3 + 1))
        params = {"lat": self.lat, "lon": self.lon, "appid": self.api_key,
                  "units": self.units, "lang": self.lang, "cnt": cnt}
        try:
            r = requests.get(OPENWEATHER_BASE_FORECAST, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def get_rain_intensity(self):
        """Retorna (mm/h, descricao, alerta). Falha/indisponibilidade => mm/h 0."""
        current = self._get_current()
        if not current:
            return 0.0, "indisponível", "⚠️ Falha na consulta"

        rain_data = current.get("rain", {})
        intensidade = rain_data.get("1h", 0.0)
        desc = current.get("weather", [{}])[0].get("description", "sem dados")
        alerta = self._gerar_alerta()
        return round(intensidade, 2), desc, alerta

    def _gerar_alerta(self):
        forecast = self._get_forecast(6)
        if not forecast:
            return "⚠️ Previsão indisponível"

        alertas = []
        for item in forecast.get("list", []):
            rain_3h = item.get("rain", {}).get("3h", 0.0)
            mm_h = rain_3h / 3.0
            if mm_h > 2.0:
                dt = item.get("dt_txt", "desconhecido")
                alertas.append(f"  - {dt}: {mm_h:.1f} mm/h")
        if alertas:
            return "🚨 ALERTA: Chuva forte prevista!\n" + "\n".join(alertas)
        return "✅ Sem chuva significativa prevista."


# Instancia global (usa .env). Sem chave, degrada para "sem chuva".
weather_service = WeatherService(
    api_key=os.getenv("OPENWEATHER_API_KEY"),
    lat=float(os.getenv("OPENWEATHER_LAT", 0)),
    lon=float(os.getenv("OPENWEATHER_LON", 0)),
    units=os.getenv("OPENWEATHER_UNITS", "metric"),
    lang=os.getenv("OPENWEATHER_LANG", "pt_br"),
)