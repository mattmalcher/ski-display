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
├── font.py       5×7 bitmap font, column-major bitmasks for MAX7219
├── display.py    Main display loop — scenes, transitions, file watching
└── web.py        Flask web UI for editing messages
install.sh        One-shot deploy script
led-matrix-display.html   Browser pixel-accurate emulator (reference/preview)
```

### Scene types

Messages are driven by `/home/matt/display/messages.txt` — one line per entry.

| Line content | Result |
|---|---|
| `CLOCK` | Live HH:MM clock, colon blinks on odd seconds |
| Short text (fits ≤32px wide) | Centred static frame, 3 seconds |
| Long text | Scrolls right-to-left at 36 px/sec |

The display watches the file for changes and reloads within ~2 seconds.

### Transitions

Scenes cycle through five transitions in rotation: slide-left, wipe-right, curtain, rain, dissolve — all with cubic ease-in-out, matching the browser emulator exactly.

## Deploy

```bash
# From this repo on your dev machine:
scp -r display/ install.sh matt@<pi-ip>:~/
ssh matt@<pi-ip> bash install.sh
```

The script:
1. Enables SPI (`raspi-config nonint do_spi 0`)
2. Installs Python packages into a venv at `/home/matt/display/.venv`
3. Creates two systemd services (`display` and `display-web`), enabled on boot

> **Note:** On Pi OS Trixie + Python 3.13, `luma.core` needs `RPi.GPIO`.
> The install script handles this by creating the venv with `--system-site-packages`
> (to access the system `python3-lgpio`) and installing `rpi-lgpio` via pip.

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

`display.py` has a commented-out stub at the bottom showing how to pull sensor
data from the HA REST API and write it into `messages.txt`. Uncomment and set
`HA_URL` / `HA_TOKEN` to enable.
