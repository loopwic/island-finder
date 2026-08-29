from __future__ import annotations

import parent_watch


def test_parent_pid_is_optional_and_validated():
    assert parent_watch.configured_parent_pid({}) is None
    assert parent_watch.configured_parent_pid({parent_watch.SUPERVISOR_PID_ENV: "bad"}) is None
    assert parent_watch.configured_parent_pid({parent_watch.SUPERVISOR_PID_ENV: "1"}) is None
    assert parent_watch.configured_parent_pid({parent_watch.SUPERVISOR_PID_ENV: "1234"}) == 1234


def test_parent_must_still_be_the_direct_parent(monkeypatch):
    monkeypatch.setattr(parent_watch.os, "getppid", lambda: 55)
    assert not parent_watch.parent_is_alive(99)


def test_live_direct_parent_is_accepted(monkeypatch):
    probes: list[tuple[int, int]] = []
    monkeypatch.setattr(parent_watch.os, "getppid", lambda: 99)
    monkeypatch.setattr(parent_watch.os, "kill", lambda pid, signal: probes.append((pid, signal)))

    assert parent_watch.parent_is_alive(99)
    assert probes == [(99, 0)]
