from __future__ import annotations

import os
import threading

import pytest

import runtime_supervisor


@pytest.mark.parametrize("payload", [b"", b"shutdown\n"])
def test_stdin_watcher_stops_runtime_on_parent_close_or_command(payload: bytes):
    read_fd, write_fd = os.pipe()
    stop_event = threading.Event()
    try:
        if payload:
            os.write(write_fd, payload)
        os.close(write_fd)
        write_fd = -1

        runtime_supervisor._watch_stdin(read_fd, stop_event)

        assert stop_event.is_set()
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)


def test_cleanup_refuses_runtime_from_another_checkout(monkeypatch: pytest.MonkeyPatch):
    requests: list[tuple[str, str]] = []
    monkeypatch.setattr(runtime_supervisor, "_port_is_open", lambda _port: True)

    def request(url: str, *, method: str = "GET", timeout: float = 0.8):
        requests.append((method, url))
        return {
            "service": runtime_supervisor.RUNTIME_SERVICE,
            "projectRoot": "/another/island-finder",
        }

    monkeypatch.setattr(runtime_supervisor, "_request_json", request)

    with pytest.raises(RuntimeError, match="不属于当前 Island Finder 项目"):
        runtime_supervisor._cleanup_previous_runtime()

    assert requests == [("GET", "http://127.0.0.1:32146/health")]


def test_cleanup_only_stops_verified_current_runtime(monkeypatch: pytest.MonkeyPatch):
    requests: list[tuple[str, str]] = []
    port_checks = iter([True, False])
    monkeypatch.setattr(runtime_supervisor, "_port_is_open", lambda _port: next(port_checks))

    def request(url: str, *, method: str = "GET", timeout: float = 0.8):
        requests.append((method, url))
        return {
            "service": runtime_supervisor.RUNTIME_SERVICE,
            "projectRoot": str(runtime_supervisor.PROJECT_ROOT),
        }

    monkeypatch.setattr(runtime_supervisor, "_request_json", request)

    runtime_supervisor._cleanup_previous_runtime()

    assert requests == [
        ("GET", "http://127.0.0.1:32146/health"),
        ("POST", "http://127.0.0.1:32146/shutdown"),
    ]
