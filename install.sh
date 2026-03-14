#!/usr/bin/env bash
# LED Matrix Display — install script
# Run on the Pi: bash install.sh
set -euo pipefail

DEST=/home/matt/display
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "=== LED Matrix Display — Install ==="

# ── SPI ──────────────────────────────────────────────────────────────────────
echo "Enabling SPI..."
sudo raspi-config nonint do_spi 0
# Try to load kernel module now so we don't need a reboot
sudo modprobe spi-bcm2835 2>/dev/null || true
sudo modprobe spidev        2>/dev/null || true

if [ ! -e /dev/spidev0.0 ]; then
    echo "WARNING: /dev/spidev0.0 not found yet."
    echo "         SPI will be active after reboot: sudo reboot"
fi

# ── Files ────────────────────────────────────────────────────────────────────
echo "Installing files to $DEST..."
mkdir -p "$DEST"
SRC="$HERE/display"
if [ "$SRC" != "$DEST" ]; then
    cp "$SRC/font.py"        "$DEST/"
    cp "$SRC/display.py"     "$DEST/"
    cp "$SRC/web.py"         "$DEST/"
    cp "$SRC/transitions.py" "$DEST/"
    cp "$SRC/scheduler.py"   "$DEST/"
    cp "$SRC/icons.py"       "$DEST/"
    cp "$SRC/animations.py"  "$DEST/"
    # Copy modules directory (always overwrite module code)
    cp -r "$SRC/modules/" "$DEST/"
fi

# config.json: only copy on first install to preserve user customisations
if [ ! -f "$DEST/config.json" ]; then
    cp "$SRC/config.json" "$DEST/"
fi

if [ ! -f "$DEST/messages.txt" ]; then
    cat > "$DEST/messages.txt" << 'MSG'
CLOCK
WELCOME
EDIT VIA WEB UI
MSG
fi

# ── Python venv ───────────────────────────────────────────────────────────────
echo "Creating venv and installing packages..."
# --system-site-packages makes the system python3-lgpio available in the venv
python3 -m venv --system-site-packages "$DEST/.venv"
"$DEST/.venv/bin/pip" install --quiet --upgrade pip
"$DEST/.venv/bin/pip" install --quiet luma.led_matrix flask rpi-lgpio

# ── systemd: display ─────────────────────────────────────────────────────────
sudo tee /etc/systemd/system/display.service > /dev/null << EOF
[Unit]
Description=LED Matrix Display
After=network.target

[Service]
ExecStart=$DEST/.venv/bin/python3 $DEST/display.py
WorkingDirectory=$DEST
Restart=always
RestartSec=5
User=matt

[Install]
WantedBy=multi-user.target
EOF

# ── systemd: web UI ───────────────────────────────────────────────────────────
sudo tee /etc/systemd/system/display-web.service > /dev/null << EOF
[Unit]
Description=LED Display Web UI
After=network.target

[Service]
ExecStart=$DEST/.venv/bin/python3 $DEST/web.py
WorkingDirectory=$DEST
Restart=always
RestartSec=5
User=matt

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable display display-web
sudo systemctl restart display display-web

echo ""
echo "=== Done ==="
echo ""
echo "  Display service:  sudo systemctl status display"
echo "  Web UI service:   sudo systemctl status display-web"
echo "  Logs:             journalctl -u display -f"
echo "  Web UI:           http://$(hostname -I | awk '{print $1}'):5000"
echo ""
if [ ! -e /dev/spidev0.0 ]; then
    echo "  *** Reboot required for SPI: sudo reboot ***"
fi
