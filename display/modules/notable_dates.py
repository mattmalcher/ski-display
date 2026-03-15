"""Notable dates module — shows messages on specific dates and reminder countdowns.

Add to config.json:
    {
        "name": "notable_dates",
        "enabled": true,
        "dates": [
            {
                "date": "2026-12-25",
                "message": "Merry Christmas!",
                "repeat": "annual",
                "reminder_days": [7, 3, 1]
            },
            {
                "date": "2026-06-15",
                "message": "Summer hols begin",
                "repeat": "none",
                "reminder_days": [14, 7]
            },
            {
                "date": "2026-03-19",
                "message": "Recycling bins",
                "repeat": "weekly",
                "interval_weeks": 2,
                "reminder_days": [1]
            }
        ]
    }

repeat modes:
    "none"    — one-off date (YYYY-MM-DD); silently ignored once the date has passed
    "annual"  — same month/day every year; year in the date field is ignored
    "weekly"  — every N weeks anchored to the given date; use interval_weeks (default 1)

reminder_days:
    List of integers. A reminder scene is shown when days_until == N for each N in the list.
    Set to [] for no reminders (show on the day only).
"""

import datetime
import logging

from modules.base import DisplayModule

logger = logging.getLogger(__name__)

# Rough per-character pixel width for the 5×7 font (5px glyph + 1px gap).
_CHAR_WIDTH = 6
# Icon width (8px) plus a 1px gap.
_ICON_WIDTH = 9


class Module(DisplayModule):
    def start(self):
        self._dates = self.config.get('dates', [])

    def get_scenes(self) -> list:
        today = datetime.date.today()
        scenes = []
        for entry in self._dates:
            try:
                scenes.extend(self._scenes_for_entry(entry, today))
            except Exception as exc:
                logger.warning('notable_dates: skipping entry %r: %s', entry, exc)
        return scenes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scenes_for_entry(self, entry: dict, today: datetime.date) -> list:
        raw_date = entry.get('date', '')
        message = entry.get('message', '').strip()
        repeat = entry.get('repeat', 'none')
        reminder_days = entry.get('reminder_days', [])

        if not raw_date or not message:
            return []

        try:
            anchor = datetime.date.fromisoformat(raw_date)
        except ValueError:
            logger.warning('notable_dates: invalid date %r', raw_date)
            return []

        if repeat == 'annual':
            return self._annual_scenes(anchor, message, reminder_days, today)
        elif repeat == 'weekly':
            interval_weeks = int(entry.get('interval_weeks', 1))
            return self._weekly_scenes(anchor, message, reminder_days, interval_weeks, today)
        else:  # "none" or anything unrecognised
            return self._onetime_scenes(anchor, message, reminder_days, today)

    def _onetime_scenes(self, date: datetime.date, message: str,
                        reminder_days: list, today: datetime.date) -> list:
        days_until = (date - today).days
        if days_until < 0:
            return []
        return self._emit(days_until, message, reminder_days)

    def _annual_scenes(self, anchor: datetime.date, message: str,
                       reminder_days: list, today: datetime.date) -> list:
        # Try this year first, then next year if already past.
        for year in (today.year, today.year + 1):
            try:
                target = anchor.replace(year=year)
            except ValueError:
                # 29 Feb in a non-leap year — skip to next year
                continue
            days_until = (target - today).days
            if days_until >= 0:
                return self._emit(days_until, message, reminder_days)
        return []

    def _weekly_scenes(self, anchor: datetime.date, message: str,
                       reminder_days: list, interval_weeks: int,
                       today: datetime.date) -> list:
        cycle = interval_weeks * 7
        # Python's modulo always returns non-negative for positive divisor.
        offset = (today - anchor).days % cycle
        days_until = (cycle - offset) % cycle  # 0 if today is an occurrence day
        return self._emit(days_until, message, reminder_days)

    def _emit(self, days_until: int, message: str, reminder_days: list) -> list:
        if days_until == 0:
            return [self._make_scene(message)]
        if days_until in reminder_days:
            label = f'{days_until}d: {message}'
            return [self._make_scene(label)]
        return []

    def _make_scene(self, text: str) -> dict:
        # Estimate rendered width: icon + text.
        pixel_width = _ICON_WIDTH + len(text) * _CHAR_WIDTH
        if pixel_width > 32:
            return {
                'type': 'scroll',
                'text': text,
                'icon': 'clock',
                'speed': 30,
            }
        return {
            'type': 'static',
            'text': text,
            'icon': 'clock',
            'duration': 5.0,
        }
