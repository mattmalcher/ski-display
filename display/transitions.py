"""Pluggable transition registry for the LED matrix display.

Each transition function signature:
    fn(disp, frm, to, e, COLS, ROWS)
where `e` is the eased progress value (0.0 → 1.0).

Register custom transitions with `register(name, fn)`.
"""

import logging

logger = logging.getLogger(__name__)

COLS, ROWS = 32, 8


def _ease(p):
    return 4 * p * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def _slide_left(disp, frm, to, e, COLS, ROWS):
    off = int(e * COLS)
    for r in range(ROWS):
        for c in range(COLS):
            src = c + off
            disp.set(c, r, frm.get(src, r) if src < COLS else to.get(src - COLS, r))


def _wipe_right(disp, frm, to, e, COLS, ROWS):
    wc = int(e * COLS)
    for r in range(ROWS):
        for c in range(COLS):
            disp.set(c, r, to.get(c, r) if c < wc else frm.get(c, r))


def _curtain(disp, frm, to, e, COLS, ROWS):
    p = e  # already eased by caller — but curtain uses raw p for the midpoint split
    # Re-derive raw p: undo ease for curtain's two-phase logic by using e directly
    if e < 0.5:
        rr = int(e * 2 * ROWS)
        for r in range(ROWS):
            for c in range(COLS):
                disp.set(c, r, 0 if r < rr else frm.get(c, r))
    else:
        rr = int((e - 0.5) * 2 * ROWS)
        for r in range(ROWS):
            for c in range(COLS):
                disp.set(c, r, to.get(c, r) if r < rr else 0)


def _rain(disp, frm, to, e, COLS, ROWS):
    for c in range(COLS):
        cp = min(1.0, max(0.0, (e - (c / COLS) * 0.55) / 0.45))
        filled = int(cp * ROWS)
        for r in range(ROWS):
            disp.set(c, r, to.get(c, r) if r < filled else frm.get(c, r))


def _dissolve(disp, frm, to, e, COLS, ROWS):
    for r in range(ROWS):
        for c in range(COLS):
            h = ((c * 2749 ^ r * 1361 ^ (c * r + c) * 53) & 0x3FF) / 0x3FF
            disp.set(c, r, to.get(c, r) if h < e else frm.get(c, r))


TRANSITIONS = {
    'slide-left': _slide_left,
    'wipe-right': _wipe_right,
    'curtain':    _curtain,
    'rain':       _rain,
    'dissolve':   _dissolve,
}


def register(name: str, fn) -> None:
    """Register a custom transition function under the given name.

    The function will be available for use by name in scene dicts
    (``scene['transition'] = name``) and will be added to the auto-cycle.
    """
    TRANSITIONS[name] = fn
    logger.info('Registered custom transition: %s', name)
