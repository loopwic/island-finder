from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import firmware_transport
from firmware_transport import DarwinFirmwareSerial, firmware_port


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin select-based serial implementation")
def test_timeout_updates_never_reapply_baud_but_line_settings_still_do(monkeypatch):
    port = DarwinFirmwareSerial(port=None, timeout=8, write_timeout=10)
    changes = []
    monkeypatch.setattr(port, "_reconfigure_port", lambda: changes.append(port.baudrate))
    port.is_open = True
    try:
        # esptool repeatedly sets these while the device is already streaming.
        for timeout in (3, 8, 3, 3, 0, None):
            port.timeout = timeout
            assert port.timeout == timeout
        port.write_timeout = 20
        assert port.write_timeout == 20
        assert changes == []
        port.baudrate = 460800
        port.bytesize = 7
        assert changes == [460800, 460800]
    finally:
        port.is_open = False


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), "3"])
def test_invalid_software_timeout_does_not_replace_previous_value(value):
    port = DarwinFirmwareSerial(port=None, timeout=8, write_timeout=10)
    with pytest.raises(ValueError): port.timeout = value
    with pytest.raises(ValueError): port.write_timeout = value
    assert (port.timeout, port.write_timeout) == (8, 10)


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_other_platforms_keep_esptool_native_port_opening(monkeypatch, platform):
    monkeypatch.setattr(firmware_transport, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(firmware_transport, "DarwinFirmwareSerial",
                        lambda *_args, **_kwargs: pytest.fail("must not use Darwin transport"))
    with firmware_port("test-port") as connection:
        assert connection == "test-port"


def test_darwin_port_is_exclusive_bounded_and_closed_on_connection_failure(monkeypatch):
    calls = []
    class Port:
        def __init__(self, path, **settings):
            assert path == "test-port"
            assert settings == {"baudrate": 115200, "timeout": 8, "write_timeout": 10, "exclusive": True}
        def __enter__(self): return self
        def __exit__(self, *_): calls.append("closed")
    monkeypatch.setattr(firmware_transport, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(firmware_transport, "DarwinFirmwareSerial", Port)
    with pytest.raises(RuntimeError):
        with firmware_port("test-port"):
            raise RuntimeError("no chip response")
    assert calls == ["closed"]
