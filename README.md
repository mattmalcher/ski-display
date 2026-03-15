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
├── display.py           Main display loop — rendering, transitions, hardware push
├── scheduler.py         Collects scenes from all modules; handles TTL and priority
├── transitions.py       Pluggable transition registry (5 built-in + custom support)
├── icons.py             Static icon bitmaps (column-major, same format as font.py)
├── animations.py        Multi-frame animations (same format, list of frames)
├── font.py              5×7 bitmap font, column-major bitmasks for MAX7219
├── web.py               Flask web UI for editing messages
├── config.json          Module enable/disable and per-module settings
└── modules/
    ├── base.py           DisplayModule base class
    ├── clock.py          Live HH:MM clock with blinking colon
    ├── textfile.py       Reads messages.txt; watches for live edits
    ├── weather.py        Current conditions via Open-Meteo (no API key needed)
    ├── stock.py          Stock ticker prices via yfinance
    ├── notable_dates.py  Date-based messages and countdown reminders
    ├── home_assistant.py Home Assistant sensor states via REST API
    ├── ics.py            Upcoming events from any iCal/ICS feed URL
    └── claude_usage.py   Claude.ai subscription message limit utilisation
install.sh               One-shot deploy script
led-matrix-display.html  Browser pixel-accurate emulator (reference/preview)
```

### Scene types

Messages are driven by `/home/matt/display/messages.txt` — one line per entry.

| Line content | Result |
|---|---|
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

### Available modules

#### `clock` — live clock
```json
{"name": "clock", "enabled": true, "duration": 5.0}
```
Displays a live HH:MM clock with a blinking colon. `duration` controls how long it stays on screen before rotating to the next scene.

---

#### `textfile` — messages file
```json
{"name": "textfile", "enabled": true, "file": "messages.txt", "reload_interval": 2.0}
```
Reads scenes from `messages.txt` (one line per entry). Watches for changes every `reload_interval` seconds and reloads live. See [Scene types](#scene-types) for supported line formats.

---

#### `weather` — current conditions
```json
{"name": "weather", "enabled": true, "location": "Aviemore", "fetch_interval": 600}
```
Fetches current temperature, conditions, and wind speed via [Open-Meteo](https://open-meteo.com/) — free, no API key required. Location is resolved by name using the Open-Meteo Geocoding API. No extra dependencies.

---

#### `stock` — stock ticker
```json
{"name": "stock", "enabled": true, "symbols": ["AAPL", "TSLA"], "fetch_interval": 300}
```
Shows price and daily change percentage for each symbol. Requires `yfinance` (`uv add yfinance`). Animated with `stock_up` / `stock_down` arrow animations.

---

#### `notable_dates` — date messages and countdowns
```json
{
    "name": "notable_dates",
    "enabled": true,
    "dates": [
        {"date": "2026-12-25", "message": "Merry Christmas!", "repeat": "annual", "reminder_days": [7, 3, 1]},
        {"date": "2026-06-15", "message": "Summer hols begin", "repeat": "none", "reminder_days": [14, 7]},
        {"date": "2026-03-19", "message": "Recycling bins", "repeat": "weekly", "interval_weeks": 2, "reminder_days": [1]}
    ]
}
```

Shows a message on the specified date, and countdown reminders on the days listed in `reminder_days`. Repeat modes:

| `repeat` | Behaviour |
|---|---|
| `"none"` | One-off; silently ignored once the date has passed |
| `"annual"` | Same month/day every year; year in the date field is ignored |
| `"weekly"` | Every N weeks anchored to the given date; use `interval_weeks` (default 1) |

---

#### `home_assistant` — sensor states
```json
{
    "name": "home_assistant",
    "enabled": true,
    "ha_url": "http://homeassistant.local:8123",
    "token": "your-long-lived-access-token",
    "entity_ids": ["sensor.living_room_temperature", "sensor.outdoor_humidity"],
    "fetch_interval": 60,
    "ttl": 120
}
```
Fetches entity states from the Home Assistant REST API. The `token` is a long-lived access token from your HA profile page. Short readings display as static; long text scrolls automatically. No extra dependencies.

---

#### `ics` — iCal / calendar events
```json
{
    "name": "ics",
    "enabled": true,
    "ical_url": "https://...",
    "days_ahead": 7,
    "fetch_interval": 900
}
```
Shows upcoming events from any iCal feed URL. Handles recurring events. Events today are shown at `priority: 2` (appear more frequently); future events show day/time until the event. Requires `icalendar` and `recurring-ical-events` (`uv add icalendar recurring-ical-events`).

ICS feed URLs by provider:
- **Google Calendar:** Settings → (select calendar) → Integrate calendar → "Secret address in iCal format"
- **Outlook / Hotmail:** Settings → View all Outlook settings → Calendar → Shared calendars → Publish a calendar → copy the ICS link
- **Apple iCloud:** Calendar app → right-click calendar → Share Calendar → Public Calendar → copy the link (change `webcal://` to `https://`)

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

---

#### `claude_usage` — Claude.ai subscription usage
```json
{
  "name": "claude_usage",
  "enabled": true,
  "session_key": "sk-ant-sid01-...",
  "org_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "fetch_interval": 120
}
```
Shows message limit utilisation and reset times for the 5-hour and 7-day rolling windows, e.g. `Claude 5h 31% resets 15:00`. Polls every `fetch_interval` seconds (default 120). No extra dependencies.

**Finding your `session_key`:** Log in to claude.ai → DevTools (F12) → Application → Cookies → `https://claude.ai` → copy the `sessionKey` value (starts with `sk-ant-sid01-`). The cookie expires roughly every 30 days; when it does the module silently produces no scenes and logs `session expired — update session_key in config`.

**Finding your `org_id`:** Visit `claude.ai/settings/usage`, open DevTools → Network, and look for the request to `/api/organizations/<org_id>/usage` — the UUID in that URL is your org ID.
