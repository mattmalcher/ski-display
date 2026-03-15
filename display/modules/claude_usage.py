"""Claude API usage module — shows monthly API spend and token usage.

Calls the Anthropic Admin API to fetch current-month cost and token usage,
then displays them on the LED matrix. Limits reset on the 1st of each month.

Requires an Admin API key (starting with sk-ant-admin...) which can be created
in the Anthropic Console by an organisation admin.

Add to config.json:
    {
        "name": "claude_usage",
        "enabled": true,
        "admin_api_key": "sk-ant-admin...",
        "fetch_interval": 300
    }
"""

import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

from modules.base import DisplayModule

logger = logging.getLogger(__name__)

_BASE_URL = 'https://api.anthropic.com'
_ANTHROPIC_VERSION = '2023-06-01'


def _http_get(url: str, api_key: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            'x-api-key': api_key,
            'anthropic-version': _ANTHROPIC_VERSION,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _parse_cost(value) -> float:
    """Parse a cost value that may be a string (cents) or float (dollars)."""
    try:
        # Anthropic reports costs as decimal strings in cents
        return float(value) / 100.0
    except (TypeError, ValueError):
        return 0.0


class Module(DisplayModule):
    def start(self):
        self._api_key = self.config.get('admin_api_key', '')
        self._fetch_interval = float(self.config.get('fetch_interval', 300))
        self._cache = None
        self._lock = threading.Lock()
        self._stop = threading.Event()

        if not self._api_key:
            logger.warning('claude_usage: no admin_api_key configured')
            return

        t = threading.Thread(target=self._fetch_loop, daemon=True)
        t.start()

    def stop(self):
        self._stop.set()

    def get_scenes(self) -> list:
        with self._lock:
            data = self._cache

        if data is None:
            return []

        try:
            scenes = []
            cost_usd = data.get('cost_usd', 0.0)
            input_tokens = data.get('input_tokens', 0)
            output_tokens = data.get('output_tokens', 0)
            reset_label = data.get('reset_label', '')

            # Cost scene: "Claude $1.23 resets 1 Apr"
            cost_text = f'Claude ${cost_usd:.2f}'
            if reset_label:
                cost_text += f' resets {reset_label}'
            scenes.append({
                'type': 'scroll',
                'text': cost_text,
                'speed': 30,
                'ttl': self._fetch_interval * 2,
            })

            # Token scene: "Claude 42k in 8k out"
            total_in = input_tokens // 1000
            total_out = output_tokens // 1000
            if input_tokens or output_tokens:
                tok_text = f'Claude {total_in}k in {total_out}k out'
                scenes.append({
                    'type': 'scroll',
                    'text': tok_text,
                    'speed': 30,
                    'ttl': self._fetch_interval * 2,
                })

            return scenes
        except Exception:
            logger.exception('claude_usage: error building scenes')
            return []

    # ------------------------------------------------------------------
    # Background helpers
    # ------------------------------------------------------------------

    def _fetch_loop(self):
        while not self._stop.is_set():
            try:
                self._fetch_usage()
            except urllib.error.URLError as exc:
                logger.warning('claude_usage: network error: %s', exc)
            except Exception:
                logger.exception('claude_usage: fetch error')
            self._stop.wait(self._fetch_interval)

    def _fetch_usage(self):
        now = datetime.now(timezone.utc)

        # Current month window
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        starting_at = month_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        ending_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Reset is the 1st of next month
        if now.month == 12:
            reset_dt = now.replace(year=now.year + 1, month=1, day=1,
                                   hour=0, minute=0, second=0, microsecond=0)
        else:
            reset_dt = now.replace(month=now.month + 1, day=1,
                                   hour=0, minute=0, second=0, microsecond=0)
        reset_label = reset_dt.strftime('%-d %b')  # e.g. "1 Apr"

        # --- Cost report ---
        cost_url = (
            f'{_BASE_URL}/v1/organizations/cost_report'
            f'?starting_at={starting_at}&ending_at={ending_at}'
        )
        cost_data = _http_get(cost_url, self._api_key)
        total_cost_usd = sum(
            _parse_cost(item.get('cost', 0))
            for item in cost_data.get('data', [])
        )

        # --- Usage report (token counts, bucketed daily) ---
        usage_url = (
            f'{_BASE_URL}/v1/organizations/usage_report/messages'
            f'?starting_at={starting_at}&ending_at={ending_at}&bucket_width=1d'
        )
        usage_data = _http_get(usage_url, self._api_key)
        input_tokens = 0
        output_tokens = 0
        for bucket in usage_data.get('data', []):
            input_tokens += bucket.get('input_tokens', 0)
            output_tokens += bucket.get('output_tokens', 0)

        with self._lock:
            self._cache = {
                'cost_usd': total_cost_usd,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'reset_label': reset_label,
            }

        logger.info(
            'claude_usage: $%.2f this month, %dk in / %dk out tokens, resets %s',
            total_cost_usd, input_tokens // 1000, output_tokens // 1000, reset_label,
        )
