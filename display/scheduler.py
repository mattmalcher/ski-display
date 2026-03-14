"""Scene scheduler — collects scenes from all active modules.

The scheduler is the glue between independent modules and the main render loop:
  - Calls each module's get_scenes() on a configurable interval
  - Stamps scenes with a collection timestamp (for TTL enforcement)
  - Filters out stale scenes (scene['ttl'] exceeded)
  - Expands scenes by priority (priority=2 → scene appears twice per cycle)
  - Wraps every module call in try/except so one broken module can't crash the loop

Usage in main loop:
    scheduler = SceneScheduler(modules, refresh_interval=5.0)
    scheduler.start()
    ...
    if scheduler.maybe_refresh(time.monotonic()):
        si = 0          # reset scene index on list change
    scene = scheduler[si]
"""

import time
import logging

logger = logging.getLogger(__name__)

_FALLBACK = [{'type': 'static', 'text': 'NO DATA', 'duration': 3.0}]


class SceneScheduler:
    def __init__(self, modules: list, refresh_interval: float = 5.0):
        self._modules = modules
        self.refresh_interval = refresh_interval
        self._scenes: list = list(_FALLBACK)
        self._last_refresh = 0.0

    def start(self) -> None:
        """Start all modules and perform the initial scene collection."""
        for m in self._modules:
            try:
                m.start()
            except Exception:
                logger.exception('Failed to start module %s', type(m).__name__)
        self._rebuild()

    def stop(self) -> None:
        """Stop all modules (best-effort)."""
        for m in self._modules:
            try:
                m.stop()
            except Exception:
                logger.exception('Failed to stop module %s', type(m).__name__)

    def maybe_refresh(self, now: float) -> bool:
        """Refresh the scene list if the interval has elapsed.

        Returns True if the scene list changed (caller should reset scene index).
        """
        if now - self._last_refresh < self.refresh_interval:
            return False
        old_len = len(self._scenes)
        self._rebuild()
        # Consider changed if length differs — simple heuristic, avoids deep compare
        return len(self._scenes) != old_len

    def __len__(self) -> int:
        return len(self._scenes)

    def __getitem__(self, i: int) -> dict:
        if not self._scenes:
            return _FALLBACK[0]
        return self._scenes[i % len(self._scenes)]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        now = time.monotonic()
        collected: list = []

        for m in self._modules:
            try:
                scenes = m.get_scenes()
            except Exception:
                logger.exception('Module %s raised in get_scenes()', type(m).__name__)
                scenes = []

            if not scenes:
                continue

            for scene in scenes:
                # Stamp with collection time if not already set
                if 'fetched_at' not in scene:
                    scene = dict(scene)  # don't mutate the module's copy
                    scene['fetched_at'] = now

                # TTL check — skip stale scenes
                ttl = scene.get('ttl')
                if ttl is not None and now - scene['fetched_at'] > ttl:
                    continue

                # Priority expansion — repeat scene in rotation
                priority = max(1, int(scene.get('priority', 1)))
                for _ in range(priority):
                    collected.append(scene)

        self._scenes = collected if collected else list(_FALLBACK)
        self._last_refresh = now
        logger.debug('Scheduler rebuilt: %d scenes from %d modules',
                     len(self._scenes), len(self._modules))
