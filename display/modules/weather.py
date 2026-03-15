"""Weather module — fetches current conditions for a UK location via Open-Meteo.

Uses Open-Meteo (https://open-meteo.com/) — free, no API key required.
Location is resolved by name using the Open-Meteo Geocoding API.

Add to config.json:
    {
        "name": "weather",
        "enabled": true,
        "location": "Aviemore",
        "fetch_interval": 600
    }

No extra dependencies required (uses stdlib urllib).
"""

import json
import logging
import threading
import urllib.parse
import urllib.request

from modules.base import DisplayModule

logger = logging.getLogger(__name__)

# WMO Weather interpretation codes → short description
_WMO_CODES = {
    0: 'Clear',
    1: 'Mostly clear',
    2: 'Partly cloudy',
    3: 'Overcast',
    45: 'Fog',
    48: 'Icy fog',
    51: 'Light drizzle',
    53: 'Drizzle',
    55: 'Heavy drizzle',
    61: 'Light rain',
    63: 'Rain',
    65: 'Heavy rain',
    71: 'Light snow',
    73: 'Snow',
    75: 'Heavy snow',
    77: 'Snow grains',
    80: 'Showers',
    81: 'Showers',
    82: 'Heavy showers',
    85: 'Snow showers',
    86: 'Heavy snow showers',
    95: 'Thunderstorm',
    96: 'Thunderstorm',
    99: 'Thunderstorm',
}

_GEOCODING_URL = (
    'https://geocoding-api.open-meteo.com/v1/search'
    '?name={name}&count=1&language=en&format=json'
)
_FORECAST_URL = (
    'https://api.open-meteo.com/v1/forecast'
    '?latitude={lat}&longitude={lon}'
    '&current=temperature_2m,weathercode,windspeed_10m'
    '&timezone=Europe%2FLondon'
    '&wind_speed_unit=mph'
)


def _http_get(url: str, timeout: int = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


class Module(DisplayModule):
    def start(self):
        self._location_name = self.config.get('location', 'London')
        self._fetch_interval = float(self.config.get('fetch_interval', 600))
        self._cache = None  # {'temp': float, 'condition': str, 'wind_mph': float}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._lat = None
        self._lon = None
        self._resolved_name = None

        t = threading.Thread(target=self._fetch_loop, daemon=True)
        t.start()

    def stop(self):
        self._stop.set()

    def get_scenes(self) -> list:
        with self._lock:
            data = self._cache

        if data is None:
            return []

        try:
            temp = data['temp']
            condition = data['condition']
            wind_mph = data['wind_mph']
            name = data['name']
            text = f'{name} {temp:.0f}C {condition} {wind_mph:.0f}mph'
            return [{
                'type': 'scroll',
                'text': text,
                'icon': 'thermometer',
                'speed': 30,
                'ttl': self._fetch_interval * 2,
            }]
        except Exception:
            logger.exception('weather: error building scene')
            return []

    # ------------------------------------------------------------------
    # Background helpers
    # ------------------------------------------------------------------

    def _fetch_loop(self):
        while not self._stop.is_set():
            try:
                if self._lat is None:
                    self._resolve_location()
                if self._lat is not None:
                    self._fetch_weather()
            except Exception:
                logger.exception('weather: fetch error')
            self._stop.wait(self._fetch_interval)

    def _resolve_location(self):
        url = _GEOCODING_URL.format(name=urllib.parse.quote(self._location_name))
        try:
            data = _http_get(url)
        except Exception:
            logger.exception('weather: geocoding failed for %r', self._location_name)
            return

        results = data.get('results')
        if not results:
            logger.error('weather: no geocoding results for %r', self._location_name)
            return

        place = results[0]
        self._lat = place['latitude']
        self._lon = place['longitude']
        self._resolved_name = place.get('name', self._location_name)
        logger.info(
            'weather: resolved %r → %s (%.4f, %.4f)',
            self._location_name, self._resolved_name, self._lat, self._lon,
        )

    def _fetch_weather(self):
        url = _FORECAST_URL.format(lat=self._lat, lon=self._lon)
        data = _http_get(url)

        current = data['current']
        temp = current['temperature_2m']
        code = current['weathercode']
        wind_mph = current['windspeed_10m']
        condition = _WMO_CODES.get(code, f'Code {code}')

        with self._lock:
            self._cache = {
                'temp': temp,
                'condition': condition,
                'wind_mph': wind_mph,
                'name': self._resolved_name or self._location_name,
            }
        logger.info('weather: %s %.1fC %s %.0fmph', self._resolved_name, temp, condition, wind_mph)
