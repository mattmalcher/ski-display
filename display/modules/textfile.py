"""Text file module — reads scenes from messages.txt.

Supports the same format as the messages module, plus optional
icon/animation prefix tags:

    Normal message                  → static or scroll depending on length
    [ICON:thermometer] -3C          → static/scroll with icon prefix
    [ANIM:print_head:4] Print 67%   → static/scroll with animation prefix

The file is watched for changes every `reload_interval` seconds (default 2).
"""

import os
import time
import logging

from modules.base import DisplayModule
from modules.messages import parse_message, _get_display_constants

logger = logging.getLogger(__name__)


class Module(DisplayModule):
    def __init__(self, config: dict):
        super().__init__(config)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._file = os.path.join(base, config.get('file', 'messages.txt'))
        self._reload_interval = float(config.get('reload_interval', 2.0))
        self._mtime = 0.0
        self._scenes: list = []
        self._last_check = 0.0

    def get_scenes(self) -> list:
        try:
            now = time.monotonic()
            if now - self._last_check >= self._reload_interval:
                self._last_check = now
                mt = self._disk_mtime()
                if mt != self._mtime:
                    self._mtime = mt
                    self._scenes = self._parse()
            return list(self._scenes)
        except Exception:
            logger.exception('textfile module error')
            return []

    # ── Internal ──────────────────────────────────────────────────────────────

    def _disk_mtime(self) -> float:
        try:
            return os.path.getmtime(self._file)
        except OSError:
            return 0.0

    def _parse(self) -> list:
        try:
            lines = open(self._file).read().splitlines()
        except OSError:
            logger.warning('textfile: cannot read %s', self._file)
            return [{'type': 'static', 'text': 'NO MSG', 'duration': 3.0}]

        cols, scroll_speed = _get_display_constants()

        scenes = []
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            scene = parse_message(line, cols, scroll_speed)
            if scene:
                scenes.append(scene)

        return scenes or [{'type': 'static', 'text': 'EMPTY', 'duration': 3.0}]
