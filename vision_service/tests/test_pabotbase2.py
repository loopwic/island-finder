from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

import pabotbase2
from controller_server import ControllerHTTPServer
from pabotbase2 import ControllerError, PABotBase2Bridge, protocol_self_test


def test_protocol_vectors_match_the_verified_swift_bridge() -> None:
    assert protocol_self_test() == []


def test_packet_parser_recovers_after_noise_and_rejects_bad_crc() -> None:
    bridge = PABotBase2Bridge()
    bridge.session_id = 0x1234_5678
    corrupted = bytearray(
        bridge.make_packet(6, bridge.STREAM_REPLY, b"", bridge.session_id)
    )
    corrupted[-1] ^= 0xFF
    valid = bridge.make_packet(
        7,
        bridge.STREAM_REPLY,
        b"",
        bridge.session_id,
    )
    bridge.receive_buffer.extend(b"rom log\r\n" + corrupted + valid)

    packet = bridge._pull_packet()

    assert packet is not None
    assert packet.sequence == 7
    assert packet.opcode == bridge.STREAM_REPLY
    assert bridge._pull_packet() is None


def test_stream_message_decoder_tracks_results_and_completed_commands() -> None:
    bridge = PABotBase2Bridge()
    mode_message = bytes([0x08, 0x00, bridge.RETURN_UINT32, 9]) + (
        0x1010
    ).to_bytes(4, "little")
    finished_message = bytes([0x04, 0x00, bridge.COMMAND_FINISHED, 3])
    bridge.message_buffer.extend(mode_message + finished_message)

    bridge._process_messages()

    assert bridge.uint32_responses[9] == 0x1010
    assert 3 in bridge.finished_commands
    assert bridge.message_buffer == bytearray()


def test_serial_port_discovery_prefers_board_like_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ports = [
        SimpleNamespace(
            device="COM4",
            description="Bluetooth Port",
            manufacturer="Microsoft",
            product="",
            hwid="",
        ),
        SimpleNamespace(
            device="COM12",
            description="USB Serial Device",
            manufacturer="Espressif",
            product="ESP32-S3 UART",
            hwid="USB VID:PID=303A:1001",
        ),
    ]
    monkeypatch.setattr(pabotbase2.list_ports, "comports", lambda: ports)
    monkeypatch.setattr(pabotbase2.sys, "platform", "win32")
    monkeypatch.setenv("ISLAND_CONTROLLER_SERIAL_PORT", "COM20")

    assert PABotBase2Bridge().candidate_ports() == ["COM20", "COM12", "COM4"]


def test_macos_serial_discovery_ignores_bluetooth_and_debug_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ports = [
        SimpleNamespace(
            device="/dev/cu.Bluetooth-Incoming-Port",
            description="Bluetooth",
            manufacturer="Apple",
            product="",
            hwid="",
        ),
        SimpleNamespace(
            device="/dev/cu.usbmodemEXAMPLE",
            description="USB device",
            manufacturer="Espressif",
            product="",
            hwid="",
        ),
        SimpleNamespace(
            device="/dev/cu.debug-console",
            description="Debug console",
            manufacturer="Apple",
            product="",
            hwid="",
        ),
    ]
    monkeypatch.setattr(pabotbase2.list_ports, "comports", lambda: ports)
    monkeypatch.setattr(pabotbase2.sys, "platform", "darwin")
    monkeypatch.delenv("ISLAND_CONTROLLER_SERIAL_PORT", raising=False)

    assert PABotBase2Bridge().candidate_ports() == [
        "/dev/cu.usbmodemEXAMPLE"
    ]


def test_unknown_button_is_rejected_without_touching_serial() -> None:
    with pytest.raises(ControllerError, match="不支持的手柄按键"):
        PABotBase2Bridge.state_for("CAPTURE")


def test_cross_platform_http_contract_exposes_status_and_validates_press() -> None:
    bridge = PABotBase2Bridge()
    server = ControllerHTTPServer(("127.0.0.1", 0), bridge)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(f"{base_url}/v1/status", timeout=2) as response:
            status = json.loads(response.read())
        assert status["service"] == "island-controller-service"
        assert status["version"] == "0.5.0"
        assert status["transport"] == "pabotbase2"
        assert status["readyForInput"] is False

        request = urllib.request.Request(
            f"{base_url}/v1/press",
            method="POST",
            data=json.dumps(
                {"type": "press", "button": "A", "hold_ms": 80}
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as captured:
            urllib.request.urlopen(request, timeout=2)
        assert captured.value.code == 409
        assert "尚未进入 NS2" in json.loads(captured.value.read())["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
