"""Stock ticker module — fetches prices and injects scroll scenes.

Add to config.json:
    {
        "name": "stock",
        "enabled": true,
        "symbols": ["AAPL", "TSLA"],
        "fetch_interval": 300
    }

Requires yfinance: pip install yfinance
"""

import sys
import threading
import time

from modules.base import DisplayModule


class Module(DisplayModule):
    def start(self):
        self._symbols = self.config.get('symbols', [])
        self._fetch_interval = float(self.config.get('fetch_interval', 300))
        self._cache = {}  # symbol -> {'price': float, 'change_pct': float}
        self._stop = threading.Event()

        t = threading.Thread(target=self._fetch_loop, daemon=True)
        t.start()

    def stop(self):
        self._stop.set()

    def get_scenes(self) -> list:
        scenes = []
        for sym in self._symbols:
            data = self._cache.get(sym)
            if data is None:
                continue
            price = data['price']
            change_pct = data['change_pct']
            sign = '+' if change_pct >= 0 else ''
            text = f'{sym} ${price:.2f} {sign}{change_pct:.1f}%'
            anim = 'stock_up' if change_pct >= 0 else 'stock_down'
            scenes.append({
                'type': 'scroll',
                'text': text,
                'animation': anim,
                'speed': 30,
                'ttl': self._fetch_interval * 2,
            })
        return scenes

    def _fetch_loop(self):
        try:
            import yfinance as yf
        except ImportError:
            print('stock module: yfinance not installed (pip install yfinance)', file=sys.stderr)
            return

        while not self._stop.is_set():
            try:
                self._fetch_all(yf)
            except Exception as e:
                print(f'stock module: fetch error: {e}', file=sys.stderr)
            self._stop.wait(self._fetch_interval)

    def _fetch_all(self, yf):
        for sym in self._symbols:
            try:
                info = yf.Ticker(sym).fast_info
                price = info.last_price
                prev_close = info.previous_close
                if price is None or prev_close is None or prev_close == 0:
                    continue
                change_pct = (price - prev_close) / prev_close * 100
                self._cache[sym] = {'price': price, 'change_pct': change_pct}
            except Exception as e:
                print(f'stock module: error fetching {sym}: {e}', file=sys.stderr)
