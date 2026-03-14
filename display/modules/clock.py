"""Clock module — provides a live clock scene.

Add to config.json:
    {"name": "clock", "enabled": true, "duration": 5.0}

The actual rendering of the clock (HH:MM with blinking colon) is handled
by display.py — this module simply injects the clock scene into the rotation.
"""

from modules.base import DisplayModule


class Module(DisplayModule):
    def get_scenes(self) -> list:
        return [{'type': 'clock', 'duration': float(self.config.get('duration', 5.0))}]
