"""Static icon bitmaps for the LED matrix display.

Format mirrors font.py exactly: column-major bitmasks, bit 0 = top row.
Icons are 8 rows tall (full display height) unless otherwise noted.

Add new icons by extending _SRC with an 8-element list of equal-length row strings.
Use '#' for lit pixels and '.' (or space) for dark.
"""

_SRC = {
    'thermometer': [
        '..#..',
        '..#..',
        '..#..',
        '.###.',
        '#...#',
        '#...#',
        '.###.',
        '.....',
    ],
    'battery_ok': [
        '.#####.',
        '#.....#',
        '#.###.#',
        '#.###.#',
        '#.###.#',
        '#.....#',
        '.#####.',
        '.......',
    ],
    'battery_low': [
        '.#####.',
        '#.....#',
        '#.#...#',
        '#.#...#',
        '#.#...#',
        '#.....#',
        '.#####.',
        '.......',
    ],
    'wifi': [
        '#####',
        '#...#',
        '.###.',
        '.#.#.',
        '..#..',
        '.....',
        '..#..',
        '.....',
    ],
    'snowflake': [
        '#.#.#',
        '.###.',
        '#####',
        '.###.',
        '#.#.#',
        '.....',
        '.....',
        '.....',
    ],
    'print_head': [
        '######',
        '......',
        '.####.',
        '..##..',
        '..##..',
        '...##.',
        '...#..',
        '......',
    ],
    'arrow_up': [
        '..#..',
        '.###.',
        '#####',
        '..#..',
        '..#..',
        '..#..',
        '..#..',
        '.....',
    ],
    'arrow_down': [
        '..#..',
        '..#..',
        '..#..',
        '..#..',
        '#####',
        '.###.',
        '..#..',
        '.....',
    ],
    'clock': [
        '.###.',
        '#...#',
        '#.#.#',
        '#.##.',
        '#...#',
        '.###.',
        '.....',
        '.....',
    ],
    'ski': [
        '.....',
        '..#..',
        '.###.',
        '..#..',
        '..#..',
        '..###',
        '.....',
        '.....',
    ],
}


def _compile(src: dict) -> dict:
    out = {}
    for name, rows in src.items():
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
        out[name] = cols
    return out


ICONS = _compile(_SRC)
