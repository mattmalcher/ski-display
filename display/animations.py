"""Animations and icons for the LED matrix display.

Format: each entry is a list of frames.
Each frame is a list of column bitmasks — column-major, bit 0 = top row.
A 1-frame entry is a static icon; multi-frame entries animate over time.

Scene dict usage:
    {'type': 'scroll', 'text': 'Print 67%', 'animation': 'print_head', 'anim_fps': 4}
    {'type': 'static', 'text': '-3C', 'icon': 'thermometer'}

The frame is selected by: frame_idx = int(elapsed * anim_fps) % len(frames)
For 1-frame entries (icons) the frame index is always 0.
"""

# Row-string source for each frame, compiled to column bitmasks at import time.
# Format: list of frames, each frame is a list of row strings (same as icons._SRC).

_SRC = {
    # 3D printer nozzle moving left → centre → right (3 frames, 6 wide)
    'print_head': [
        [   # frame 0: nozzle left
            '######',
            '......',
            '.####.',
            '..##..',
            '..#...',
            '..#...',
            '......',
            '......',
        ],
        [   # frame 1: nozzle centre (drip forming)
            '######',
            '......',
            '.####.',
            '..##..',
            '..##..',
            '...#..',
            '......',
            '......',
        ],
        [   # frame 2: nozzle right
            '######',
            '......',
            '.####.',
            '..##..',
            '...#..',
            '...#..',
            '......',
            '......',
        ],
    ],

    # Spinning indicator — 4 frames (5 wide × 8 tall)
    'loading': [
        [   # frame 0: horizontal bar
            '.....',
            '.....',
            '.....',
            '#####',
            '.....',
            '.....',
            '.....',
            '.....',
        ],
        [   # frame 1: diagonal /
            '....#',
            '...#.',
            '..#..',
            '.#...',
            '#....',
            '.....',
            '.....',
            '.....',
        ],
        [   # frame 2: vertical bar
            '..#..',
            '..#..',
            '..#..',
            '..#..',
            '..#..',
            '.....',
            '.....',
            '.....',
        ],
        [   # frame 3: diagonal \
            '#....',
            '.#...',
            '..#..',
            '...#.',
            '....#',
            '.....',
            '.....',
            '.....',
        ],
    ],

    # Stock ticker up arrow — 1-frame (static, but consistent format)
    'stock_up': [
        [
            '..#..',
            '.###.',
            '#####',
            '..#..',
            '..#..',
            '..#..',
            '..#..',
            '.....',
        ],
    ],

    # Stock ticker down arrow
    'stock_down': [
        [
            '..#..',
            '..#..',
            '..#..',
            '..#..',
            '#####',
            '.###.',
            '..#..',
            '.....',
        ],
    ],

    # Blinking dot — 2 frames (signals "live" data)
    'live': [
        [   # frame 0: dot on
            '.....',
            '.....',
            '.....',
            '..#..',
            '.....',
            '.....',
            '.....',
            '.....',
        ],
        [   # frame 1: dot off
            '.....',
            '.....',
            '.....',
            '.....',
            '.....',
            '.....',
            '.....',
            '.....',
        ],
    ],

    # ── Static icons (1-frame) ─────────────────────────────────────────────────

    'thermometer': [[
        '..#..',
        '..#..',
        '..#..',
        '.###.',
        '#...#',
        '#...#',
        '.###.',
        '.....',
    ]],

    'battery_ok': [[
        '.#####.',
        '#.....#',
        '#.###.#',
        '#.###.#',
        '#.###.#',
        '#.....#',
        '.#####.',
        '.......',
    ]],

    'battery_low': [[
        '.#####.',
        '#.....#',
        '#.#...#',
        '#.#...#',
        '#.#...#',
        '#.....#',
        '.#####.',
        '.......',
    ]],

    'wifi': [[
        '#####',
        '#...#',
        '.###.',
        '.#.#.',
        '..#..',
        '.....',
        '..#..',
        '.....',
    ]],

    'snowflake': [[
        '#.#.#',
        '.###.',
        '#####',
        '.###.',
        '#.#.#',
        '.....',
        '.....',
        '.....',
    ]],

    'arrow_up': [[
        '..#..',
        '.###.',
        '#####',
        '..#..',
        '..#..',
        '..#..',
        '..#..',
        '.....',
    ]],

    'arrow_down': [[
        '..#..',
        '..#..',
        '..#..',
        '..#..',
        '#####',
        '.###.',
        '..#..',
        '.....',
    ]],

    'clock': [[
        '.###.',
        '#...#',
        '#.#.#',
        '#.##.',
        '#...#',
        '.###.',
        '.....',
        '.....',
    ]],

    'ski': [[
        '.....',
        '..#..',
        '.###.',
        '..#..',
        '..#..',
        '..###',
        '.....',
        '.....',
    ]],
}


def _compile_frame(rows: list) -> list:
    h = len(rows)
    w = max(len(r) for r in rows)
    cols = []
    for c in range(w):
        b = 0
        for r in range(h):
            ch = rows[r][c] if c < len(rows[r]) else '.'
            if ch == '#':
                b |= (1 << r)
        cols.append(b)
    return cols


def _compile(src: dict) -> dict:
    out = {}
    for name, frames in src.items():
        out[name] = [_compile_frame(frame) for frame in frames]
    return out


ANIMATIONS = _compile(_SRC)
