"""Claude.ai subscription usage module — shows message limit utilisation.

Calls the claude.ai internal usage API to fetch current utilisation for
the 5-hour and 7-day rolling windows, and when each resets.

Add to config.json:
    {
        "name": "claude_usage",
        "enabled": true,
        "session_key": "sk-ant-sid01-...",
        "org_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "fetch_interval": 120
    }

--- Finding your session_key ---

1. Log in to claude.ai in your browser
2. Open DevTools (F12) → Application tab → Storage → Cookies → https://claude.ai
3. Find the cookie named 'sessionKey' and copy its value (starts with sk-ant-sid01-)
4. Paste it into config.json as 'session_key'

The cookie expires roughly every 30 days. When it does the module logs:
    "claude_usage: session expired — update session_key in config"
and silently produces no scenes until you refresh it using the steps above.

--- Finding your org_id ---

Log in to claude.ai and look at the URL when you open any conversation or
visit settings — it contains your org UUID, e.g.:
    https://claude.ai/settings/usage
Then check the network request to /api/organizations/<org_id>/usage in
DevTools → Network, or look at the URL bar after navigating to a conversation.
"""

import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

from modules.base import DisplayModule

logger = logging.getLogger(__name__)

_USAGE_URL = 'https://claude.ai/api/organizations/{org_id}/usage'
_USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0'
)


def _fmt_reset(iso: str) -> str:
    """Format a reset timestamp for display.

    Uses HH:MM for resets within 24 hours, otherwise '%-d %b' (e.g. '21 Mar').
    """
    try:
        dt = datetime.fromisoformat(iso).astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        delta = dt - now
        if delta.total_seconds() < 86400:
            return dt.strftime('%H:%M')
        return dt.strftime('%-d %b')
    except Exception:
        return ''


class Module(DisplayModule):
    def start(self):
        self._session_key = self.config.get('session_key', '')
        self._org_id = self.config.get('org_id', '')
        self._fetch_interval = float(self.config.get('fetch_interval', 120))
        self._cache = None
        self._lock = threading.Lock()
        self._stop = threading.Event()

        if not self._session_key or not self._org_id:
            logger.warning('claude_usage: session_key and org_id are required')
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

            five_h = data.get('five_hour') or {}
            seven_d = data.get('seven_day') or {}

            if five_h.get('utilization') is not None:
                pct = five_h['utilization']
                reset = _fmt_reset(five_h.get('resets_at', ''))
                text = f'Claude 5h {pct:.0f}%'
                if reset:
                    text += f' resets {reset}'
                scenes.append({
                    'type': 'scroll',
                    'text': text,
                    'speed': 30,
                    'ttl': self._fetch_interval * 3,
                })

            if seven_d.get('utilization') is not None:
                pct = seven_d['utilization']
                reset = _fmt_reset(seven_d.get('resets_at', ''))
                text = f'Claude 7d {pct:.0f}%'
                if reset:
                    text += f' resets {reset}'
                scenes.append({
                    'type': 'scroll',
                    'text': text,
                    'speed': 30,
                    'ttl': self._fetch_interval * 3,
                })

            extra = data.get('extra_usage') or {}
            if extra.get('is_enabled') and extra.get('monthly_limit'):
                used = extra.get('used_credits', 0) or 0
                limit = extra['monthly_limit']
                text = f'Claude extra {used:.0f}/{limit} credits'
                scenes.append({
                    'type': 'scroll',
                    'text': text,
                    'speed': 30,
                    'ttl': self._fetch_interval * 3,
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
            except urllib.error.HTTPError as exc:
                if exc.code == 401:
                    logger.error(
                        'claude_usage: session expired — update session_key in config'
                    )
                else:
                    logger.warning('claude_usage: HTTP %d', exc.code)
            except urllib.error.URLError as exc:
                logger.warning('claude_usage: network error: %s', exc)
            except Exception:
                logger.exception('claude_usage: fetch error')
            self._stop.wait(self._fetch_interval)

    def _fetch_usage(self):
        url = _USAGE_URL.format(org_id=self._org_id)
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': _USER_AGENT,
                'Accept': '*/*',
                'Accept-Language': 'en-GB,en;q=0.9',
                'Referer': 'https://claude.ai/settings/usage',
                'anthropic-client-platform': 'web_claude_ai',
                'Cookie': f'sessionKey={self._session_key}',
                'DNT': '1',
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode())

        with self._lock:
            self._cache = payload

        five_h = payload.get('five_hour') or {}
        seven_d = payload.get('seven_day') or {}
        logger.info(
            'claude_usage: 5h=%.0f%% 7d=%.0f%%',
            five_h.get('utilization', 0),
            seven_d.get('utilization', 0),
        )
