from __future__ import annotations

import copy
import threading
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import AutomationEngine, ControllerClient, DEFAULT_SETTINGS, validate_settings
from http_api import create_app


def _dry_run_engine():
    presses: list[str] = []
    controller = ControllerClient(
        lambda kind, message: presses.append(message) if kind == "sent" else None
    )
    controller._request = lambda *_args, **_kwargs: {}  # type: ignore[method-assign]
    controller.set_dry_run(True)
    engine = AutomationEngine(
        lambda: copy.deepcopy(DEFAULT_SETTINGS),
        SimpleNamespace(),  # type: ignore[arg-type]
        controller,
        SimpleNamespace(update=lambda *_args, **_kwargs: {}),  # type: ignore[arg-type]
        lambda _snapshot: None,
        lambda _level, _message: None,
    )
    return engine, controller, presses


def test_stop_keeps_a_running_action_from_pressing_or_reviving_the_run():
    engine, controller, presses = _dry_run_engine()
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def action() -> None:
        try:
            entered.set()
            release.wait(2)  # stands in for OCR work that cannot be interrupted
            controller.press("A")
            engine._patch(phase="fastForwarding")
        finally:
            finished.set()

    engine._patch(phase="fastForwarding")
    assert engine._spawn(action)
    assert entered.wait(2)
    engine.stop()
    release.set()

    assert finished.wait(2)
    assert presses == []
    assert engine.state()["phase"] == "idle"


def test_pause_wakes_an_action_waiting_between_ocr_polls():
    engine, _controller, _presses = _dry_run_engine()
    waiting = threading.Event()
    finished = threading.Event()

    def action() -> None:
        try:
            waiting.set()
            engine._wait(30)
        finally:
            finished.set()

    engine._patch(phase="fastForwarding")
    assert engine._spawn(action)
    assert waiting.wait(2)
    started = time.monotonic()
    engine.pause()

    assert finished.wait(2)
    assert time.monotonic() - started < 1
    assert engine.state()["phase"] == "paused"


def test_resume_returns_a_paused_decision_to_the_user():
    engine, _controller, _presses = _dry_run_engine()
    candidate = {"cardIndex": 1, "score": 0.9}
    engine._patch(phase="awaitingDecision", selectedCandidate=candidate)

    engine.pause()
    engine.resume()

    assert engine.state()["phase"] == "awaitingDecision"
    assert engine.state()["selectedCandidate"] == candidate


def test_birthday_is_clamped_to_the_month_length():
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["identity"].update({"birthMonth": 4, "birthDay": 31})
    settings["birthdayCursorOrigin"] = {"month": 2, "day": 30}

    validated = validate_settings(settings)

    assert validated["identity"]["birthDay"] == 30
    assert validated["birthdayCursorOrigin"]["day"] == 29


def test_other_web_pages_cannot_write_to_the_backend():
    calls: list[str] = []
    runtime = SimpleNamespace(
        action=lambda name, *_args: calls.append(name) or {"ok": True},
        update_settings=lambda payload: calls.append("settings") or payload,
        clear_logs=lambda: calls.append("logs"),
    )
    client = TestClient(create_app(runtime))  # type: ignore[arg-type]
    foreign = {"Origin": "https://evil.example"}

    assert client.post("/v1/actions/accept", headers=foreign).status_code == 403
    assert client.post(
        "/v1/settings",
        content='{"dryRun": false}',
        headers={**foreign, "Content-Type": "text/plain"},
    ).status_code == 403
    assert client.post("/v1/logs/clear", headers=foreign).status_code == 403
    assert calls == []

    assert client.post("/v1/actions/stop", headers={"Origin": "http://127.0.0.1:4173"}).status_code == 200
    assert client.post("/v1/actions/stop").status_code == 200
    assert calls == ["stop", "stop"]
