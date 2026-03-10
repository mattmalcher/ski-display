# LED Matrix Info Display — Project Brief

## What We're Building

A wall-mounted LED dot matrix display unit, styled after 2010s-era ski resort lift status boards. It will live at a remote location (parents' house) and be updated over Tailscale. Messages and data are edited via SSH or a simple web UI.

## Hardware

| Component | Spec |
|---|---|
| Pi Zero 2W | Main compute, runs Pi OS Lite (64-bit, Bookworm) |
| 4× MAX7219 8×8 LED matrix modules | Chained via SPI, FC16 type (the common black PCB modules) |
| 5V 3A USB-C PSU | Powers both Pi and display — shared GND, separate 5V rail to matrices |

**Physical dimensions:** ~4 modules × 32mm wide = ~130mm × 35mm display face. Target housing approx 40cm × 5cm (room to expand to more modules later).

## Wiring

MAX7219 uses SPI. All 4 modules share CLK and CS. Daisy-chained DOUT→DIN.

| MAX7219 pin | Pi Zero 2W GPIO | Physical pin |
|---|---|---|
| VCC | — (separate 5V rail) | — |
| GND | GND (shared) | Pin 6 |
| DIN | GPIO 10 (MOSI) | Pin 19 |
| CS | GPIO 8 (CE0) | Pin 24 |
| CLK | GPIO 11 (SCLK) | Pin 23 |

Chain: `Pi → Module 1 DOUT → Module 2 DIN → Module 3 DIN → Module 4 DIN`

SPI must be enabled: `sudo raspi-config` → Interface Options → SPI → Enable.

## Software Stack

- **OS:** Pi OS Lite 64-bit (Bookworm), headless
- **Python library:** `luma.led_matrix` (handles SPI, MAX7219, fonts, scrolling)
- **Remote access:** Tailscale (already set up — SSH via Tailscale IP from anywhere)
- **Message update method:** Edit `/home/pi/display/messages.txt` over SSH, or via Flask web UI on the Tailscale IP
- **Boot:** systemd service, starts display script on boot
- **Resilience:** overlayfs read-only root filesystem (raspi-config → Performance → Overlay FS), messages.txt on a small separate writable partition

## Display Behaviour

The display is **32×8 pixels** (4 chained 8×8 modules). Font is 5×7 pixel bitmap, fits ~5 characters across.

Each panel cycles through **scenes** with **transitions** between them:

**Scene types:**
- `static` — short text centred or left/right aligned, shown for a fixed duration
- `blink` — alternates between two strings at a set interval
- `scroll` — text scrolls right-to-left across the display
- `clock` — live HH:MM, colon blinks on odd seconds

**Transitions** (rotate through): slide-left, wipe-right, curtain, column-rain, dissolve

**Scroll speed:** ~36px/sec (fast and readable — not a crawl)

**Scene staggering:** Each panel unit starts with a different delay so they're not all in sync.

## File Structure

```
/home/pi/display/
├── display.py          # Main display loop
├── messages.txt        # Editable message file, watched for changes
├── font.py             # 5×7 bitmap font, column-major for MAX7219
└── web.py              # Optional Flask UI for editing messages
```

## messages.txt Format

Plain text, one message per line. Long lines scroll automatically. Short lines show as static frames.

```
WELCOME TO THE SMITH HOUSE
DINNER AT 7PM TONIGHT
BIN DAY TOMORROW - BLUE BIN
TEMP -3C OUTSIDE - WRAP UP!
```

The display script watches `mtime` on this file and reloads without restart when it changes.

## display.py — Key Logic

```python
from luma.core.interface.serial import spi
from luma.led_matrix.device import max7219
from luma.core.render import canvas
from luma.core.legacy import text, show_message
from luma.core.legacy.font import proportional, CP437_FONT

serial = spi(port=0, device=0, gpio=None)
device = max7219(serial, cascaded=4, block_orientation=-90, rotate=0)
device.contrast(3)  # 0–15, 3 is readable indoors without being blinding
```

`block_orientation=-90` is required for the common FC16 modules — without it columns are scrambled.

Main loop:
1. Load `messages.txt`
2. For each line: if short → show as static frame with transition in/out; if long → scroll through
3. Watch `mtime` of messages.txt — reload on change
4. Loop forever

## Transition Implementation

Transitions operate on pixel buffers (2D arrays of 0/1). Apply for ~600ms between scenes:

- **slide-left:** old buffer slides out left as new slides in from right
- **wipe-right:** column by column reveal left to right
- **curtain:** rows collapse to centre then expand to reveal new content
- **rain:** columns fill top-to-bottom, left column first
- **dissolve:** pseudo-random pixel-by-pixel crossfade

## Web UI (Optional)

Simple Flask app on port 5000, accessible at `http://<tailscale-ip>:5000`:
- Single textarea showing current messages.txt content
- Submit button writes file
- Display picks up change within ~2 seconds automatically

## systemd Service

```ini
# /etc/systemd/system/display.service
[Unit]
Description=LED Matrix Display
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/display/display.py
WorkingDirectory=/home/pi/display
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Enable: `sudo systemctl enable display && sudo systemctl start display`

## What Claude Code Should Produce

1. `font.py` — complete 5×7 bitmap font dict, compiled to column-major bitmasks
2. `display.py` — full display loop with scene system, transitions, file watching
3. `web.py` — minimal Flask message editor
4. `install.sh` — installs dependencies, copies files, enables systemd service

## Dependencies to Install

```bash
pip3 install luma.led_matrix flask --break-system-packages
# or in a venv:
python3 -m venv /home/pi/display/.venv
source /home/pi/display/.venv/bin/activate
pip install luma.led_matrix flask
```

## Future / Home Assistant Integration

The display script should be written so data sources are swappable. A commented-out stub should show how to pull from HA REST API:

```python
# HA_URL   = 'http://homeassistant.local:8123'
# HA_TOKEN = 'your_long_lived_access_token'
# GET /api/states/sensor.outdoor_temperature → inject into messages
```

Eventually messages.txt may be replaced or supplemented by HA sensor data pushed via MQTT or polled via REST.

## Reference: Browser Emulator

A browser-based pixel-accurate emulator of this display exists (`led-matrix-display.html`) showing the exact 32×8 dot matrix with amber LED rendering, all transition effects, and the scene system. The Python implementation should match this behaviour closely. The font and transition logic in that file can be used as a reference implementation.
