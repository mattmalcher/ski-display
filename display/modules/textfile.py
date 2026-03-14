"""Text file module — reads scenes from messages.txt.

Supports the same format as the original display.py, plus optional
icon/animation prefix tags:

    CLOCK                           → live clock scene
    Normal message                  → static or scroll depending on length
    [ICON:thermometer] -3C          → static/scroll with icon prefix
    [ANIM:print_head:4] Print 67%   → static/scroll with animation prefix

The file is watched for changes every `reload_interval` seconds (default 2).
"""

import os
import re
import time
import logging

from modules.base import DisplayModule

logger = logging.getLogger(__name__)

_TAG = re.compile(r'^\[(ICON|ANIM):([^:\]]+)(?::(\d+))?\]\s*', re.IGNORECASE)

# Keep in sync with display.py constants (imported at runtime to avoid circular dep)
_DEFAULT_SCROLL_SPEED = 36
_DEFAULT_COLS = 32


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

        # Import here to pick up runtime values set by display.py
        try:
            import display as _d
            cols = _d.COLS
            scroll_speed = _d.SCROLL_SPEED
        except Exception:
            cols = _DEFAULT_COLS
            scroll_speed = _DEFAULT_SCROLL_SPEED

        scenes = []
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            scene = self._parse_line(line, cols, scroll_speed)
            if scene:
                scenes.append(scene)

        return scenes or [{'type': 'static', 'text': 'EMPTY', 'duration': 3.0}]

    def _parse_line(self, line: str, cols: int, scroll_speed: int) -> dict | None:
        """Parse one line into a scene dict, honoring [ICON:] / [ANIM:] tags."""
        extra: dict = {}

        # Strip optional tag prefix
        m = _TAG.match(line)
        if m:
            tag_kind = m.group(1).upper()
            tag_name = m.group(2)
            tag_fps  = m.group(3)
            if tag_kind == 'ICON':
                extra['icon'] = tag_name
            else:  # ANIM
                extra['animation'] = tag_name
                extra['anim_fps'] = int(tag_fps) if tag_fps else 4
            line = line[m.end():]

        if not line:
            # Tag with no text — skip
            return None

        if line.upper() == 'CLOCK':
            return {'type': 'clock', 'duration': 5.0, **extra}

        # Determine width — import text_width lazily
        try:
            from display import text_width
            w = text_width(line)
        except Exception:
            w = len(line) * 6  # rough fallback

        if w <= cols:
            return {'type': 'static', 'text': line, 'duration': 3.0, **extra}
        else:
            return {'type': 'scroll', 'text': line + '     ', 'speed': scroll_speed, **extra}
