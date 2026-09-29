from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import firmware_service
from firmware_api import install_firmware_routes
from firmware_service import FirmwareService
from test_firmware import FILENAME, PORTS, firmware_bytes


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(firmware_service, "serial_ports", lambda: PORTS)
    service = FirmwareService(tmp_path, lambda *_: pytest.fail("must not access hardware"))
    runtime = SimpleNamespace(instance_id="session", firmware=service, _action_lock=threading.RLock(),
                              engine=SimpleNamespace(state=lambda: {"phase": "idle"}, busy=False))
    app = FastAPI()
    install_firmware_routes(app, runtime, {"http://localhost:4173"})
    return TestClient(app), runtime


HEADERS = {"X-Island-Finder-Instance": "session", "Origin": "http://localhost:4173"}


def test_upload_and_prepare_need_current_session_and_trusted_origin(harness):
    client, runtime = harness
    for headers in ({}, {**HEADERS, "Origin": "https://evil.example"},
                    {**HEADERS, "X-Island-Finder-Instance": "old"}):
        response = client.post(f"/v1/firmware/image?filename={FILENAME}", content=firmware_bytes(), headers=headers)
        assert response.status_code == 400
        assert runtime.firmware.status()["image"]["source"] == "bundled"
    assert client.get("/v1/firmware/ports", headers=HEADERS).json()["ports"] == PORTS
    uploaded = client.post(f"/v1/firmware/image?filename={FILENAME}", content=firmware_bytes(), headers=HEADERS)
    assert uploaded.status_code == 200
    prepared = client.post("/v1/firmware/prepare", json={"port": "COM12"}, headers=HEADERS)
    assert prepared.status_code == 200
    assert prepared.json()["image"]["sha256"] == uploaded.json()["sha256"]


@pytest.mark.parametrize("phase", ["paused", "restarting", "scanning", "awaitingDecision", "error"])
def test_non_idle_automation_cannot_prepare_or_flash(harness, phase):
    client, runtime = harness
    runtime.engine.state = lambda: {"phase": phase}
    for operation in ("prepare", "flash"):
        response = client.post(f"/v1/firmware/{operation}", json={"port": "COM12"}, headers=HEADERS)
        assert response.status_code == 400
        assert "先停止" in response.json()["error"]


def test_flash_requires_explicit_ack_and_validates_json(harness):
    client, runtime = harness
    runtime.firmware.upload(firmware_bytes(), FILENAME)
    token = runtime.firmware.prepare("COM12")["confirmationToken"]
    response = client.post("/v1/firmware/flash", json={"confirmationToken": token, "baud": 460800}, headers=HEADERS)
    assert response.status_code == 400
    for body in (b"[]", b"bad-json", b"x" * 4097):
        assert client.post("/v1/firmware/flash", content=body, headers=HEADERS).status_code == 400
    assert runtime.firmware.busy is False


@pytest.mark.parametrize("backup_requested", [None, "false", 0, [], {}])
def test_backup_choice_requires_real_boolean(harness, backup_requested):
    client, runtime = harness
    token = runtime.firmware.prepare("COM12")["confirmationToken"]
    response = client.post("/v1/firmware/flash", headers=HEADERS, json={
        "confirmationToken": token, "baud": 460800, "acknowledged": True,
        "backupRequested": backup_requested,
    })
    assert response.status_code == 400
    assert runtime.firmware.busy is False


def test_streaming_upload_is_bounded(harness, monkeypatch):
    import firmware_api
    client, runtime = harness
    monkeypatch.setattr(firmware_api, "MAX_FIRMWARE_BYTES", 10)
    response = client.post(f"/v1/firmware/image?filename={FILENAME}", content=b"x" * 11, headers=HEADERS)
    assert response.status_code == 400
    assert runtime.firmware.status()["image"]["source"] == "bundled"


def test_bundled_image_is_ready_without_upload_and_can_be_reselected(harness):
    client, runtime = harness
    image = client.get("/v1/firmware/status").json()["image"]
    assert image["source"] == "bundled" and image["release"] == "2026090200"
    prepared = client.post("/v1/firmware/prepare", json={"port": "COM12"}, headers=HEADERS)
    assert prepared.status_code == 200
    assert prepared.json()["image"] == image
    runtime.firmware.upload(firmware_bytes(), FILENAME)
    assert client.post("/v1/firmware/bundled", json={}).status_code == 400
    assert client.post("/v1/firmware/bundled", json={}, headers=HEADERS).json() == image
    assert runtime.firmware.busy is False


def test_close_guard_and_progress_recover_without_starting_another_job(harness):
    client, runtime = harness
    assert client.get("/v1/firmware/close-guard").text == "idle"
    runtime.firmware._state.update(busy=True, stage="writing", jobId="same-job")
    assert client.get("/v1/firmware/close-guard").text == "busy"
    for _ in range(3):
        assert client.get("/v1/firmware/status").json()["jobId"] == "same-job"
        assert client.post("/v1/firmware/flash", json={}, headers=HEADERS).status_code == 400


def test_backup_progress_survives_status_refresh_without_hardware_access(harness):
    client, runtime = harness
    runtime.firmware._update(busy=True, stage="backing_up", jobId="same-backup",
                             bytesRead=1048576, totalBytes=16777216, percent=6.25,
                             bytesPerSecond=42000, estimatedSeconds=374)
    for _ in range(2):
        state = client.get("/v1/firmware/status").json()
        assert state["percent"] == 6.25 and state["bytesRead"] == 1048576
        assert state["bytesPerSecond"] == 42000 and state["jobId"] == "same-backup"
