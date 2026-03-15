# ski-display

Wall-mounted LED dot matrix display styled after ski resort lift status boards.
Lives at a remote location, updated over Tailscale via SSH or web UI.

## Hardware

| Component | Spec |
|---|---|
| Pi Zero 2W | Main compute, Pi OS Trixie 64-bit headless |
| 4× MAX7219 8×8 modules | Chained via SPI, FC16 type (common black PCB) |
| 5V 3A USB-C PSU | Powers Pi and display — shared GND, separate 5V rail |

**Display:** 32×8 pixels (4 chained 8×8 modules), ~130mm × 35mm face.

### Wiring

| MAX7219 pin | Pi Zero 2W GPIO | Physical pin |
|---|---|---|
| VCC | — (separate 5V rail) | — |
| GND | GND (shared) | Pin 6 |
| DIN | GPIO 10 (MOSI) | Pin 19 |
| CS | GPIO 8 (CE0) | Pin 24 |
| CLK | GPIO 11 (SCLK) | Pin 23 |

Chain: `Pi → Module 1 DOUT → Module 2 DIN → Module 3 DIN → Module 4 DIN`

## Software

```
display/
├── display.py        Main display loop — rendering, transitions, hardware push
├── scheduler.py      Collects scenes from all modules; handles TTL and priority
├── transitions.py    Pluggable transition registry (5 built-in + custom support)
├── icons.py          Static icon bitmaps (column-major, same format as font.py)
├── animations.py     Multi-frame animations (same format, list of frames)
├── font.py           5×7 bitmap font, column-major bitmasks for MAX7219
├── web.py            Flask web UI for editing messages
├── config.json       Module enable/disable and per-module settings
└── modules/
    ├── base.py       DisplayModule base class
    ├── textfile.py   Reads messages.txt; built-in, always active
    └── …             Add new modules here (weather, stock, print status, …)
install.sh            One-shot deploy script
led-matrix-display.html   Browser pixel-accurate emulator (reference/preview)
```

### Scene types

Messages are driven by `/home/matt/display/messages.txt` — one line per entry.

| Line content | Result |
|---|---|
| `CLOCK` | Live HH:MM clock, colon blinks on odd seconds |
| Short text (fits ≤32px wide) | Centred static frame, 3 seconds |
| Long text | Scrolls right-to-left at 36 px/sec |
| `[ICON:name] text` | Prefixes text with a static icon (see `icons.py` for names) |
| `[ANIM:name] text` | Prefixes text with an animation (see `animations.py` for names) |
| `[ANIM:name:fps] text` | Same, with explicit frame rate (default 4 fps) |

The display watches the file for changes and reloads within ~2 seconds.

**Available icons:** `thermometer`, `battery_ok`, `battery_low`, `wifi`, `snowflake`, `print_head`, `arrow_up`, `arrow_down`, `clock`, `ski`

**Available animations:** `print_head`, `loading`, `stock_up`, `stock_down`, `live`

### Transitions

Five built-in transitions cycle automatically: `slide-left`, `wipe-right`, `curtain`, `rain`, `dissolve` — all with cubic ease-in-out.

Custom transitions can be registered from any module via `transitions.register(name, fn)`. A scene can also pin a specific transition with `scene['transition'] = 'name'`.

### Module system

Each data source is an independent module in `display/modules/`. Modules run independently — if one crashes or loses its data source, the rest keep displaying.

**Key scene dict fields:**

| Field | Type | Description |
|---|---|---|
| `type` | str | `'static'`, `'scroll'`, or `'clock'` |
| `text` | str | Text to display |
| `duration` | float | Seconds to show (static/clock) |
| `speed` | int | Scroll speed in px/sec (default 36) |
| `icon` | str | Icon name to prefix |
| `animation` | str | Animation name to prefix (takes precedence over icon) |
| `ttl` | float | Seconds before scene is considered stale and dropped |
| `priority` | int | Repeat count in rotation (default 1; higher = more frequent) |
| `transition` | str | Override the auto-cycle transition for this scene |

**Multiple instances:** You can add the same module name more than once in `config.json` — each entry gets its own independent instance. This is useful for e.g. showing events from two different `ics` calendars, or tracking two separate sets of `stock` symbols.

**Adding a module:**

1. Create `display/modules/yourmodule.py` with a class `Module(DisplayModule)`
2. Implement `get_scenes() -> list` — must never raise
3. Enable it in `config.json`
4. Redeploy with `install.sh`

For modules that fetch data over the network, run the fetch in a daemon thread and cache results — `get_scenes()` should only read the cache so it never blocks the render loop.

## Deploy

```bash
# From this repo on your dev machine:
scp -r display/ install.sh pyproject.toml uv.lock matt@<pi-ip>:~/
ssh matt@<pi-ip> bash install.sh
```

The script:
1. Enables SPI (`raspi-config nonint do_spi 0`)
2. Installs [uv](https://docs.astral.sh/uv/) if not already present
3. Syncs the Python environment from `uv.lock` into `/home/matt/display/.venv`
4. Creates two systemd services (`display` and `display-web`), enabled on boot

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`. To add a dependency: `uv add <package>`, then redeploy.

## Usage

**Edit messages via SSH:**
```bash
ssh matt@<pi-ip>
nano /home/matt/display/messages.txt
```

**Edit messages via web UI:**
Open `http://<pi-ip>:5000` in a browser.

**Service management:**
```bash
sudo systemctl status display
sudo systemctl status display-web
journalctl -u display -f
```

## Home Assistant integration

Create `display/modules/homeassistant.py` with a `Module` class that fetches
sensor states from the HA REST API and returns them as scenes. Enable it in
`config.json` with your `ha_url` and `ha_token`. Use a daemon thread for the
HTTP fetch and cache results so the render loop is never blocked.
