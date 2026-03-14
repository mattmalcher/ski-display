"""Base class for all display modules.

Each module provides a list of scenes to be displayed in rotation.
Modules are independent — a crash or error in one does not affect others.

To create a new module:
  1. Create display/modules/yourmodule.py
  2. Define a class named ``Module`` that subclasses ``DisplayModule``
  3. Implement ``get_scenes()``
  4. Enable it in config.json

Scene dict keys:
    type       (str)   Required. 'static' | 'scroll' | 'clock'
    text       (str)   Required for static/scroll.
    duration   (float) Required for static/clock. Seconds to display.
    speed      (int)   Required for scroll. Pixels per second (default 36).
    icon       (str)   Optional. Icon name from icons.py.
    animation  (str)   Optional. Animation name from animations.py (takes precedence over icon).
    anim_fps   (int)   Optional. Animation frames per second (default 4).
    transition (str)   Optional. Specific transition name to use entering this scene.
    ttl        (float) Optional. Seconds after collection before this scene is considered stale.
    priority   (int)   Optional. Repeat count in the rotation (default 1). Higher = more frequent.
"""

import abc
import logging

logger = logging.getLogger(__name__)


class DisplayModule(abc.ABC):
    """Abstract base class for display modules."""

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get('enabled', True)

    def start(self) -> None:
        """Called once at startup. Override to launch background threads."""
        pass

    @abc.abstractmethod
    def get_scenes(self) -> list:
        """Return current list of scene dicts.

        This method MUST NOT raise — catch all exceptions internally and return
        whatever partial data is available, or an empty list.  An empty return
        value causes this module to be silently skipped for the current cycle.
        """
        ...

    def stop(self) -> None:
        """Called on shutdown. Override to clean up threads or connections."""
        pass
