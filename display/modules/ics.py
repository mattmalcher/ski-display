"""ICS / iCal Calendar module — shows upcoming events fetched from any iCal URL.

No OAuth required. Obtain your ICS feed URL from your calendar provider:

  Google Calendar:
    Settings → (select calendar) → Integrate calendar
    → "Secret address in iCal format"

  Outlook / Hotmail (outlook.live.com):
    Settings (gear) → View all Outlook settings → Calendar → Shared calendars
    → Publish a calendar → copy the ICS link

  Apple iCloud:
    Calendar app → right-click calendar → Share Calendar → Public Calendar
    → copy the link (change webcal:// to https://)

Add to config.json:
    {
        "name": "ics",
        "enabled": true,
        "ical_url": "https://...",
        "days_ahead": 7,
        "fetch_interval": 900
    }

Options:
    ical_url       — iCal feed URL (required).
    days_ahead     — how many days into the future to show events (default 7).
    fetch_interval — seconds between fetches (default 900 = 15 min).

Requires: icalendar, recurring-ical-events
    pip install icalendar recurring-ical-events
"""

from __future__ import annotations

import logging
import threading
import urllib.request
from datetime import date, datetime, timedelta

from modules.base import DisplayModule

logger = logging.getLogger(__name__)

# Rough per-character pixel width for the 5×7 font (5px glyph + 1px gap).
_CHAR_WIDTH = 6
# Icon width (8px) plus a 1px gap.
_ICON_WIDTH = 9

try:
    import icalendar
    import recurring_ical_events
    _DEPS_OK = True
except ImportError:
    _DEPS_OK = False


class Module(DisplayModule):
    def start(self):
        self._ical_url: str = self.config.get('ical_url', '')
        self._days_ahead: int = int(self.config.get('days_ahead', 7))
        self._fetch_interval: float = float(self.config.get('fetch_interval', 900))
        self._cache: list = []
        self._lock = threading.Lock()
        self._stop = threading.Event()

        if not _DEPS_OK:
            logger.error(
                'ics: icalendar and/or recurring-ical-events not installed '
                '(pip install icalendar recurring-ical-events)'
            )
            return

        if not self._ical_url:
            logger.warning('ics: no ical_url configured, module inactive')
            return

        t = threading.Thread(target=self._fetch_loop, daemon=True)
        t.start()

    def stop(self):
        self._stop.set()

    def get_scenes(self) -> list:
        with self._lock:
            return list(self._cache)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_loop(self):
        while not self._stop.is_set():
            try:
                self._fetch()
            except Exception:
                logger.exception('ics: fetch error')
            self._stop.wait(self._fetch_interval)

    def _fetch(self):
        with urllib.request.urlopen(self._ical_url, timeout=15) as resp:
            data = resp.read()

        cal = icalendar.Calendar.from_ical(data)
        today = date.today()
        now = datetime.now()
        end = today + timedelta(days=self._days_ahead)

        occurrences = recurring_ical_events.of(cal).between(
            datetime(today.year, today.month, today.day, 0, 0, 0),
            datetime(end.year, end.month, end.day, 23, 59, 59),
        )

        scenes = []
        for event in sorted(occurrences, key=_sort_key):
            try:
                scene = self._event_to_scene(event, today, now)
                if scene:
                    scenes.append(scene)
            except Exception:
                logger.exception('ics: error processing event %r', event.get('SUMMARY'))

        with self._lock:
            self._cache = scenes

    def _event_to_scene(self, event, today: date, now: datetime) -> dict | None:
        summary = str(event.get('SUMMARY', 'Event')).strip()
        if not summary:
            return None

        dtstart = event.get('DTSTART')
        if dtstart is None:
            return None
        val = dtstart.dt

        is_all_day = isinstance(val, date) and not isinstance(val, datetime)

        if is_all_day:
            days_until = (val - today).days
            if days_until < 0:
                return None
            if days_until == 0:
                text, priority = summary, 2
            elif days_until == 1:
                text, priority = f'{summary} tmrw', 1
            else:
                text, priority = f'{summary} in {days_until}d', 1
        else:
            if hasattr(val, 'tzinfo') and val.tzinfo is not None:
                event_dt = val.astimezone().replace(tzinfo=None)
            else:
                event_dt = val

            dtend = event.get('DTEND')
            if dtend is not None:
                end_val = dtend.dt
                if isinstance(end_val, datetime):
                    if hasattr(end_val, 'tzinfo') and end_val.tzinfo is not None:
                        end_val = end_val.astimezone().replace(tzinfo=None)
                    if end_val <= now:
                        return None

            days_until = (event_dt.date() - today).days
            if days_until < 0:
                return None

            time_str = event_dt.strftime('%-H:%M')
            if days_until == 0:
                text, priority = f'{summary} {time_str}', 2
            elif days_until == 1:
                text, priority = f'{summary} tmrw {time_str}', 1
            else:
                text, priority = f'{summary} in {days_until}d', 1

        return _make_scene(text, priority, self._fetch_interval)


def _sort_key(event) -> datetime:
    dtstart = event.get('DTSTART')
    if dtstart is None:
        return datetime.max
    val = dtstart.dt
    if isinstance(val, datetime):
        if val.tzinfo is not None:
            return val.astimezone().replace(tzinfo=None)
        return val
    return datetime(val.year, val.month, val.day)


def _make_scene(text: str, priority: int, fetch_interval: float) -> dict:
    pixel_width = _ICON_WIDTH + len(text) * _CHAR_WIDTH
    base = {
        'icon': 'clock',
        'text': text,
        'priority': priority,
        'ttl': fetch_interval * 2,
    }
    if pixel_width > 32:
        return {**base, 'type': 'scroll', 'speed': 30}
    return {**base, 'type': 'static', 'duration': 5.0}
