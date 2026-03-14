"""Messages module — provides scenes from a static list of messages in config.json.

Supports the same line format as messages.txt:

    Normal message              → static or scroll depending on length
    [ICON:thermometer] -3C      → static/scroll with icon prefix
    [ANIM:print_head:4] 67%     → static/scroll with animation prefix

Add to config.json:
    {"name": "messages", "enabled": true, "messages": ["Hello!", "Ski season!"]}

The parse_message() function is also used by textfile.py so parsing behaviour
stays consistent between the two modules.
"""

import re
import logging

from modules.base import DisplayModule

logger = logging.getLogger(__name__)

_TAG = re.compile(r'^\[(ICON|ANIM):([^:\]]+)(?::(\d+))?\]\s*', re.IGNORECASE)

_DEFAULT_SCROLL_SPEED = 36
_DEFAULT_COLS = 32


def parse_message(line: str, cols: int = _DEFAULT_COLS, scroll_speed: int = _DEFAULT_SCROLL_SPEED) -> dict | None:
    """Parse one message string into a scene dict.

    Returns None if the line is empty or tag-only (nothing to display).
    Shared by both the messages and textfile modules.
    """
    extra: dict = {}

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
        return None

    try:
        from display import text_width
        w = text_width(line)
    except Exception:
        w = len(line) * 6  # rough fallback

    if w <= cols:
        return {'type': 'static', 'text': line, 'duration': 3.0, **extra}
    else:
        return {'type': 'scroll', 'text': line + '     ', 'speed': scroll_speed, **extra}


def _get_display_constants() -> tuple[int, int]:
    """Return (cols, scroll_speed) from the running display module if available."""
    try:
        import display as _d
        return _d.COLS, _d.SCROLL_SPEED
    except Exception:
        return _DEFAULT_COLS, _DEFAULT_SCROLL_SPEED


class Module(DisplayModule):
    def get_scenes(self) -> list:
        try:
            messages = self.config.get('messages', [])
            cols, scroll_speed = _get_display_constants()
            scenes = []
            for msg in messages:
                line = str(msg).strip()
                if line:
                    scene = parse_message(line, cols, scroll_speed)
                    if scene:
                        scenes.append(scene)
            return scenes
        except Exception:
            logger.exception('messages module error')
            return []
