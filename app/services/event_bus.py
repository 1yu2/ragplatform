from __future__ import annotations

import threading
from collections import defaultdict


class TaskEventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, list[str]] = defaultdict(list)

    def append(self, task_id: str, state: str) -> None:
        with self._lock:
            self._events[task_id].append(state)

    def get(self, task_id: str) -> list[str]:
        with self._lock:
            return list(self._events.get(task_id, []))


EVENT_BUS = TaskEventBus()
