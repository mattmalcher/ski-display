#!/usr/bin/env python3
"""LED Matrix Display — 4× MAX7219, 32×8 px.

Scenes: static / scroll / clock
Transitions: slide-left, wipe-right, curtain, rain, dissolve
Watches messages.txt for changes and reloads live.
"""

import os
import time
import datetime
from PIL import Image
from luma.core.interface.serial import spi
from luma.led_matrix.device import max7219
from font import FONT

COLS, ROWS = 32, 8
MSG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'messages.txt')
TRANS_TYPES = ['slide-left', 'wipe-right', 'curtain', 'rain', 'dissolve']
SCROLL_SPEED = 36   # px/sec
FRAME_TIME   = 0.016  # ~60 fps target

# ── Hardware ──────────────────────────────────────────────────────────────────

serial = spi(port=0, device=0, gpio=None)
device = max7219(serial, cascaded=4, block_orientation=-90, rotate=0)
device.contrast(3)  # 0–15; 3 is readable indoors

# Shared PIL image reused every frame to avoid GC pressure
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


# ── Font helpers ──────────────────────────────────────────────────────────────

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


# ── Transitions ───────────────────────────────────────────────────────────────

def _ease(p):
    return 4 * p * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def apply_transition(disp, frm, to, kind, p):
    e = _ease(p)

    if kind == 'slide-left':
        off = int(e * COLS)
        for r in range(ROWS):
            for c in range(COLS):
                src = c + off
                disp.set(c, r, frm.get(src, r) if src < COLS else to.get(src - COLS, r))

    elif kind == 'wipe-right':
        wc = int(e * COLS)
        for r in range(ROWS):
            for c in range(COLS):
                disp.set(c, r, to.get(c, r) if c < wc else frm.get(c, r))

    elif kind == 'curtain':
        if p < 0.5:
            rr = int(p * 2 * ROWS)
            for r in range(ROWS):
                for c in range(COLS):
                    disp.set(c, r, 0 if r < rr else frm.get(c, r))
        else:
            rr = int((p - 0.5) * 2 * ROWS)
            for r in range(ROWS):
                for c in range(COLS):
                    disp.set(c, r, to.get(c, r) if r < rr else 0)

    elif kind == 'rain':
        for c in range(COLS):
            cp = min(1.0, max(0.0, (p - (c / COLS) * 0.55) / 0.45))
            filled = int(cp * ROWS)
            for r in range(ROWS):
                disp.set(c, r, to.get(c, r) if r < filled else frm.get(c, r))

    elif kind == 'dissolve':
        for r in range(ROWS):
            for c in range(COLS):
                h = ((c * 2749 ^ r * 1361 ^ (c * r + c) * 53) & 0x3FF) / 0x3FF
                disp.set(c, r, to.get(c, r) if h < e else frm.get(c, r))


# ── Scene rendering ───────────────────────────────────────────────────────────

def render(buf, scene, elapsed, scroll_x=0.0):
    buf.clear()
    kind = scene['type']

    if kind == 'clock':
        now = datetime.datetime.now()
        sep = ':' if now.second % 2 == 0 else ' '
        draw_centered(buf, now.strftime('%H') + sep + now.strftime('%M'))

    elif kind == 'static':
        draw_centered(buf, scene['text'])

    elif kind == 'scroll':
        draw_text(buf, scene['text'], COLS - int(scroll_x))


# ── Messages file ─────────────────────────────────────────────────────────────

def _mtime():
    try:
        return os.path.getmtime(MSG_FILE)
    except OSError:
        return 0.0


def load_scenes():
    try:
        lines = open(MSG_FILE).read().splitlines()
    except OSError:
        return [{'type': 'static', 'text': 'NO MSG', 'duration': 3.0}]
    scenes = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.upper() == 'CLOCK':
            scenes.append({'type': 'clock', 'duration': 5.0})
        elif text_width(line) <= COLS:
            scenes.append({'type': 'static', 'text': line, 'duration': 3.0})
        else:
            scenes.append({'type': 'scroll', 'text': line + '     ', 'speed': SCROLL_SPEED})
    return scenes or [{'type': 'static', 'text': 'EMPTY', 'duration': 3.0}]


# ── Display push ──────────────────────────────────────────────────────────────

def push(buf):
    for r in range(ROWS):
        base = r * COLS
        for c in range(COLS):
            _pix[c, r] = 255 if buf.data[base + c] else 0
    device.display(_img)


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    disp      = Buf()
    trans_idx = 0
    scenes    = load_scenes()
    mtime     = _mtime()
    last_mtime_check = time.monotonic()
    si        = 0

    while True:
        scene = scenes[si]

        # Build target buffer (scroll scenes render off-screen at sx=0, so to_buf is blank)
        to_buf = Buf()
        render(to_buf, scene, 0.0, 0.0)
        from_buf = disp.clone()

        # Transition in
        kind = TRANS_TYPES[trans_idx % len(TRANS_TYPES)]
        dur  = 0.35 if scene['type'] == 'scroll' else 0.62
        t0   = time.monotonic()
        while True:
            p = min(1.0, (time.monotonic() - t0) / dur)
            apply_transition(disp, from_buf, to_buf, kind, p)
            push(disp)
            if p >= 1.0:
                break
            time.sleep(FRAME_TIME)

        trans_idx += 1
        disp.copy_from(to_buf)

        # Scene playback
        t_start  = time.monotonic()
        t_prev   = t_start
        scroll_x = 0.0
        reload   = False

        while True:
            now     = time.monotonic()
            dt      = now - t_prev
            t_prev  = now
            elapsed = now - t_start
            done    = False

            if scene['type'] == 'scroll':
                scroll_x += scene['speed'] * dt
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

            # Check for file changes (~every 2 sec)
            if now - last_mtime_check >= 2.0:
                last_mtime_check = now
                mt = _mtime()
                if mt != mtime:
                    mtime  = mt
                    scenes = load_scenes()
                    si     = 0
                    reload = True
                    break

            if done:
                break
            time.sleep(FRAME_TIME)

        if not reload:
            si = (si + 1) % len(scenes)


if __name__ == '__main__':
    main()


# ── Home Assistant stub (uncomment and configure) ─────────────────────────────
# import urllib.request, json
#
# HA_URL   = 'http://homeassistant.local:8123'
# HA_TOKEN = 'your_long_lived_access_token'
#
# def ha_state(entity):
#     req = urllib.request.Request(
#         f'{HA_URL}/api/states/{entity}',
#         headers={'Authorization': f'Bearer {HA_TOKEN}'},
#     )
#     return json.loads(urllib.request.urlopen(req).read())['state']
#
# def inject_ha_data():
#     temp = ha_state('sensor.outdoor_temperature')
#     with open(MSG_FILE, 'w') as f:
#         f.write(f'CLOCK\nOUTDOOR TEMP: {temp}C\n')
#
# # Call inject_ha_data() on a timer (e.g. every 60 sec) or from a thread.
