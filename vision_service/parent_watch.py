from __future__ import annotations

import os
import threading
from collections.abc import Callable, Mapping


SUPERVISOR_PID_ENV = "ISLAND_FINDER_SUPERVISOR_PID"


def configured_parent_pid(environment: Mapping[str, str] | None = None) -> int | None:
    source = os.environ if environment is None else environment
    value = source.get(SUPERVISOR_PID_ENV, "").strip()
    if not value:
        return None
    try:
        parent_pid = int(value)
    except ValueError:
        return None
    return parent_pid if parent_pid > 1 else None


def parent_is_alive(parent_pid: int) -> bool:
    if os.getppid() != parent_pid:
        return False
    try:
        os.kill(parent_pid, 0)
    except OSError:
        return False
    return True


def start_parent_watch(
    request_shutdown: Callable[[], None],
    *,
    parent_pid: int | None = None,
    interval: float = 0.5,
) -> threading.Thread | None:
    expected_parent = parent_pid if parent_pid is not None else configured_parent_pid()
    if expected_parent is None:
        return None
    waiter = threading.Event()

    def watch() -> None:
        while parent_is_alive(expected_parent):
            waiter.wait(interval)
        request_shutdown()

    thread = threading.Thread(
        target=watch,
        name="island-finder-parent-watch",
        daemon=True,
    )
    thread.start()
    return thread
