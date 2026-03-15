"""Home Assistant sensor module — fetches entity states via the HA REST API.

Add to config.json:
    {
        "name": "home_assistant",
        "enabled": true,
        "ha_url": "http://homeassistant.local:8123",
        "token": "your-long-lived-access-token",
        "entity_ids": ["sensor.living_room_temperature", "sensor.outdoor_humidity"],
        "fetch_interval": 60,
        "ttl": 120
    }

Options:
    ha_url         — Base URL of your Home Assistant instance (required).
    token          — Long-lived access token from HA profile page (required).
    entity_ids     — List of entity IDs to display (required).
    fetch_interval — Seconds between fetches (default 60).
    ttl            — Seconds before a scene is considered stale (default: 2×fetch_interval).

Scenes use the entity's friendly_name and unit_of_measurement from HA attributes.
Short readings display as static; long text scrolls automatically.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request

from modules.base import DisplayModule

logger = logging.getLogger(__name__)

# Display is 32px wide. 5px glyph + 1px gap per character.
_CHAR_WIDTH = 6
# Thermometer icon (8px) plus 1px gap.
_ICON_WIDTH = 9
_DISPLAY_WIDTH = 32


class Module(DisplayModule):
    def start(self):
        self._ha_url = self.config['ha_url'].rstrip('/')
        self._token = self.config['token']
        self._entity_ids = self.config.get('entity_ids', [])
        self._fetch_interval = float(self.config.get('fetch_interval', 60))
        self._ttl = float(self.config.get('ttl', self._fetch_interval * 2))
        # entity_id -> {'label': str, 'state': str, 'unit': str}
        self._cache: dict[str, dict] = {}
        self._stop = threading.Event()

        t = threading.Thread(target=self._fetch_loop, daemon=True)
        t.start()

    def stop(self):
        self._stop.set()

    def get_scenes(self) -> list:
        scenes = []
        for entity_id in self._entity_ids:
            data = self._cache.get(entity_id)
            if data is None:
                continue
            label = data['label']
            state = data['state']
            unit = data['unit']
            text = f'{label}: {state}{unit}'
            pixel_width = _ICON_WIDTH + len(text) * _CHAR_WIDTH
            if pixel_width > _DISPLAY_WIDTH:
                scenes.append({
                    'type': 'scroll',
                    'text': text,
                    'icon': 'thermometer',
                    'speed': 30,
                    'ttl': self._ttl,
                })
            else:
                scenes.append({
                    'type': 'static',
                    'text': text,
                    'icon': 'thermometer',
                    'duration': 4.0,
                    'ttl': self._ttl,
                })
        return scenes

    def _fetch_loop(self):
        while not self._stop.is_set():
            try:
                self._fetch_all()
            except Exception as e:
                logger.error('home_assistant: fetch error: %s', e)
            self._stop.wait(self._fetch_interval)

    def _fetch_all(self):
        for entity_id in self._entity_ids:
            try:
                url = f'{self._ha_url}/api/states/{entity_id}'
                req = urllib.request.Request(
                    url,
                    headers={'Authorization': f'Bearer {self._token}'},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    payload = json.loads(resp.read())
                attrs = payload.get('attributes', {})
                state = payload.get('state', '')
                unit = attrs.get('unit_of_measurement', '')
                label = attrs.get('friendly_name') or entity_id
                self._cache[entity_id] = {
                    'label': label,
                    'state': state,
                    'unit': unit,
                }
            except urllib.error.URLError as e:
                logger.warning('home_assistant: could not reach %s: %s', entity_id, e)
            except Exception as e:
                logger.warning('home_assistant: error fetching %s: %s', entity_id, e)
