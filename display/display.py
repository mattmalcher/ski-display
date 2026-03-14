#!/usr/bin/env python3
"""LED Matrix Display — 4× MAX7219, 32×8 px.

Scene types: static / scroll / clock
Icons and animations can be prefixed to any scene (see icons.py, animations.py).
Transitions are pluggable (see transitions.py).
Modules provide scenes independently (see modules/).
"""

import json
import logging
import os
import sys
import time
import datetime
import importlib

from PIL import Image
from luma.core.interface.serial import spi
from luma.led_matrix.device import max7219

from font import FONT
from icons import ICONS
from animations import ANIMATIONS
from transitions import TRANSITIONS, _ease, register as register_transition  # noqa: F401
from scheduler import SceneScheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)

# ── Constants (overridable from config.json) ───────────────────────────────────

COLS, ROWS = 32, 8
SCROLL_SPEED = 36     # px/sec
FRAME_TIME   = 0.016  # ~60 fps target

# ── Config ────────────────────────────────────────────────────────────────────

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def load_config() -> dict:
    try:
        with open(_CONFIG_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning('Could not load config.json (%s), using defaults', e)
        return {}


def load_modules(config: dict) -> list:
    """Instantiate enabled modules from config."""
    modules = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    for mc in config.get('modules', []):
        if not mc.get('enabled', True):
            continue
        name = mc.get('name', '')
        try:
            mod = importlib.import_module(f'modules.{name}')
            cls = getattr(mod, 'Module')
            modules.append(cls(mc))
            logger.info('Loaded module: %s', name)
        except Exception:
            logger.exception('Failed to load module %r', name)

    if not modules:
        logger.warning('No modules loaded — falling back to textfile module')
        from modules.textfile import Module as TextfileModule
        modules.append(TextfileModule({'name': 'textfile', 'enabled': True}))

    return modules


# ── Hardware ──────────────────────────────────────────────────────────────────

serial = spi(port=0, device=0, gpio=None)
device = max7219(serial, cascaded=4, block_orientation=-90, rotate=0)

# PIL image reused every frame to avoid GC pressure
_img = Image.new('1', (COLS, ROWS), 0)
_pix = _img.load()


# ── Pixel Buffer ──────────────────────────────────────────────────────────────

class Buf:
    __slots__ = ('data',)

    def __init__(self):
        self.data = bytearray(COLS * ROWS)

    def clear(self):
        self.data = bytearray(COLS * ROWS)

    def set(self, c, r, v):
        if 0 <= c < COLS and 0 <= r < ROWS:
            self.data[r * COLS + c] = v

    def get(self, c, r):
        if 0 <= c < COLS and 0 <= r < ROWS:
            return self.data[r * COLS + c]
        return 0

    def clone(self):
        b = Buf()
        b.data[:] = self.data
        return b

    def copy_from(self, other):
        self.data[:] = other.data


# ── Font helpers ───────────────────────────────────────────────────────────────

def _glyph(ch):
    return FONT.get(ch.upper(), FONT.get(' ', [0]))


def text_width(s):
    if not s:
        return 0
    return sum(len(_glyph(c)) + 1 for c in s) - 1


def draw_text(buf, s, col, row=0):
    x = col
    for ch in s:
        g = _glyph(ch)
        for ci, coldata in enumerate(g):
            for ri in range(7):
                if coldata & (1 << ri):
                    buf.set(x + ci, row + ri, 1)
        x += len(g) + 1


def draw_centered(buf, s, row=0):
    draw_text(buf, s, (COLS - text_width(s)) // 2, row)


# ── Icon / animation drawing ───────────────────────────────────────────────────

def draw_bitmap(buf, cols: list, col: int, row: int = 0) -> int:
    """Draw a list of column bitmasks at (col, row). Returns pixel width drawn."""
    for ci, coldata in enumerate(cols):
        for ri in range(8):
            if coldata & (1 << ri):
                buf.set(col + ci, row + ri, 1)
    return len(cols)


def draw_icon(buf, name: str, col: int, row: int = 0) -> int:
    """Draw a named icon. Returns pixel width consumed (0 if icon not found)."""
    glyph = ICONS.get(name)
    if not glyph:
        logger.debug('Icon not found: %s', name)
        return 0
    return draw_bitmap(buf, glyph, col, row)


def draw_animation_frame(buf, name: str, elapsed: float, fps: float,
                          col: int, row: int = 0) -> int:
    """Draw the current frame of a named animation. Returns pixel width consumed."""
    frames = ANIMATIONS.get(name)
    if not frames:
        logger.debug('Animation not found: %s', name)
        return 0
    frame = frames[int(elapsed * fps) % len(frames)]
    return draw_bitmap(buf, frame, col, row)


# ── Transitions ────────────────────────────────────────────────────────────────

def apply_transition(disp, frm, to, kind, p):
    e = _ease(p)
    fn = TRANSITIONS.get(kind)
    if fn is None:
        logger.warning('Unknown transition %r, falling back to dissolve', kind)
        fn = TRANSITIONS['dissolve']
    fn(disp, frm, to, e, COLS, ROWS)


# ── Scene rendering ────────────────────────────────────────────────────────────

def _draw_prefix(buf, scene, elapsed) -> int:
    """Draw icon or animation prefix. Returns starting column for text."""
    anim = scene.get('animation')
    if anim:
        fps = scene.get('anim_fps', 4)
        w = draw_animation_frame(buf, anim, elapsed, fps, col=1)
        return 1 + w + 1 if w else 0

    icon = scene.get('icon')
    if icon:
        w = draw_icon(buf, icon, col=1)
        return 1 + w + 1 if w else 0

    return 0  # no prefix


def render(buf, scene, elapsed, scroll_x=0.0):
    buf.clear()
    kind = scene['type']

    if kind == 'clock':
        now = datetime.datetime.now()
        sep = ':' if now.second % 2 == 0 else ' '
        draw_centered(buf, now.strftime('%H') + sep + now.strftime('%M'))

    elif kind == 'static':
        text_col = _draw_prefix(buf, scene, elapsed)
        if text_col:
            draw_text(buf, scene['text'], text_col)
        else:
            draw_centered(buf, scene['text'])

    elif kind == 'scroll':
        text_col = _draw_prefix(buf, scene, elapsed)
        x = (text_col if text_col else COLS) - int(scroll_x)
        draw_text(buf, scene['text'], x)


# ── Display push ───────────────────────────────────────────────────────────────

def push(buf):
    for r in range(ROWS):
        base = r * COLS
        for c in range(COLS):
            _pix[c, r] = 255 if buf.data[base + c] else 0
    device.display(_img)


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    config = load_config()

    # Apply config overrides to module-level constants
    global SCROLL_SPEED, FRAME_TIME
    dcfg = config.get('display', {})
    SCROLL_SPEED = dcfg.get('scroll_speed', SCROLL_SPEED)
    FRAME_TIME   = dcfg.get('frame_time', FRAME_TIME)
    contrast     = dcfg.get('contrast', 3)
    refresh_interval = dcfg.get('scheduler_refresh_interval', 5.0)

    device.contrast(contrast)

    modules   = load_modules(config)
    scheduler = SceneScheduler(modules, refresh_interval=refresh_interval)
    scheduler.start()

    trans_keys = list(TRANSITIONS.keys())
    trans_idx  = 0
    si         = 0

    disp = Buf()

    while True:
        scene = scheduler[si]

        # Build target buffer for transition
        to_buf = Buf()
        render(to_buf, scene, 0.0, 0.0)
        from_buf = disp.clone()

        # Pick transition — scene can override the auto-cycle
        if scene.get('transition') and scene['transition'] in TRANSITIONS:
            kind = scene['transition']
        else:
            trans_keys = list(TRANSITIONS.keys())  # re-read in case modules registered new ones
            kind = trans_keys[trans_idx % len(trans_keys)]
            trans_idx += 1

        dur = 0.35 if scene['type'] == 'scroll' else 0.62
        t0  = time.monotonic()
        while True:
            p = min(1.0, (time.monotonic() - t0) / dur)
            apply_transition(disp, from_buf, to_buf, kind, p)
            push(disp)
            if p >= 1.0:
                break
            time.sleep(FRAME_TIME)

        disp.copy_from(to_buf)

        # Scene playback
        t_start  = time.monotonic()
        t_prev   = t_start
        scroll_x = 0.0
        refreshed = False

        while True:
            now     = time.monotonic()
            dt      = now - t_prev
            t_prev  = now
            elapsed = now - t_start
            done    = False

            if scene['type'] == 'scroll':
                scroll_x += scene.get('speed', SCROLL_SPEED) * dt
                if scroll_x > COLS + text_width(scene['text']) + 4:
                    done = True
                else:
                    render(disp, scene, elapsed, scroll_x)
                    push(disp)
            else:
                render(disp, scene, elapsed)
                push(disp)
                if elapsed >= scene['duration']:
                    done = True

            if scheduler.maybe_refresh(now):
                refreshed = True
                break

            if done:
                break

            time.sleep(FRAME_TIME)

        if refreshed:
            si = 0
        else:
            si = (si + 1) % len(scheduler)


if __name__ == '__main__':
    main()
