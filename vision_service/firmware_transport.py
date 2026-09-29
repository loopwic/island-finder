"""Serial transport scoped to esptool, without changing the controller bridge."""
from __future__ import annotations

import math
import sys
from contextlib import contextmanager

import serial


def _timeout(value: float | None) -> float | None:
    if value is not None and (
        not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
    ):
        raise ValueError(f"Invalid serial timeout: {value!r}")
    return value


class DarwinFirmwareSerial(serial.Serial):
    """pyserial 3.5 select()-based I/O needs no ioctl for software timeouts.

    esptool changes timeouts between commands and for every Flash read packet.
    On macOS, the stock setters reapply the custom baud through IOSSIOSPEED,
    briefly selecting B38400 while bytes are arriving at 460800. That corrupts
    the stream. Keep actual baud/format/reset setters untouched, and only avoid
    hardware reconfiguration for these two select()-managed deadlines.
    This class is instantiated only on Darwin; Windows keeps its native timers.
    """

    @serial.Serial.timeout.setter
    def timeout(self, value: float | None) -> None:
        self._timeout = _timeout(value)

    @serial.Serial.write_timeout.setter
    def write_timeout(self, value: float | None) -> None:
        self._write_timeout = _timeout(value)


@contextmanager
def firmware_port(path: str):
    if sys.platform != "darwin":
        # Let esptool retain its OS-specific open/reset behaviour elsewhere.
        yield path
        return
    with DarwinFirmwareSerial(path, baudrate=115200, timeout=8, write_timeout=10,
                              exclusive=True) as port:
        yield port
