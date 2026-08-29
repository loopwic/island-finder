from __future__ import annotations

import os
import secrets
import struct
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import serial
from serial.tools import list_ports


class ControllerError(RuntimeError):
    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


class SerialLike(Protocol):
    @property
    def in_waiting(self) -> int: ...

    @property
    def is_open(self) -> bool: ...

    def read(self, size: int = 1) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def flush(self) -> None: ...

    def reset_input_buffer(self) -> None: ...

    def reset_output_buffer(self) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class Packet:
    sequence: int
    opcode: int
    payload: bytes


class PABotBase2Bridge:
    """Cross-platform PABotBase2 serial bridge for macOS and Windows.

    The ESP32-S3 firmware and its USB/OTG connection to Switch 2 stay exactly
    the same.  Only the host-side UART/COM transport moved from Darwin-specific
    Swift code to pyserial.
    """

    MAGIC = 0x81
    SERIAL_BAUD = 921_600
    NS2_WIRED_CONTROLLER_ID = 0x1010

    RESET = 0x01
    RESET_REPLY = 0x41
    STREAM = 0x12
    STREAM_REPLY = 0x52

    RETURN_UINT32 = 0x12
    RETURN_UINT32_DATA = 0x14
    REQUEST_STATUS = 0x31
    READ_CONTROLLER_MODE = 0x32
    CHANGE_CONTROLLER_MODE = 0x33
    COMMAND_DROPPED = 0x40
    CANCEL_QUEUE = 0x41
    COMMAND_FINISHED = 0x43
    WIRED_CONTROLLER_STATE = 0x90

    NEUTRAL_STATE = bytes([0x00, 0x00, 0x08, 0x80, 0x80, 0x80, 0x80])
    BUTTONS = {
        "Y": (0, 1 << 0),
        "B": (0, 1 << 1),
        "A": (0, 1 << 2),
        "X": (0, 1 << 3),
        "L": (0, 1 << 4),
        "R": (0, 1 << 5),
        "MINUS": (1, 1 << 0),
        "PLUS": (1, 1 << 1),
        "HOME": (1, 1 << 4),
    }
    DPAD = {"UP": 0, "RIGHT": 2, "DOWN": 4, "LEFT": 6}

    def __init__(
        self,
        serial_factory: Callable[..., SerialLike] = serial.Serial,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._serial_factory = serial_factory
        self._sleep = sleep
        self._serial: SerialLike | None = None
        self._lock = threading.RLock()

        self.port_path: str | None = None
        self.diagnostic = "尚未连接 PABotBase2 开发板"
        self.controller_mode = 0
        self.console_connected = False

        self.session_id = 0
        self.transmit_sequence = 0
        self.transmit_stream_offset = 0
        self.receive_stream_offset = 0
        self.request_id = 1
        self.command_id = 0
        self.receive_buffer = bytearray()
        self.message_buffer = bytearray()
        self.reset_replies: set[int] = set()
        self.stream_replies: set[int] = set()
        self.uint32_responses: dict[int, int] = {}
        self.uint32_data_responses: dict[int, tuple[int, bytes]] = {}
        self.finished_commands: set[int] = set()
        self.dropped_commands: set[int] = set()

    @property
    def active(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    @property
    def ready_for_input(self) -> bool:
        return self.active and self.controller_mode == self.NS2_WIRED_CONTROLLER_ID

    def status(self) -> dict[str, Any]:
        with self._lock:
            self.refresh()
            platform_name = {
                "darwin": "macOS",
                "win32": "Windows",
            }.get(sys.platform, sys.platform)
            return {
                "service": "island-controller-service",
                "version": "0.5.0",
                "platform": platform_name,
                "bluetoothPowered": False,
                "privateAPIAvailable": False,
                "pairingActive": self.active,
                "consoleConnected": self.console_connected,
                "readyForInput": self.ready_for_input,
                "pairingRecordStored": False,
                "diagnostic": self.diagnostic,
                "transport": "pabotbase2",
                "serialPort": self.port_path,
            }

    def start(self) -> None:
        with self._lock:
            if self.ready_for_input:
                return
            self._stop_without_sending()
            candidates = self.candidate_ports()
            if not candidates:
                raise ControllerError(
                    "未发现开发板 UART/COM 串口；请把电脑数据线接到开发板的 UART/COM 口"
                )

            failures: list[str] = []
            for path in candidates:
                try:
                    self._open(path)
                    self._begin_session()
                    self._change_controller_mode(self.NS2_WIRED_CONTROLLER_ID)
                    self._sleep(0.20)
                    mode = self._query_controller_mode()
                    if mode != self.NS2_WIRED_CONTROLLER_ID:
                        raise ControllerError(
                            f"模式读回为 0x{mode:x}，期望 0x1010"
                        )
                    self.controller_mode = mode
                    try:
                        self.console_connected = self._query_controller_status()
                    except ControllerError:
                        self.console_connected = False
                    if self.console_connected:
                        self.diagnostic = (
                            f"PABotBase2 已连接：NS2 有线手柄可接收按键（{path}）"
                        )
                    else:
                        self.diagnostic = (
                            f"PABotBase2 已就绪：请发送任意按键连接 NS2（{path}）"
                        )
                    return
                except Exception as error:  # noqa: BLE001
                    failures.append(f"{path}: {error}")
                    self._stop_without_sending()
            raise ControllerError(
                "发现串口但 PABotBase2 握手失败：" + "；".join(failures)
            )

    def stop(self) -> None:
        with self._lock:
            if self.ready_for_input:
                self.release_all()
                try:
                    self._change_controller_mode(0)
                except ControllerError:
                    pass
            self._stop_without_sending()
            self.diagnostic = "PABotBase2 已停止并回到安全模式"

    def refresh(self) -> None:
        with self._lock:
            if not self.active:
                return
            try:
                self._pump_packets()
            except (OSError, serial.SerialException) as error:
                self.diagnostic = f"开发板 UART/COM 串口已断开：{error}"
                self._stop_without_sending()

    def press(self, button: str, hold_ms: int) -> None:
        with self._lock:
            button = button.upper()
            if not self.ready_for_input:
                raise ControllerError("PABotBase2 尚未进入 NS2 有线手柄模式")
            if button not in self.BUTTONS and button not in self.DPAD:
                raise ControllerError(f"不支持的手柄按键：{button}", status=400)
            if not 20 <= hold_ms <= 2_000:
                raise ControllerError("hold_ms 必须在 20–2000 之间", status=400)

            self._pump_packets()
            press_id = self._send_controller_state(
                self.state_for(button),
                hold_ms,
            )
            release_id = self._send_controller_state(self.NEUTRAL_STATE, 40)
            self._wait_for_command(press_id, 0.80 + hold_ms / 1_000)
            self._wait_for_command(release_id, 0.80)
            try:
                self.console_connected = self._query_controller_status()
            except ControllerError:
                pass
            if self.console_connected:
                self.diagnostic = (
                    f"已通过 PABotBase2 发送 {button}（NS2 已接收）"
                )
            else:
                self.diagnostic = (
                    f"已发送 {button}，等待 NS2 建立有线手柄连接"
                )

    def release_all(self) -> None:
        with self._lock:
            if not self.ready_for_input:
                return
            try:
                self._send_stream(
                    bytes([0x04, 0x00, self.CANCEL_QUEUE, 0x00])
                )
                release_id = self._send_controller_state(self.NEUTRAL_STATE, 40)
                self._wait_for_command(release_id, 0.80)
                self.diagnostic = "PABotBase2 已释放全部按键"
            except ControllerError as error:
                if str(error).startswith("按键命令 ") and str(error).endswith(
                    "执行超时"
                ):
                    self.console_connected = False
                    self.diagnostic = (
                        "PABotBase2 已发送中性状态；NS2 尚未返回完成确认，"
                        "串口保持连接"
                    )
                    return
                self.diagnostic = f"释放 PABotBase2 按键失败：{error}"
                self._stop_without_sending()
            except Exception as error:  # noqa: BLE001
                self.diagnostic = f"释放 PABotBase2 按键失败：{error}"
                self._stop_without_sending()

    def candidate_ports(self) -> list[str]:
        preferred = os.environ.get("ISLAND_CONTROLLER_SERIAL_PORT", "").strip()
        candidates = [preferred] if preferred else []
        discovered = list(list_ports.comports())

        def priority(port: Any) -> tuple[int, int, str]:
            device = str(getattr(port, "device", "")).strip()
            text = " ".join(
                str(value or "")
                for value in (
                    getattr(port, "description", ""),
                    getattr(port, "manufacturer", ""),
                    getattr(port, "product", ""),
                    getattr(port, "hwid", ""),
                )
            ).lower() + " " + device.lower()
            likely_board = any(
                marker in text
                for marker in (
                    "esp32",
                    "usb serial",
                    "uart",
                    "cp210",
                    "ch340",
                    "ch910",
                    "wch",
                    "silicon labs",
                    "usbmodem",
                    "usbserial",
                    "ttyusb",
                    "ttyacm",
                )
            )
            return (0 if likely_board else 1, -len(device), device.lower())

        for port in sorted(discovered, key=priority):
            path = str(getattr(port, "device", "")).strip()
            if sys.platform == "darwin" and not any(
                marker in path.lower()
                for marker in (
                    "/dev/cu.usbmodem",
                    "/dev/cu.usbserial",
                    "/dev/cu.slab_usbtouart",
                    "/dev/cu.wchusbserial",
                )
            ):
                continue
            if path and path not in candidates:
                candidates.append(path)
        return candidates

    def _open(self, path: str) -> None:
        try:
            connection = self._serial_factory(
                port=path,
                baudrate=self.SERIAL_BAUD,
                timeout=0,
                write_timeout=1,
            )
        except (OSError, serial.SerialException) as error:
            raise ControllerError(f"打开串口 {path} 失败：{error}") from error
        self._serial = connection
        self.port_path = path
        self._sleep(1.40)
        connection.reset_input_buffer()
        connection.reset_output_buffer()

    def _stop_without_sending(self) -> None:
        connection = self._serial
        self._serial = None
        if connection is not None:
            try:
                connection.close()
            except (OSError, serial.SerialException):
                pass
        self.port_path = None
        self.controller_mode = 0
        self.console_connected = False
        self.receive_buffer.clear()
        self.message_buffer.clear()
        self.reset_replies.clear()
        self.stream_replies.clear()
        self.uint32_responses.clear()
        self.uint32_data_responses.clear()
        self.finished_commands.clear()
        self.dropped_commands.clear()

    def _begin_session(self) -> None:
        self.session_id = secrets.randbits(32)
        if self.session_id == 0xFFFF_FFFF:
            self.session_id = 0x4946_4E44
        self.transmit_sequence = 0
        self.transmit_stream_offset = 0
        self.receive_stream_offset = 0
        self.request_id = 1
        self.command_id = 0
        self.receive_buffer.clear()
        self.message_buffer.clear()
        self.reset_replies.clear()
        self.stream_replies.clear()
        self.uint32_responses.clear()
        self.uint32_data_responses.clear()
        self.finished_commands.clear()
        self.dropped_commands.clear()

        packet = self.make_packet(
            sequence=0,
            opcode=self.RESET,
            payload=struct.pack("<I", self.session_id),
            crc_seed=0xFFFF_FFFF,
        )
        self._write_all(packet)
        if not self._wait(lambda: 0 in self.reset_replies, 1.0):
            raise ControllerError("固件未回复 PABotBase2 session reset")
        self.transmit_sequence = 1

    def _send_stream(self, message: bytes) -> None:
        if len(message) > 14:
            raise ControllerError(
                f"单条 PABotBase2 消息过长：{len(message)} bytes"
            )
        sequence = self.transmit_sequence
        payload = struct.pack("<H", self.transmit_stream_offset) + message
        packet = self.make_packet(
            sequence=sequence,
            opcode=self.STREAM,
            payload=payload,
            crc_seed=self.session_id,
        )
        self.stream_replies.discard(sequence)
        for _ in range(3):
            self._write_all(packet)
            if self._wait(lambda: sequence in self.stream_replies, 0.30):
                break
        else:
            raise ControllerError(f"固件未确认串口包 seq={sequence}")

        self.stream_replies.discard(sequence)
        self.transmit_sequence = (sequence + 1) & 0xFF
        self.transmit_stream_offset = (
            self.transmit_stream_offset + len(message)
        ) & 0xFFFF

    def _pump_packets(self) -> None:
        connection = self._serial
        if connection is None:
            return
        while True:
            waiting = max(0, int(connection.in_waiting))
            chunk = connection.read(waiting or 1)
            if not chunk:
                break
            self.receive_buffer.extend(chunk)
        while True:
            packet = self._pull_packet()
            if packet is None:
                return
            self._process_packet(packet)

    def _pull_packet(self) -> Packet | None:
        while True:
            try:
                magic_index = self.receive_buffer.index(self.MAGIC)
            except ValueError:
                self.receive_buffer.clear()
                return None
            if magic_index:
                del self.receive_buffer[:magic_index]
            if len(self.receive_buffer) < 4:
                return None
            encoded_length = self.receive_buffer[2]
            length = 256 if encoded_length == 0 else encoded_length
            if length < 8:
                del self.receive_buffer[0]
                continue
            if len(self.receive_buffer) < length:
                return None
            raw = bytes(self.receive_buffer[:length])
            del self.receive_buffer[:length]
            expected_crc = struct.unpack_from("<I", raw, length - 4)[0]
            actual_crc = self.crc32c(raw[:-4], self.session_id)
            if expected_crc != actual_crc:
                continue
            return Packet(raw[1], raw[3] & 0x7F, raw[4:-4])

    def _process_packet(self, packet: Packet) -> None:
        if packet.opcode == self.RESET_REPLY:
            self.reset_replies.add(packet.sequence)
            return
        if packet.opcode == self.STREAM_REPLY:
            self.stream_replies.add(packet.sequence)
            return
        if packet.opcode != self.STREAM or len(packet.payload) < 2:
            return

        offset = struct.unpack_from("<H", packet.payload, 0)[0]
        data = packet.payload[2:]
        if offset == self.receive_stream_offset:
            self.message_buffer.extend(data)
            self.receive_stream_offset = (
                self.receive_stream_offset + len(data)
            ) & 0xFFFF
            self._process_messages()
        acknowledgement = self.make_packet(
            sequence=packet.sequence,
            opcode=self.STREAM_REPLY,
            payload=struct.pack("<I", 4_096),
            crc_seed=self.session_id,
        )
        self._write_all(acknowledgement)

    def _process_messages(self) -> None:
        while len(self.message_buffer) >= 4:
            length = struct.unpack_from("<H", self.message_buffer, 0)[0]
            if not 4 <= length <= 256:
                del self.message_buffer[0]
                continue
            if len(self.message_buffer) < length:
                return
            message = bytes(self.message_buffer[:length])
            del self.message_buffer[:length]
            opcode = message[2]
            message_id = message[3]
            if opcode == self.RETURN_UINT32 and len(message) >= 8:
                self.uint32_responses[message_id] = struct.unpack_from(
                    "<I", message, 4
                )[0]
            elif opcode == self.RETURN_UINT32_DATA and len(message) >= 8:
                self.uint32_data_responses[message_id] = (
                    struct.unpack_from("<I", message, 4)[0],
                    message[8:],
                )
            elif opcode == self.COMMAND_FINISHED:
                self.finished_commands.add(message_id)
            elif opcode == self.COMMAND_DROPPED:
                self.dropped_commands.add(message_id)

    def _wait(self, condition: Callable[[], bool], timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._pump_packets()
            if condition():
                return True
            self._sleep(0.005)
        self._pump_packets()
        return condition()

    def _write_all(self, data: bytes) -> None:
        connection = self._serial
        if connection is None:
            raise ControllerError("串口尚未打开")
        written = 0
        while written < len(data):
            try:
                count = connection.write(data[written:])
            except (OSError, serial.SerialException) as error:
                raise ControllerError(
                    f"写入串口 {self.port_path or ''} 失败：{error}"
                ) from error
            if count <= 0:
                raise ControllerError(
                    f"写入串口 {self.port_path or ''} 时没有写入任何数据"
                )
            written += count
        connection.flush()

    def _change_controller_mode(self, mode: int) -> None:
        self._send_stream(
            bytes([0x08, 0x00, self.CHANGE_CONTROLLER_MODE, 0x00])
            + struct.pack("<I", mode)
        )
        self.controller_mode = mode

    def _query_controller_mode(self) -> int:
        request_id = self.request_id
        self.request_id = (request_id + 1) & 0xFF
        self.uint32_responses.pop(request_id, None)
        self._send_stream(
            bytes([0x04, 0x00, self.READ_CONTROLLER_MODE, request_id])
        )
        if not self._wait(
            lambda: request_id in self.uint32_responses,
            0.80,
        ):
            raise ControllerError("读取 NS2 控制器模式超时")
        return self.uint32_responses.pop(request_id)

    def _query_controller_status(self) -> bool:
        request_id = self.request_id
        self.request_id = (request_id + 1) & 0xFF
        self.uint32_data_responses.pop(request_id, None)
        self._send_stream(
            bytes([0x04, 0x00, self.REQUEST_STATUS, request_id])
        )
        if not self._wait(
            lambda: request_id in self.uint32_data_responses,
            0.80,
        ):
            raise ControllerError("读取 NS2 有线手柄状态超时")
        mode, data = self.uint32_data_responses.pop(request_id)
        return mode == self.NS2_WIRED_CONTROLLER_ID and bool(
            data and data[0] & 0x01
        )

    def _send_controller_state(self, state: bytes, milliseconds: int) -> int:
        command_id = self.command_id
        self.command_id = (command_id + 1) & 0xFF
        self.finished_commands.discard(command_id)
        self.dropped_commands.discard(command_id)
        message = (
            bytes([0x0D, 0x00, self.WIRED_CONTROLLER_STATE, command_id])
            + struct.pack("<H", milliseconds)
            + state
        )
        self._send_stream(message)
        return command_id

    def _wait_for_command(self, command_id: int, timeout: float) -> None:
        if not self._wait(
            lambda: command_id in self.finished_commands
            or command_id in self.dropped_commands,
            timeout,
        ):
            raise ControllerError(f"按键命令 {command_id} 执行超时")
        if command_id in self.dropped_commands:
            self.dropped_commands.discard(command_id)
            raise ControllerError(f"固件拒绝了按键命令 {command_id}")
        self.finished_commands.discard(command_id)

    @classmethod
    def state_for(cls, button: str) -> bytes:
        button = button.upper()
        state = bytearray(cls.NEUTRAL_STATE)
        if button in cls.DPAD:
            state[2] = cls.DPAD[button]
        elif button in cls.BUTTONS:
            index, bit = cls.BUTTONS[button]
            state[index] |= bit
        else:
            raise ControllerError(f"不支持的手柄按键：{button}", status=400)
        return bytes(state)

    @classmethod
    def make_packet(
        cls,
        sequence: int,
        opcode: int,
        payload: bytes,
        crc_seed: int,
    ) -> bytes:
        full_length = 4 + len(payload) + 4
        if full_length > 256:
            raise ValueError("PABotBase2 packet exceeds 256 bytes")
        packet = bytes(
            [cls.MAGIC, sequence & 0xFF, full_length & 0xFF, opcode & 0xFF]
        ) + payload
        return packet + struct.pack("<I", cls.crc32c(packet, crc_seed))

    @staticmethod
    def crc32c(data: bytes, seed: int) -> int:
        crc = seed & 0xFFFF_FFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = (crc >> 1) ^ (
                    0x82F6_3B78 if crc & 1 else 0
                )
        return crc & 0xFFFF_FFFF


def protocol_self_test() -> list[str]:
    failures: list[str] = []
    packet = PABotBase2Bridge.make_packet(
        sequence=0,
        opcode=0x01,
        payload=bytes([0x44, 0x4E, 0x46, 0x49]),
        crc_seed=0xFFFF_FFFF,
    )
    if packet != bytes(
        [
            0x81,
            0x00,
            0x0C,
            0x01,
            0x44,
            0x4E,
            0x46,
            0x49,
            0xAB,
            0x91,
            0x18,
            0xB5,
        ]
    ):
        failures.append("PABotBase2 CRC32C reset packet")
    expected_states = {
        "A": bytes([0x04, 0x00, 0x08, 0x80, 0x80, 0x80, 0x80]),
        "LEFT": bytes([0x00, 0x00, 0x06, 0x80, 0x80, 0x80, 0x80]),
        "HOME": bytes([0x00, 0x10, 0x08, 0x80, 0x80, 0x80, 0x80]),
    }
    for button, expected in expected_states.items():
        if PABotBase2Bridge.state_for(button) != expected:
            failures.append(f"PABotBase2 {button} button state")
    return failures
