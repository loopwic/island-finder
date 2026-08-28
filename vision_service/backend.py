from __future__ import annotations

import copy
import json
import math
import os
import re
import select
import struct
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from analyzer import analysis_input_sha256, analyze_map
from audit_store import SelectionAuditStore
from birthday_ocr import recognize_birthday
from candidate_ocr import recognize_keyboard_frame
from screen_classifier import classify_screen


CONTROLLER_URL = "http://127.0.0.1:32145"
MAX_CANDIDATE_PAGES = 12
KEYBOARD_OCR_POLL_SECONDS = 0.06
KEYBOARD_OCR_STABLE_HITS = 3
RECOGNITION_RETRY_LIMIT = 3
RECOGNITION_RETRY_BASE_SECONDS = 0.18
MAP_RENDER_MIN_SATURATION_COVERAGE = 0.78
MAP_STABILITY_MAX_DELTA = 0.012
MAP_STABILITY_REQUIRED_COMPARISONS = 2
MAP_STABILITY_MIN_SETTLE_SECONDS = 0.65
TRANSITION_RETRY_LIMIT = 3
TRANSITION_RETRY_BASE_SECONDS = 1.2
ADVANCE_STALL_PRESS_LIMIT = 12
ADVANCE_STALL_MAX_DELTA = 0.01


LEGACY_CARD_REGIONS: list[dict[str, float]] = [
    {"x": 0.105, "y": 0.2, "width": 0.355, "height": 0.29},
    {"x": 0.54, "y": 0.2, "width": 0.355, "height": 0.29},
    {"x": 0.105, "y": 0.535, "width": 0.355, "height": 0.29},
    {"x": 0.54, "y": 0.535, "width": 0.355, "height": 0.29},
]

# Measured from the actual 1920x1080 Chinese four-island selection screen.
# Each region keeps 4-7 pixels of water/card padding around the detected map so
# anti-aliasing and tiny HDMI shifts cannot clip beaches, rocks, or docks.
CALIBRATED_CARD_REGIONS: list[dict[str, float]] = [
    {"x": 0.249, "y": 0.291, "width": 0.232, "height": 0.253},
    {"x": 0.52, "y": 0.296, "width": 0.232, "height": 0.251},
    {"x": 0.2495, "y": 0.5715, "width": 0.23, "height": 0.247},
    {"x": 0.5205, "y": 0.5685, "width": 0.2305, "height": 0.2525},
]


DEFAULT_SETTINGS: dict[str, Any] = {
    "identity": {
        "name": "",
        "namePinyin": [],
        "birthMonth": 1,
        "birthDay": 1,
        "initialStyle": "right",
    },
    "birthdayCursorOrigin": {"month": 1, "day": 1},
    "threshold": 0.76,
    "stableFrames": 3,
    "scanIntervalMs": 320,
    "autoReject": True,
    "dryRun": True,
    "captureDeviceIndex": 0,
    "captureDeviceId": "",
    "captureDeviceName": "",
    "captureWidth": 1920,
    "captureHeight": 1080,
    "captureFps": 30,
    "autoConnectController": True,
    "cardRegions": copy.deepcopy(CALIBRATED_CARD_REGIONS),
    "targets": [],
}


INITIAL_RUNTIME: dict[str, Any] = {
    "phase": "idle",
    "runNumber": 0,
    "startedAt": None,
    "lastMessage": "等待配置",
    "candidates": [],
    "selectedCandidate": None,
    "currentScreen": "unknown",
    "screenConfidence": 0.0,
    "stableHitCount": 0,
}


PINYIN_ROWS = (
    "1234567890-",
    "qwertyuiop/",
    "asdfghjkl:\\",
    "zxcvbnm,.?!",
)


def now_ms() -> int:
    return round(time.time() * 1000)


def _deep_merge(defaults: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(defaults)
    for key, item in value.items():
        if key in result and isinstance(result[key], dict) and isinstance(item, dict):
            result[key] = _deep_merge(result[key], item)
        else:
            result[key] = copy.deepcopy(item)
    return result


def _card_regions_equal(
    left: object,
    right: list[dict[str, float]],
    tolerance: float = 1e-6,
) -> bool:
    if not isinstance(left, list) or len(left) != len(right):
        return False
    try:
        return all(
            all(abs(float(region[key]) - expected[key]) <= tolerance for key in ("x", "y", "width", "height"))
            for region, expected in zip(left, right, strict=True)
            if isinstance(region, dict)
        ) and all(isinstance(region, dict) for region in left)
    except (KeyError, TypeError, ValueError):
        return False


def _default_data_dir() -> Path:
    override = os.environ.get("ISLAND_FINDER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "data"


class SettingsStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or _default_data_dir()
        self.path = self.data_dir / "settings.json"
        self._lock = threading.RLock()
        self._settings = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("settings root must be an object")
            settings = validate_settings(_deep_merge(DEFAULT_SETTINGS, payload))
            legacy_keys = set(payload) - set(DEFAULT_SETTINGS)
            if legacy_keys or not _card_regions_equal(payload.get("cardRegions"), CALIBRATED_CARD_REGIONS):
                temporary = self.path.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps(settings, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                temporary.replace(self.path)
                print("[backend] 已迁移配置并固定四岛裁切框为 1080p 实测坐标")
            return settings
        except FileNotFoundError:
            return copy.deepcopy(DEFAULT_SETTINGS)
        except Exception as error:  # noqa: BLE001
            print(f"[backend] 无法读取后端配置，使用默认值：{error}")
            return copy.deepcopy(DEFAULT_SETTINGS)

    def get(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._settings)

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("配置必须是 JSON 对象")
        with self._lock:
            settings = validate_settings(_deep_merge(self._settings, payload))
            self.data_dir.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.path)
            self._settings = settings
            return copy.deepcopy(settings)


def validate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    identity = settings.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("身份配置无效")
    identity["name"] = str(identity.get("name", ""))[:10]
    pinyin = identity.get("namePinyin", [])
    if not isinstance(pinyin, list):
        raise ValueError("姓名拼音必须是数组")
    identity["namePinyin"] = [str(item) for item in pinyin[:10]]
    identity["birthMonth"] = max(1, min(12, int(identity.get("birthMonth", 1))))
    identity["birthDay"] = max(1, min(31, int(identity.get("birthDay", 1))))
    if identity.get("initialStyle") not in {"left", "right"}:
        raise ValueError("初始造型必须是 left 或 right")

    birthday_origin = settings.get("birthdayCursorOrigin")
    if not isinstance(birthday_origin, dict):
        raise ValueError("生日初始游标配置无效")
    birthday_origin["month"] = max(1, min(12, int(birthday_origin.get("month", 1))))
    birthday_origin["day"] = max(1, min(31, int(birthday_origin.get("day", 1))))

    settings["threshold"] = max(0.55, min(0.95, float(settings.get("threshold", 0.76))))
    settings["stableFrames"] = max(1, min(8, int(settings.get("stableFrames", 3))))
    settings["scanIntervalMs"] = max(250, min(5000, int(settings.get("scanIntervalMs", 320))))
    # Windows camera enumerators encode the selected backend in the high
    # digits (for example DirectShow camera 1 may be index 701).
    settings["captureDeviceIndex"] = max(
        0,
        min(2_048, int(settings.get("captureDeviceIndex", 0))),
    )
    # DirectShow symbolic links commonly include a long USB instance path and
    # GUID. Preserve enough of it for a stable binding after re-enumeration.
    settings["captureDeviceId"] = str(settings.get("captureDeviceId") or "")[:1_024]
    settings["captureDeviceName"] = str(settings.get("captureDeviceName") or "")[:200]
    settings["captureWidth"] = max(640, min(3840, int(settings.get("captureWidth", 1920))))
    settings["captureHeight"] = max(360, min(2160, int(settings.get("captureHeight", 1080))))
    settings["captureFps"] = max(3, min(30, int(settings.get("captureFps", 30))))
    for key in ("autoReject", "dryRun", "autoConnectController"):
        settings[key] = bool(settings.get(key, DEFAULT_SETTINGS[key]))

    # Map crops are backend-owned measured coordinates.  Browser settings are
    # deliberately ignored so a stale tab or accidental drag cannot corrupt
    # map analysis or audit evidence.
    settings["cardRegions"] = copy.deepcopy(CALIBRATED_CARD_REGIONS)
    regions = settings["cardRegions"]
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError("地图识别框无效")
        x, y, width, height = (float(region[key]) for key in ("x", "y", "width", "height"))
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
            raise ValueError("地图识别框必须位于画面内")
        region.update({"x": x, "y": y, "width": width, "height": height})
    # Keep persisted/API settings on the current schema. This also drops
    # browser-era anchor fields from older installations.
    return {key: copy.deepcopy(settings[key]) for key in DEFAULT_SETTINGS}


def _devices_from_system_profiler(payload: dict[str, Any]) -> list[dict[str, Any]]:
    cameras = payload.get("SPCameraDataType", [])
    if not isinstance(cameras, list):
        return []
    devices: list[dict[str, Any]] = []
    for index, camera in enumerate(cameras):
        if not isinstance(camera, dict):
            continue
        name = str(camera.get("_name", "")).strip()
        if not name:
            continue
        model_id = str(camera.get("spcamera_model-id", "")).strip()
        avfoundation_id = str(camera.get("spcamera_unique-id", "")).strip()
        devices.append(
            {
                "index": index,
                "name": name,
                "id": avfoundation_id,
                "avFoundationId": avfoundation_id,
                "modelId": model_id,
                "preferred": bool(re.search(r"capture|uvc|cam\s*link", name, re.IGNORECASE)),
                "usbLinkMbps": None,
                "usbSerialNumber": None,
                "transportCodec": (
                    "MJPEG"
                    if "VendorID_7649 ProductID_61717" in model_id
                    else None
                ),
            }
        )
    return devices


def _usb_details_from_ioreg(output: str, names: list[str]) -> dict[str, dict[str, Any]]:
    lines = output.splitlines()
    devices: dict[str, dict[str, Any]] = {}
    for name in names:
        marker = re.compile(rf"\+-o\s+{re.escape(name)}@")
        for index, line in enumerate(lines):
            if not marker.search(line):
                continue
            detail_payload: dict[str, Any] = {}
            for detail in lines[index + 1 : index + 55]:
                if "+-o " in detail:
                    break
                speed_match = re.search(r'"UsbLinkSpeed"\s*=\s*(\d+)', detail)
                if speed_match:
                    detail_payload["usbLinkMbps"] = round(int(speed_match.group(1)) / 1_000_000)
                serial_match = re.search(r'"USB Serial Number"\s*=\s*"([^"]+)"', detail)
                if serial_match:
                    detail_payload["usbSerialNumber"] = serial_match.group(1)
            if detail_payload:
                devices[name] = detail_payload
            break
    return devices


def _devices_from_camera_infos(camera_infos: list[Any]) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for camera in camera_infos:
        name = str(getattr(camera, "name", "")).strip()
        if not name:
            continue
        index = int(getattr(camera, "index", len(devices)))
        path = str(getattr(camera, "path", "") or "").strip()
        vendor_id = getattr(camera, "vid", None)
        product_id = getattr(camera, "pid", None)
        backend = int(getattr(camera, "backend", cv2.CAP_DSHOW))
        identifier_parts = [
            str(value)
            for value in (vendor_id, product_id, path or name)
            if value not in (None, "")
        ]
        devices.append(
            {
                "index": index,
                "name": name,
                "id": "dshow:" + ":".join(identifier_parts),
                "devicePath": path or None,
                "backend": backend,
                "vendorId": vendor_id,
                "productId": product_id,
                "preferred": bool(
                    re.search(
                        r"capture|uvc|cam\s*link|usb\s*video|hdmi",
                        name,
                        re.IGNORECASE,
                    )
                ),
                "usbLinkMbps": None,
                "usbSerialNumber": None,
                "transportCodec": "MJPEG",
            }
        )
    return devices


def discover_capture_devices() -> list[dict[str, Any]]:
    if sys.platform == "win32":
        try:
            from cv2_enumerate_cameras import enumerate_cameras

            return _devices_from_camera_infos(
                list(enumerate_cameras(cv2.CAP_DSHOW))
            )
        except Exception as error:  # noqa: BLE001
            print(f"[backend] 无法枚举 Windows DirectShow 设备：{error}")
            return []
    if sys.platform != "darwin":
        return []
    try:
        result = subprocess.run(
            ["system_profiler", "SPCameraDataType", "-json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=8,
        )
        payload = json.loads(result.stdout)
        devices = _devices_from_system_profiler(payload)
    except Exception as error:  # noqa: BLE001
        print(f"[backend] 无法枚举 AVFoundation 设备：{error}")
        return []
    if not devices:
        return []
    try:
        result = subprocess.run(
            ["ioreg", "-p", "IOUSB", "-l", "-w", "0"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        usb_details = _usb_details_from_ioreg(result.stdout, [device["name"] for device in devices])
        for device in devices:
            details = usb_details.get(device["name"], {})
            device.update(details)
            if device.get("preferred"):
                stable_parts = [device.get("modelId", ""), device.get("usbSerialNumber") or "no-serial"]
                device["id"] = "uvc:" + ":".join(str(part) for part in stable_parts)
    except Exception as error:  # noqa: BLE001
        print(f"[backend] 无法读取采集卡 USB 链路速率：{error}")
    return devices


def _opencv_capture_backend(
    device: dict[str, Any],
    platform: str | None = None,
) -> int:
    """Select an OpenCV backend without leaking macOS constants to Windows.

    DirectShow camera enumerators can attach a concrete backend to each encoded
    index.  Keep that value when present; otherwise choose the native Windows
    backend explicitly and use OpenCV's automatic backend on other platforms.
    """

    configured_backend = device.get("backend")
    if configured_backend is not None:
        return int(configured_backend)
    return cv2.CAP_DSHOW if (platform or sys.platform) == "win32" else cv2.CAP_ANY


def resolve_capture_device(
    settings: dict[str, Any], devices: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, str | None]:
    configured_id = str(settings.get("captureDeviceId", "")).strip()
    configured_name = str(settings.get("captureDeviceName", "")).strip()
    if configured_id:
        device = next(
            (
                item
                for item in devices
                if item.get("id") == configured_id or item.get("avFoundationId") == configured_id
            ),
            None,
        )
        if device is None and configured_name:
            named = [item for item in devices if item.get("name") == configured_name]
            if len(named) == 1:
                device = named[0]
        if device is None:
            return None, f"已绑定的采集卡不在线：{configured_name or configured_id}"
        if not device.get("preferred"):
            return None, f"{device.get('name')} 不是外接 UVC 采集卡，已拒绝打开"
        return device, None
    if configured_name:
        device = next((item for item in devices if item.get("name") == configured_name), None)
        if device is None:
            return None, f"已绑定的采集卡不在线：{configured_name}"
        if not device.get("preferred"):
            return None, f"{device.get('name')} 不是外接 UVC 采集卡，已拒绝打开"
        return device, None
    preferred = next((item for item in devices if item.get("preferred")), None)
    if preferred is not None:
        return preferred, None
    configured_index = int(settings.get("captureDeviceIndex", 0))
    device = next((item for item in devices if item.get("index") == configured_index), None)
    if device is None:
        return None, f"找不到采集设备索引 {configured_index}"
    if not device.get("preferred"):
        return None, f"{device.get('name')} 不是外接 UVC 采集卡，已拒绝打开"
    return device, None


def effective_capture_mode(
    settings: dict[str, Any], device: dict[str, Any]
) -> tuple[int, int, int, str | None]:
    width = int(settings["captureWidth"])
    height = int(settings["captureHeight"])
    fps = int(settings["captureFps"])
    # AVFoundation exposes decoded 420v sample buffers, but this capture card's
    # UVC descriptor advertises a compressed MJPEG video-streaming format.  Do
    # not infer the USB wire format from the decoded CoreVideo pixel format and
    # do not silently reduce the requested resolution.
    return width, height, fps, None


def normalize_pinyin(value: str) -> str:
    normalized = value.strip().lower()
    for source in "üǖǘǚǜ":
        normalized = normalized.replace(source, "v")
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", normalized)
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[1-5]", "", normalized)


def _is_han(character: str) -> bool:
    name = unicodedata.name(character, "")
    return "CJK UNIFIED IDEOGRAPH" in name or "CJK COMPATIBILITY IDEOGRAPH" in name


def validate_chinese_name(identity: dict[str, Any]) -> None:
    characters = list(str(identity.get("name", "")).strip())
    if not 1 <= len(characters) <= 10:
        raise ValueError("名字需要 1–10 个汉字")
    if not all(_is_han(character) for character in characters):
        raise ValueError("中文自动输入目前只支持汉字名字")
    pinyin = identity.get("namePinyin", [])
    for index, character in enumerate(characters):
        value = normalize_pinyin(str(pinyin[index] if index < len(pinyin) else ""))
        if not re.fullmatch(r"[a-zv]{1,6}", value):
            raise ValueError(f"请填写“{character}”的拼音（不带声调）")


def press(button: str, hold_ms: int = 80, after_ms: int = 160) -> dict[str, Any]:
    return {"type": "press", "button": button, "holdMs": hold_ms, "afterMs": after_ms}


RESTART_COMMANDS = [
    press("HOME", 100, 1100),
    press("X", 80, 350),
    press("A", 80, 1500),
    press("A", 80, 1600),
    press("A", 220, 1500),
]


def _keyboard_nodes() -> list[tuple[str, float, int]]:
    return [
        (key, float(column), row)
        for row, keys in enumerate(PINYIN_ROWS)
        for column, key in enumerate(keys)
    ]


PINYIN_NODES = _keyboard_nodes()


def _neighbors(node: tuple[str, float, int]) -> list[tuple[tuple[str, float, int], str]]:
    key, x, y = node
    horizontal = sorted((item for item in PINYIN_NODES if item[2] == y), key=lambda item: item[1])
    index = next(position for position, item in enumerate(horizontal) if item[0] == key)
    result: list[tuple[tuple[str, float, int], str]] = []
    if index > 0:
        result.append((horizontal[index - 1], "LEFT"))
    if index < len(horizontal) - 1:
        result.append((horizontal[index + 1], "RIGHT"))
    for dy, button in ((-1, "UP"), (1, "DOWN")):
        row = [item for item in PINYIN_NODES if item[2] == y + dy]
        if row:
            result.append((min(row, key=lambda item: abs(item[1] - x)), button))
    return result


def _path_between(source: str, target: str) -> list[str]:
    if source == target:
        return []
    nodes = {item[0]: item for item in PINYIN_NODES}
    if source not in nodes or target not in nodes:
        raise ValueError(f"键盘上找不到字符：{source if source not in nodes else target}")
    queue: deque[tuple[str, list[str]]] = deque([(source, [])])
    visited = {source}
    while queue:
        key, path = queue.popleft()
        for node, button in _neighbors(nodes[key]):
            if node[0] in visited:
                continue
            next_path = [*path, button]
            if node[0] == target:
                return next_path
            visited.add(node[0])
            queue.append((node[0], next_path))
    raise ValueError(f"键盘上找不到字符：{target}")


def commands_for_pinyin(value: str, cursor: str = "1") -> tuple[list[dict[str, Any]], str]:
    pinyin = normalize_pinyin(value)
    if not re.fullmatch(r"[a-zv]{1,6}", pinyin):
        raise ValueError("拼音需要使用 1–6 位英文字母")
    commands: list[dict[str, Any]] = []
    current = cursor
    for character in pinyin:
        commands.extend(press(button, 45, 72) for button in _path_between(current, character))
        commands.append(press("A", 45, 105))
        current = character
    commands[-1] = press("A", 45, 420)
    return commands, current


def commands_to_candidate_row(last_key: str) -> list[dict[str, Any]]:
    node = next((item for item in PINYIN_NODES if item[0] == last_key), None)
    if node is None or node[2] == 0:
        raise ValueError("无法从当前拼音按键进入候选栏")
    return [press("UP", 45, 55) for _ in range(node[2] + 1)]


def commands_for_candidate_move(source: int, target: int) -> list[dict[str, Any]]:
    if source < 0 or target < 0:
        raise ValueError("候选栏位置无效")
    delta = target - source
    button = "RIGHT" if delta >= 0 else "LEFT"
    return [press(button, 45, 55) for _ in range(abs(delta))]


def commands_for_birthday(month: int, day: int, origin_month: int, origin_day: int) -> list[dict[str, Any]]:
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        raise ValueError("生日配置无效")
    commands = [press("UP" if month >= origin_month else "DOWN") for _ in range(abs(month - origin_month))]
    commands.append(press("RIGHT", 80, 120))
    commands.extend(press("UP" if day >= origin_day else "DOWN") for _ in range(abs(day - origin_day)))
    return commands


class OperationCancelled(Exception):
    pass


class RestartRequired(RuntimeError):
    """The current game run is unsafe to continue but the service can recover."""


class ControllerClient:
    def __init__(self, on_event: Callable[[str, str], None]) -> None:
        self._on_event = on_event
        self._lock = threading.RLock()
        self._operation: threading.Event | None = None
        self._dry_run = True
        self._status: dict[str, Any] = {
            "active": False,
            "connected": False,
            "message": "本地手柄服务未连接",
            "transport": None,
        }

    @property
    def connected(self) -> bool:
        with self._lock:
            return bool(self._status["connected"])

    def status(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._status)

    def set_dry_run(self, value: bool) -> None:
        self._dry_run = value

    def _request(self, path: str, method: str = "GET", body: dict[str, Any] | None = None, timeout: float = 3.0) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            CONTROLLER_URL + path,
            method=method,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as error:
            try:
                payload = json.loads(error.read().decode("utf-8"))
                message = payload.get("error", str(error))
            except Exception:  # noqa: BLE001
                message = str(error)
            raise RuntimeError(message) from error
        return payload if isinstance(payload, dict) else {}

    def refresh(self) -> dict[str, Any]:
        try:
            status = self._request("/v1/status", timeout=0.9)
            message = str(status.get("diagnostic", "本地手柄服务已连接"))
            next_status = {
                "active": bool(status.get("pairingActive")),
                "connected": bool(status.get("readyForInput")),
                "message": message,
                "transport": status.get("transport"),
                "serialPort": status.get("serialPort"),
            }
        except Exception as error:  # noqa: BLE001
            next_status = {
                "active": False,
                "connected": False,
                "message": f"本地手柄服务未响应：{error}",
                "transport": None,
            }
        with self._lock:
            changed = next_status != self._status
            self._status = next_status
        if changed:
            self._on_event("status", next_status["message"])
        return self.status()

    def start_pairing(self) -> dict[str, Any]:
        self._request("/v1/pairing/start", method="POST", timeout=8.0)
        return self.refresh()

    def stop_pairing(self) -> dict[str, Any]:
        self.cancel()
        self._request("/v1/pairing/stop", method="POST", timeout=3.0)
        return self.refresh()

    def cancel(self) -> None:
        with self._lock:
            if self._operation is not None:
                self._operation.set()
            self._operation = None
        try:
            self._request("/v1/release-all", method="POST", timeout=1.0)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _sleep(seconds: float, cancelled: threading.Event) -> None:
        if cancelled.wait(max(0.0, seconds)):
            raise OperationCancelled()

    def press(self, button: str, hold_ms: int = 70, after_ms: int = 120) -> None:
        self.run([press(button, hold_ms, after_ms)])

    def run(self, commands: list[dict[str, Any]]) -> None:
        self.cancel()
        cancelled = threading.Event()
        with self._lock:
            self._operation = cancelled
        try:
            for command in commands:
                if cancelled.is_set():
                    raise OperationCancelled()
                if not self._dry_run:
                    if not self.connected:
                        raise RuntimeError("真实控制模式下必须先连接本地手柄服务")
                    self._request(
                        "/v1/press",
                        method="POST",
                        body={
                            "type": "press",
                            "button": command["button"],
                            "hold_ms": int(command.get("holdMs", 70)),
                        },
                        timeout=4.0,
                    )
                self._on_event(
                    "sent",
                    f"{'演练' if self._dry_run else '发送'} {command['button']}",
                )
                self._sleep(int(command.get("holdMs", 70)) / 1000, cancelled)
                self._sleep(int(command.get("afterMs", 120)) / 1000, cancelled)
        finally:
            with self._lock:
                if self._operation is cancelled:
                    self._operation = None


class _OpenCVCaptureSource:
    def __init__(self, capture: cv2.VideoCapture) -> None:
        self.capture = capture

    def read(self) -> tuple[bool, np.ndarray | None, bytes | None]:
        ok, frame = self.capture.read()
        return ok, frame, None

    def close(self) -> None:
        self.capture.release()

    def error_message(self) -> str | None:
        return None


class _NativeJPEGSource:
    MAX_FRAME_BYTES = 20 * 1024 * 1024

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process

    def _read_exact(self, size: int, timeout: float) -> bytes:
        if self.process.stdout is None:
            raise RuntimeError("原生采集进程没有输出管道")
        descriptor = self.process.stdout.fileno()
        payload = bytearray()
        deadline = time.monotonic() + timeout
        while len(payload) < size:
            if self.process.poll() is not None:
                raise EOFError(self.error_message() or "原生采集进程已退出")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("原生采集帧超时")
            ready, _writable, _errors = select.select([descriptor], [], [], remaining)
            if not ready:
                continue
            chunk = os.read(descriptor, size - len(payload))
            if not chunk:
                raise EOFError(self.error_message() or "原生采集流已关闭")
            payload.extend(chunk)
        return bytes(payload)

    def read(self) -> tuple[bool, np.ndarray | None, bytes | None]:
        try:
            length = struct.unpack(">I", self._read_exact(4, 3.0))[0]
            if length < 128 or length > self.MAX_FRAME_BYTES:
                raise ValueError(f"原生采集帧长度无效：{length}")
            encoded = self._read_exact(length, 3.0)
            # Keep the native JPEG compressed until a recognition scan needs a
            # decoded frame. The preview forwards this payload directly at the
            # requested frame rate without a second JPEG encode in Python.
            return True, None, encoded
        except (EOFError, OSError, TimeoutError, ValueError):
            return False, None, None

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()

    def error_message(self) -> str | None:
        if self.process.poll() is None or self.process.stderr is None:
            return None
        try:
            message = self.process.stderr.read().decode("utf-8", errors="replace").strip()
        except Exception:  # noqa: BLE001
            return None
        return message.splitlines()[-1] if message else None


CaptureSource = _OpenCVCaptureSource | _NativeJPEGSource


class CaptureManager:
    def __init__(self, settings: Callable[[], dict[str, Any]], on_event: Callable[[str, str], None]) -> None:
        self._settings = settings
        self._on_event = on_event
        self._lock = threading.Condition(threading.RLock())
        self._stop = threading.Event()
        self._reopen = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame: np.ndarray | None = None
        self._sequence = 0
        self._preview_jpeg: bytes | None = None
        self._preview_sequence = 0
        self._last_mode_note: str | None = None
        self._state: dict[str, Any] = {
            "connected": False,
            "deviceIndex": None,
            "deviceId": None,
            "deviceName": None,
            "width": 0,
            "height": 0,
            "fps": 0.0,
            "readFailures": 0,
            "error": None,
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="capture-card", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._reopen.set()
        if self._thread:
            self._thread.join(timeout=8)

    def reconfigure(self) -> None:
        self._reopen.set()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def latest(self, wait_seconds: float = 0.0, after_sequence: int | None = None) -> tuple[np.ndarray | None, int]:
        with self._lock:
            if after_sequence is not None and self._sequence <= after_sequence and wait_seconds > 0:
                self._lock.wait(wait_seconds)
            return (None if self._frame is None else self._frame.copy(), self._sequence)

    def latest_preview_jpeg(
        self,
        wait_seconds: float = 0.0,
        after_sequence: int | None = None,
    ) -> tuple[bytes | None, int]:
        """Return a native compressed preview frame without a JPEG round trip."""
        with self._lock:
            if (
                after_sequence is not None
                and self._preview_sequence <= after_sequence
                and wait_seconds > 0
            ):
                self._lock.wait(wait_seconds)
            return self._preview_jpeg, self._preview_sequence

    def _set_state(self, **patch: Any) -> None:
        with self._lock:
            previous_error = self._state.get("error")
            previous_connected = self._state.get("connected")
            self._state.update(patch)
            self._lock.notify_all()
        if patch.get("error") and patch.get("error") != previous_error:
            self._on_event("error", str(patch["error"]))
        elif patch.get("connected") and not previous_connected:
            self._on_event("status", "后端已接管采集卡画面")

    def _open(self, settings: dict[str, Any]) -> tuple[CaptureSource | None, dict[str, Any]]:
        devices = discover_capture_devices()
        if sys.platform == "darwin" and not devices:
            return None, {
                "deviceIndex": None,
                "deviceId": settings.get("captureDeviceId") or None,
                "deviceName": settings.get("captureDeviceName") or None,
                "error": "macOS 未返回可用视频设备；请检查采集卡连接和摄像头权限",
            }
        if devices:
            device, error = resolve_capture_device(settings, devices)
            if device is None:
                return None, {
                    "deviceIndex": None,
                    "deviceId": settings.get("captureDeviceId") or None,
                    "deviceName": settings.get("captureDeviceName") or None,
                    "error": error,
                }
        else:
            device = {
                "index": int(settings["captureDeviceIndex"]),
                "id": "",
                "name": f"Video device {settings['captureDeviceIndex']}",
                "preferred": False,
                "usbLinkMbps": None,
            }

        index = int(device["index"])
        width, height, fps, mode_note = effective_capture_mode(settings, device)
        capture_backend = "opencv"
        if sys.platform == "darwin":
            project_root = Path(__file__).resolve().parent.parent
            script = project_root / "scripts" / "run-capture-stream.sh"
            command = [
                "/bin/zsh",
                str(script),
                "--device-id",
                str(device.get("avFoundationId") or ""),
                "--device-name",
                str(device["name"]),
                "--width",
                str(width),
                "--height",
                str(height),
                "--source-fps",
                str(fps),
                "--output-fps",
                str(fps),
                "--jpeg-quality",
                "0.76",
            ]
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(project_root),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
            except OSError as error:
                return None, {
                    "deviceIndex": index,
                    "deviceId": device.get("id") or None,
                    "deviceName": device.get("name"),
                    "error": f"无法启动原生采集进程：{error}",
                }
            capture: CaptureSource = _NativeJPEGSource(process)
            capture_backend = "native-avfoundation-jpeg-pipe"
        else:
            backend = _opencv_capture_backend(device)
            opencv_capture = cv2.VideoCapture(index, backend)
            if not opencv_capture.isOpened() and backend != cv2.CAP_ANY:
                opencv_capture.release()
                opencv_capture = cv2.VideoCapture(index)
            if not opencv_capture.isOpened():
                opencv_capture.release()
                return None, {
                    "deviceIndex": index,
                    "deviceId": device.get("id") or None,
                    "deviceName": device.get("name"),
                    "error": f"后端无法打开采集设备 {device.get('name')}（索引 {index}）",
                }
            if sys.platform == "win32":
                opencv_capture.set(
                    cv2.CAP_PROP_FOURCC,
                    cv2.VideoWriter_fourcc(*"MJPG"),
                )
            opencv_capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            opencv_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            opencv_capture.set(cv2.CAP_PROP_FPS, fps)
            capture = _OpenCVCaptureSource(opencv_capture)
            capture_backend = (
                "opencv-directshow"
                if sys.platform == "win32"
                else "opencv"
            )
        transport_codec = device.get("transportCodec")
        if transport_codec and sys.platform == "darwin":
            transport_note = (
                f"{device['name']} 使用 UVC {transport_codec} 压缩传输；"
                "原生 AVFoundation 按设备 ID 采集，并用 JPEG 帧流交给 Python"
            )
        elif transport_codec and sys.platform == "win32":
            transport_note = (
                f"{device['name']} 使用 DirectShow / UVC "
                f"{transport_codec} 采集"
            )
        else:
            transport_note = mode_note
        if transport_note and transport_note != self._last_mode_note:
            self._on_event("status", transport_note)
        self._last_mode_note = transport_note
        return capture, {
            "deviceIndex": index,
            "deviceId": device.get("id") or None,
            "avFoundationId": device.get("avFoundationId") or None,
            "deviceName": device.get("name"),
            "usbSerialNumber": device.get("usbSerialNumber"),
            "transportCodec": transport_codec,
            "captureBackend": capture_backend,
            "requestedWidth": int(settings["captureWidth"]),
            "requestedHeight": int(settings["captureHeight"]),
            "requestedFps": int(settings["captureFps"]),
            "captureWidth": width,
            "captureHeight": height,
            "captureFps": fps,
            "usbLinkMbps": device.get("usbLinkMbps"),
            "modeNote": mode_note,
        }

    def _run(self) -> None:
        capture: CaptureSource | None = None
        last_frame_at = 0.0
        consecutive_failures = 0
        successes_since_open = 0
        reconnect_delay = 1.0
        next_read_at = 0.0
        next_decode_at = 0.0
        frame_times: deque[float] = deque(maxlen=40)
        analysis_frame_times: deque[float] = deque(maxlen=20)
        while not self._stop.is_set():
            settings = self._settings()
            if capture is None or self._reopen.is_set():
                self._reopen.clear()
                if capture is not None:
                    capture.close()
                capture, open_state = self._open(settings)
                if capture is None:
                    self._set_state(
                        connected=False,
                        readFailures=consecutive_failures,
                        **open_state,
                    )
                    self._reopen.wait(reconnect_delay)
                    reconnect_delay = min(8.0, reconnect_delay * 2)
                    continue
                self._set_state(
                    connected=False,
                    readFailures=0,
                    **open_state,
                )
                consecutive_failures = 0
                successes_since_open = 0
                next_read_at = 0.0
                next_decode_at = 0.0
                frame_times.clear()
                analysis_frame_times.clear()

            # The native JPEG pipe is already paced by the UVC/AVFoundation
            # timestamps. Sleeping here adds a second clock and costs several
            # frames per second. OpenCV sources may return as fast as possible,
            # so retain the explicit cap only for that fallback path.
            if isinstance(capture, _OpenCVCaptureSource):
                target_read_fps = max(3, min(30, int(self._state.get("captureFps", 30))))
                remaining = next_read_at - time.monotonic()
                if remaining > 0 and self._stop.wait(remaining):
                    break
                next_read_at = time.monotonic() + 1 / target_read_fps

            ok, frame, preview_jpeg = capture.read()
            if not ok or (frame is None and not preview_jpeg):
                consecutive_failures += 1
                source_error = capture.error_message()
                stale_for = time.monotonic() - last_frame_at if last_frame_at else math.inf
                if consecutive_failures < 3 and stale_for < 3.0:
                    self._set_state(readFailures=consecutive_failures)
                    continue
                self._set_state(
                    connected=False,
                    readFailures=consecutive_failures,
                    error=(
                        source_error
                        or f"采集卡连续 {consecutive_failures} 次未返回帧，{reconnect_delay:.0f} 秒后重试"
                    ),
                )
                capture.close()
                capture = None
                self._reopen.wait(reconnect_delay)
                reconnect_delay = min(8.0, reconnect_delay * 2)
                continue

            current = time.monotonic()
            analysis_interval = max(0.1, int(settings.get("scanIntervalMs", 250)) / 1000)
            if frame is None and (self._frame is None or current >= next_decode_at):
                frame = cv2.imdecode(
                    np.frombuffer(preview_jpeg, dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if frame is None or frame.size == 0:
                    consecutive_failures += 1
                    self._set_state(readFailures=consecutive_failures)
                    continue
                next_decode_at = current + analysis_interval
                analysis_frame_times.append(current)
            elif frame is not None and current >= next_decode_at:
                # Non-native capture backends already return decoded frames.
                # Encode once here so their preview uses the same streaming API.
                encoded_ok, encoded = cv2.imencode(
                    ".jpg",
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 76],
                )
                if encoded_ok:
                    preview_jpeg = encoded.tobytes()
                next_decode_at = current + analysis_interval
                analysis_frame_times.append(current)
            consecutive_failures = 0
            successes_since_open += 1
            if successes_since_open >= 10:
                reconnect_delay = 1.0
            frame_times.append(current)
            measured_fps = self._state.get("fps", 0.0)
            if len(frame_times) >= 2:
                measured_fps = (len(frame_times) - 1) / max(0.001, frame_times[-1] - frame_times[0])
            if frame is not None:
                height, width = frame.shape[:2]
            else:
                width = int(self._state.get("captureWidth", 0))
                height = int(self._state.get("captureHeight", 0))
            analysis_fps = self._state.get("analysisFps", 0.0)
            if len(analysis_frame_times) >= 2:
                analysis_fps = (len(analysis_frame_times) - 1) / max(
                    0.001,
                    analysis_frame_times[-1] - analysis_frame_times[0],
                )
            with self._lock:
                if preview_jpeg:
                    self._preview_jpeg = preview_jpeg
                    self._preview_sequence += 1
                if frame is not None:
                    self._frame = frame
                    self._sequence += 1
                self._state.update(
                    {
                        "connected": True,
                        "width": width,
                        "height": height,
                        "fps": round(float(measured_fps), 1),
                        "analysisFps": round(float(analysis_fps), 1),
                        "readFailures": 0,
                        "error": None,
                        "lastFrameAt": now_ms(),
                    }
                )
                self._lock.notify_all()
            last_frame_at = current
        if capture is not None:
            capture.close()


def _crop_region(frame: np.ndarray, region: dict[str, float]) -> np.ndarray:
    height, width = frame.shape[:2]
    x0 = max(0, min(width - 1, round(region["x"] * width)))
    y0 = max(0, min(height - 1, round(region["y"] * height)))
    x1 = max(x0 + 1, min(width, round((region["x"] + region["width"]) * width)))
    y1 = max(y0 + 1, min(height, round((region["y"] + region["height"]) * height)))
    return frame[y0:y1, x0:x1]


def _map_render_completeness(
    frame: np.ndarray,
    regions: list[dict[str, float]],
) -> float:
    """Return the weakest map card's saturated-pixel coverage.

    The four-island panel fades in over the previous dialogue frame.  During
    that cross-fade the map classifier can already identify all four cards,
    but their colors and structural contrast are not fully rendered yet.
    Requiring every calibrated card to reach normal map saturation rejects
    those translucent frames, including a frozen frame that has no temporal
    motion.
    """
    coverages: list[float] = []
    for region in regions:
        crop = _crop_region(frame, region)
        if crop.size == 0:
            return 0.0
        saturation = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 1]
        coverages.append(float(np.count_nonzero(saturation > 50)) / max(1, saturation.size))
    return min(coverages, default=0.0)


def _map_stability_signature(
    frame: np.ndarray,
    regions: list[dict[str, float]],
) -> np.ndarray:
    """Build a small, noise-resistant signature from the four map crops."""
    samples: list[np.ndarray] = []
    for region in regions:
        crop = _crop_region(frame, region)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (96, 64), interpolation=cv2.INTER_AREA)
        samples.append(cv2.GaussianBlur(resized, (5, 5), 0).reshape(-1))
    return np.concatenate(samples)


def _map_stability_delta(previous: np.ndarray, current: np.ndarray) -> float:
    if previous.shape != current.shape or previous.size == 0:
        return 1.0
    difference = cv2.absdiff(previous, current)
    return float(difference.mean()) / 255.0


def _advance_stability_signature(frame: np.ndarray) -> np.ndarray:
    """Build a noise-resistant whole-screen signature for stuck-page detection."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (96, 54), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(resized, (5, 5), 0)


def _feature(image: np.ndarray) -> dict[str, list[float]]:
    resized = cv2.resize(image, (40, 40), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float64) / 255.0
    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    chroma = (green - blue + 1) / 2
    gx = cv2.Sobel(luminance, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(luminance, cv2.CV_64F, 0, 1, ksize=3)
    edges = np.minimum(1.0, np.hypot(gx, gy))
    histogram: list[float] = []
    for channel in (red, green, blue):
        values, _bins = np.histogram(channel, bins=4, range=(0, 1))
        histogram.extend((values / (40 * 40 * 3)).tolist())
    return {
        "luminance": luminance.reshape(-1).tolist(),
        "chroma": chroma.reshape(-1).tolist(),
        "edges": edges.reshape(-1).tolist(),
        "colorHistogram": histogram,
    }


def _zero_mean_cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    a, b = np.asarray(left), np.asarray(right)
    a, b = a - a.mean(), b - b.mean()
    norms = float(np.linalg.norm(a) * np.linalg.norm(b))
    if norms < 1e-8:
        return 1.0 if abs(float(np.mean(left)) - float(np.mean(right))) < 0.02 else 0.0
    return max(0.0, min(1.0, (float(np.dot(a, b)) / norms + 1) / 2))


def _compare_features(left: dict[str, list[float]], right: dict[str, Any]) -> float:
    try:
        structure = _zero_mean_cosine(left["luminance"], right["luminance"])
        land_water = _zero_mean_cosine(left["chroma"], right["chroma"])
        edge_left, edge_right = left["edges"], right["edges"]
        edge = max(0.0, 1 - sum(abs(a - b) for a, b in zip(edge_left, edge_right, strict=True)) / len(edge_left))
        hist_left, hist_right = left["colorHistogram"], right["colorHistogram"]
        overlap = sum(min(a, b) for a, b in zip(hist_left, hist_right, strict=True))
        total = sum(max(a, b) for a, b in zip(hist_left, hist_right, strict=True))
        color = 1.0 if total == 0 else overlap / total
        return max(0.0, min(1.0, structure * 0.24 + land_water * 0.38 + edge * 0.28 + color * 0.1))
    except (KeyError, TypeError, ValueError):
        return 0.0


class AutomationEngine:
    def __init__(
        self,
        settings: Callable[[], dict[str, Any]],
        capture: CaptureManager,
        controller: ControllerClient,
        audits: SelectionAuditStore,
        on_snapshot: Callable[[dict[str, Any]], None],
        on_log: Callable[[str, str], None],
    ) -> None:
        self._settings = settings
        self.capture = capture
        self.controller = controller
        self.audits = audits
        self.on_snapshot = on_snapshot
        self.on_log = on_log
        self._lock = threading.RLock()
        self.snapshot = copy.deepcopy(INITIAL_RUNTIME)
        self.busy = False
        self.generation = 0
        self.handled_name = False
        self.handled_birthday = False
        self.handled_style = False
        self.handled_appearance = False
        self.last_advance_at = 0
        self.stable_key = ""
        self.reject_stable_key = ""
        self.reject_stable_hits = 0
        self.scan_sample_count = 0
        self.stable_screen_kind = "unknown"
        self.stable_screen_hits = 0
        self.map_first_seen_at: float | None = None
        self.map_previous_signature: np.ndarray | None = None
        self.map_stable_comparisons = 0
        self.transition_retry: dict[str, Any] | None = None
        self.advance_watch_kind = ""
        self.advance_watch_signature: np.ndarray | None = None
        self.advance_watch_presses = 0
        self.active_audit_id: str | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="automation-engine", daemon=True)

    def start_worker(self) -> None:
        self._thread.start()

    def shutdown(self) -> None:
        self._stop.set()
        self.controller.cancel()
        self._thread.join(timeout=3)

    def state(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self.snapshot)

    def _patch(self, **patch: Any) -> None:
        with self._lock:
            self.snapshot.update(copy.deepcopy(patch))
            snapshot = copy.deepcopy(self.snapshot)
        self.on_snapshot(snapshot)

    def _log(self, level: str, message: str) -> None:
        self.on_log(level, message)

    def _reset_guards(self) -> None:
        self.handled_name = False
        self.handled_birthday = False
        self.handled_style = False
        self.handled_appearance = False
        self.stable_key = ""
        self.reject_stable_key = ""
        self.reject_stable_hits = 0
        self.scan_sample_count = 0
        self.stable_screen_kind = "unknown"
        self.stable_screen_hits = 0
        self._reset_map_stability()
        self.transition_retry = None
        self._reset_advance_watch()
        self.last_advance_at = 0
        self.active_audit_id = None

    def _reset_map_stability(self) -> None:
        self.map_first_seen_at = None
        self.map_previous_signature = None
        self.map_stable_comparisons = 0

    def _reset_advance_watch(self) -> None:
        with self._lock:
            self.advance_watch_kind = ""
            self.advance_watch_signature = None
            self.advance_watch_presses = 0

    def _advance_page_stalled(self, screen_kind: str, signature: np.ndarray) -> bool:
        """Return true after bounded presses fail to produce a visual change."""
        with self._lock:
            previous = self.advance_watch_signature
            if (
                screen_kind != self.advance_watch_kind
                or previous is None
                or previous.shape != signature.shape
            ):
                self.advance_watch_kind = screen_kind
                self.advance_watch_signature = signature.copy()
                self.advance_watch_presses = 0
                return False

            delta = _map_stability_delta(previous, signature)
            if delta > ADVANCE_STALL_MAX_DELTA:
                self.advance_watch_signature = signature.copy()
                self.advance_watch_presses = 0
                return False
            return self.advance_watch_presses >= ADVANCE_STALL_PRESS_LIMIT

    def _record_advance_press(self, screen_kind: str) -> None:
        with self._lock:
            if screen_kind == self.advance_watch_kind:
                self.advance_watch_presses += 1

    @staticmethod
    def _transition_retry_delay(retry_count: int) -> float:
        return TRANSITION_RETRY_BASE_SECONDS * (1 + retry_count * 0.5)

    def _arm_transition_retry(
        self,
        screen_kind: str,
        button: str,
        label: str,
        *,
        hold_ms: int = 80,
        after_ms: int = 500,
        observed_at: float | None = None,
    ) -> None:
        current_time = time.monotonic() if observed_at is None else observed_at
        with self._lock:
            self.transition_retry = {
                "screenKind": screen_kind,
                "button": button,
                "label": label,
                "holdMs": hold_ms,
                "afterMs": after_ms,
                "retryCount": 0,
                "deadline": current_time + self._transition_retry_delay(0),
            }
        self._patch(lastMessage=f"{label}已发送，等待页面切换")

    def _maybe_retry_transition(
        self,
        screen_kind: str,
        *,
        observed_at: float | None = None,
    ) -> bool:
        current_time = time.monotonic() if observed_at is None else observed_at
        with self._lock:
            pending = self.transition_retry
            if pending is None:
                return False
            if screen_kind != pending["screenKind"]:
                self.transition_retry = None
                return False
            if current_time < float(pending["deadline"]):
                return True
            retry_count = int(pending["retryCount"])
            if retry_count >= TRANSITION_RETRY_LIMIT:
                self.transition_retry = None
                exhausted = copy.deepcopy(pending)
                next_retry: dict[str, Any] | None = None
            else:
                retry_count += 1
                pending["retryCount"] = retry_count
                pending["deadline"] = current_time + self._transition_retry_delay(retry_count)
                exhausted = None
                next_retry = copy.deepcopy(pending)

        if exhausted is not None:
            reason = (
                f"{exhausted['label']}后页面仍停留在 {screen_kind}；"
                f"已完成 {TRANSITION_RETRY_LIMIT} 轮重试，放弃本轮"
            )
            self._spawn(lambda: self._restart(reason))
            return True

        assert next_retry is not None
        retry_count = int(next_retry["retryCount"])
        label = str(next_retry["label"])
        self._patch(
            lastMessage=f"{label}后页面未切换，重试 {retry_count}/{TRANSITION_RETRY_LIMIT}"
        )
        self._log(
            "warning",
            f"{label}后仍识别为 {screen_kind}，执行第 {retry_count}/{TRANSITION_RETRY_LIMIT} 轮重试",
        )
        self._spawn(
            lambda: self.controller.press(
                str(next_retry["button"]),
                int(next_retry["holdMs"]),
                int(next_retry["afterMs"]),
            )
        )
        return True

    def _map_frame_ready(
        self,
        frame: np.ndarray,
        regions: list[dict[str, float]],
        *,
        observed_at: float | None = None,
    ) -> tuple[bool, float, float, int]:
        current_time = time.monotonic() if observed_at is None else observed_at
        if self.map_first_seen_at is None:
            self.map_first_seen_at = current_time

        completeness = _map_render_completeness(frame, regions)
        signature = _map_stability_signature(frame, regions)
        delta = (
            1.0
            if self.map_previous_signature is None
            else _map_stability_delta(self.map_previous_signature, signature)
        )
        self.map_previous_signature = signature

        complete = completeness >= MAP_RENDER_MIN_SATURATION_COVERAGE
        unchanged = delta <= MAP_STABILITY_MAX_DELTA
        if complete and unchanged:
            self.map_stable_comparisons += 1
        else:
            self.map_stable_comparisons = 0

        settled = current_time - self.map_first_seen_at >= MAP_STABILITY_MIN_SETTLE_SECONDS
        ready = (
            settled
            and complete
            and self.map_stable_comparisons >= MAP_STABILITY_REQUIRED_COMPARISONS
        )
        return ready, completeness, delta, self.map_stable_comparisons

    def _update_active_audit(self, **patch: Any) -> dict[str, Any] | None:
        audit_id = self.active_audit_id
        if audit_id is None:
            return None
        return self.audits.update(audit_id, **patch)

    def _spawn(self, action: Callable[[], None]) -> bool:
        with self._lock:
            if self.busy:
                return False
            self.busy = True
            self.generation += 1
            generation = self.generation

        def run() -> None:
            try:
                action()
            except OperationCancelled:
                pass
            except RestartRequired as error:
                try:
                    self._restart_after_unsafe_state(error)
                except OperationCancelled:
                    pass
                except Exception as restart_error:  # noqa: BLE001
                    self._fail(
                        RuntimeError(f"危险状态自动重开失败：{restart_error}")
                    )
            except Exception as error:  # noqa: BLE001
                self._fail(error)
            finally:
                with self._lock:
                    if generation == self.generation:
                        self.busy = False

        threading.Thread(target=run, name="automation-action", daemon=True).start()
        return True

    def start(self) -> None:
        settings = self._settings()
        validate_chinese_name(settings["identity"])
        self.controller.set_dry_run(bool(settings["dryRun"]))
        if not settings["dryRun"] and not self.controller.connected:
            if settings.get("autoConnectController", True):
                self.controller.start_pairing()
            if not self.controller.connected:
                raise RuntimeError("真实控制模式下必须先完成模拟手柄与 Switch 2 的配对")
        self.controller.cancel()
        with self._lock:
            self._update_active_audit(
                status="superseded",
                summary="用户启动了新一轮，上一轮审计已结束",
                decision="启动新一轮",
            )
            self.busy = False
            self.generation += 1
            self._reset_guards()
        self._patch(
            phase="fastForwarding" if settings["dryRun"] else "restarting",
            runNumber=int(self.snapshot["runNumber"]) + 1,
            startedAt=now_ms(),
            lastMessage=(
                "演练模式：从当前画面开始识别"
                if settings["dryRun"]
                else "正在关闭并重开游戏，确保从完整流程开始"
            ),
            candidates=[],
            selectedCandidate=None,
            stableHitCount=0,
        )
        if settings["dryRun"]:
            self._log("info", f"第 {self.snapshot['runNumber']} 轮演练开始")
        else:
            self._log("info", f"第 {self.snapshot['runNumber']} 轮开始：先重开游戏")
            self._spawn(self._start_fresh_game)

    def pause(self, message: str = "已暂停") -> None:
        with self._lock:
            self.generation += 1
            self.busy = False
        self.controller.cancel()
        self._update_active_audit(status="paused", summary=message)
        self._patch(phase="paused", lastMessage=message)
        self._log("warning", message)

    def resume(self) -> None:
        if self.state()["phase"] != "paused":
            return
        self._patch(phase="fastForwarding", lastMessage="继续自动识别")
        self._log("info", "自动选岛已继续")

    def stop(self) -> None:
        with self._lock:
            self.generation += 1
            self.busy = False
        self.controller.cancel()
        self._update_active_audit(
            status="stopped",
            summary="用户停止了自动选岛",
            decision="流程已停止",
        )
        self._reset_guards()
        reset = copy.deepcopy(INITIAL_RUNTIME)
        reset["lastMessage"] = "已停止"
        self._patch(**reset)
        self._log("info", "自动选岛已停止")

    def accept_candidate(self) -> None:
        if self.state()["phase"] != "awaitingDecision":
            return
        self._spawn(self._accept_candidate)

    def reject_candidate(self) -> None:
        if self.state()["phase"] != "awaitingDecision":
            return
        self._spawn(lambda: self._restart("用户放弃候选岛", audit_status="userRejected"))

    def _start_fresh_game(self) -> None:
        self.controller.run(RESTART_COMMANDS)
        self.last_advance_at = 0
        self.stable_screen_kind = "unknown"
        self.stable_screen_hits = 0
        self._patch(phase="fastForwarding", lastMessage="游戏已重开，正在从启动页识别并推进")
        self._log("success", "游戏已重开，完整自动流程开始")

    def _accept_candidate(self) -> None:
        selected = self.state().get("selectedCandidate")
        selected_index = int(selected["cardIndex"]) if isinstance(selected, dict) else None
        self._update_active_audit(
            status="accepted",
            summary=(
                f"用户确认保留地图 {selected_index + 1}"
                if selected_index is not None
                else "用户确认保留候选岛"
            ),
            decision="用户确认保留",
            selectedCardIndex=selected_index,
        )
        self.controller.press("A", 80, 250)
        self.active_audit_id = None
        self._patch(phase="paused", lastMessage="已确认该岛，控制权已交还给用户")
        self._log("success", "用户选择保留候选岛；自动化已停止发送按键")

    def _loop(self) -> None:
        next_controller_poll = 0.0
        while not self._stop.is_set():
            current = time.monotonic()
            if current >= next_controller_poll:
                self.controller.refresh()
                next_controller_poll = current + 1.0
            state = self.state()
            with self._lock:
                should_observe = not self.busy and state["phase"] in {"fastForwarding", "scanning"}
            if should_observe:
                frame, _sequence = self.capture.latest()
                if frame is not None:
                    try:
                        self._observe_frame(frame)
                    except Exception as error:  # noqa: BLE001
                        self._fail(error)
            interval = max(0.25, int(self._settings()["scanIntervalMs"]) / 1000)
            self._stop.wait(interval if should_observe else min(0.5, interval))

    def _observe_frame(self, frame: np.ndarray) -> None:
        settings = self._settings()
        small = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
        regions = [
            (region["x"], region["y"], region["width"], region["height"])
            for region in settings["cardRegions"]
        ]
        screen = classify_screen(small, regions)
        if screen.kind == "mapSelection":
            ready, completeness, delta, stable_comparisons = self._map_frame_ready(
                frame,
                settings["cardRegions"],
            )
            if not ready:
                self.stable_screen_kind = "unknown"
                self.stable_screen_hits = 0
                if completeness < MAP_RENDER_MIN_SATURATION_COVERAGE:
                    message = (
                        "地图页仍在淡入，等待渲染完成"
                        f"（色彩完整度 {round(completeness * 100)}%）"
                    )
                elif delta > MAP_STABILITY_MAX_DELTA:
                    message = "地图页已出现，等待画面停止变化"
                else:
                    message = (
                        "地图页已出现，正在确认稳定帧 "
                        f"{stable_comparisons}/{MAP_STABILITY_REQUIRED_COMPARISONS}"
                    )
                self._patch(
                    candidates=[],
                    currentScreen=screen.kind,
                    screenConfidence=float(screen.confidence),
                    stableHitCount=0,
                    lastMessage=message,
                )
                return
        else:
            self._reset_map_stability()

        candidates = self._analyze_maps(frame, settings) if screen.kind == "mapSelection" else []
        if screen.kind == "mapSelection" and len(candidates) == 4 and self.active_audit_id is None:
            record = self.audits.create(
                frame,
                settings["cardRegions"],
                candidates,
                run_number=int(self.snapshot["runNumber"]),
                threshold=float(settings["threshold"]),
                stable_frames=int(settings["stableFrames"]),
                auto_reject=bool(settings["autoReject"]),
            )
            self.active_audit_id = str(record["id"])
            self._log("info", "四岛地图原始画面与四张裁切图已写入审计记录")
        elif screen.kind == "mapSelection" and len(candidates) == 4 and self.active_audit_id is not None:
            self.audits.replace_evidence(
                self.active_audit_id,
                frame,
                settings["cardRegions"],
                candidates,
            )
        self._observe(
            screen.as_payload(),
            candidates,
            _advance_stability_signature(frame),
        )

    def _analyze_maps(self, frame: np.ndarray, settings: dict[str, Any]) -> list[dict[str, Any]]:
        targets = settings.get("targets", [])
        candidates: list[dict[str, Any]] = []
        for index, region in enumerate(settings["cardRegions"]):
            crop = _crop_region(frame, region)
            result = analyze_map(crop)
            result.update(
                {
                    "cardIndex": index,
                    "analysisInputSha256": analysis_input_sha256(crop),
                    "targetId": None,
                    "targetName": "条件筛选",
                    "visualSimilarity": None,
                    "visionEngine": "opencv",
                }
            )
            if targets:
                feature = _feature(crop)
                scored = [
                    (_compare_features(feature, target.get("feature", {})), target)
                    for target in targets
                    if isinstance(target, dict)
                ]
                if scored:
                    similarity, target = max(scored, key=lambda item: item[0])
                    result["score"] = float(result["score"]) * 0.96 + similarity * 0.04
                    result["targetId"] = target.get("id")
                    result["targetName"] = target.get("name", "条件筛选")
                    result["visualSimilarity"] = similarity
            candidates.append(result)
        return candidates

    def _observe(
        self,
        screen: dict[str, Any],
        candidates: list[dict[str, Any]],
        frame_signature: np.ndarray,
    ) -> None:
        self._patch(
            candidates=candidates,
            currentScreen=screen["kind"],
            screenConfidence=float(screen["confidence"]),
        )
        state = self.state()
        with self._lock:
            if self.busy or state["phase"] in {"idle", "paused", "awaitingDecision", "restarting", "error"}:
                return
        if screen["kind"] == self.stable_screen_kind and screen["confidence"] >= 0.58:
            self.stable_screen_hits += 1
        else:
            self.stable_screen_kind = screen["kind"]
            self.stable_screen_hits = 1 if screen["confidence"] >= 0.58 else 0

        if screen["kind"] in {"noSignal", "loading"}:
            message = "采集画面无信号，已停止发送按键" if screen["kind"] == "noSignal" else "画面正在加载，等待稳定"
            if state["lastMessage"] != message:
                self._patch(lastMessage=message)
            return
        if screen["kind"] == "unknown" or screen["confidence"] < 0.58:
            message = f"页面未可靠识别（{round(screen['confidence'] * 100)}%），等待下一帧"
            if state["lastMessage"] != message:
                self._patch(lastMessage=message)
            return
        if self.stable_screen_hits < 2:
            self._patch(lastMessage=f"正在确认当前页面：{screen['kind']}")
            return
        if self._maybe_retry_transition(screen["kind"]):
            return
        advance_kinds = {"dialogue", "choiceDialog", "startupPrompt", "styleChoice"}
        if screen["kind"] not in advance_kinds:
            self._reset_advance_watch()
        if screen["kind"] == "homeMenu":
            self._spawn(self._launch_selected_game)
            return
        if screen["kind"] == "accountPicker":
            self._spawn(self._confirm_player_account)
            return
        if screen["kind"] == "mapSelection":
            self._patch(phase="scanning", lastMessage="四岛地图页已锁定，正在比对地图结构")
            self._scan(candidates)
            return
        if not self.handled_name and screen["kind"] == "nameKeyboard":
            self._spawn(self._enter_name)
            return
        if not self.handled_birthday and screen["kind"] == "birthdayPicker":
            self._spawn(self._enter_birthday)
            return
        if not self.handled_style and screen["kind"] == "styleChoice":
            self._spawn(self._choose_initial_style)
            return
        if not self.handled_appearance and screen["kind"] == "appearanceEditor":
            self._spawn(self._confirm_default_appearance)
            return
        if screen["kind"] in advance_kinds:
            if self._advance_page_stalled(screen["kind"], frame_signature):
                reason = (
                    f"{screen['kind']} 连续推进 {ADVANCE_STALL_PRESS_LIMIT} 次后"
                    "画面仍未变化，判定流程卡住"
                )
                self._log("warning", reason)
                self._spawn(lambda: self._restart(reason))
                return
            if now_ms() - self.last_advance_at >= 300:
                self._spawn(lambda: self._advance_dialogue(screen["kind"]))

    def _scan(self, candidates: list[dict[str, Any]]) -> None:
        if not candidates:
            return
        settings = self._settings()
        self.scan_sample_count += 1
        best = max(candidates, key=lambda candidate: float(candidate["score"]))
        key = f"{best['cardIndex']}:{best.get('targetId') or 'criteria'}"
        hit = bool(best["hardPass"]) and float(best["score"]) >= float(settings["threshold"])
        if hit and key == self.stable_key:
            self._patch(stableHitCount=int(self.snapshot["stableHitCount"]) + 1)
        else:
            self.stable_key = key if hit else ""
            self._patch(stableHitCount=1 if hit else 0)
        if hit:
            self.reject_stable_key = ""
            self.reject_stable_hits = 0
        else:
            # Rejection needs the same per-card hard-failure conclusion on
            # consecutive scans. Merely counting frames can discard a valid
            # island when one factor crosses a segmentation boundary for a
            # single capture frame.
            rejection_signature = "|".join(
                f"{int(candidate['cardIndex'])}:"
                + ",".join(
                    str(factor["key"])
                    for factor in candidate["factors"]
                    if factor["hard"] and not factor["passed"]
                )
                + (":below-threshold" if float(candidate["score"]) < float(settings["threshold"]) else "")
                for candidate in sorted(candidates, key=lambda item: int(item["cardIndex"]))
            )
            if rejection_signature == self.reject_stable_key:
                self.reject_stable_hits += 1
            else:
                self.reject_stable_key = rejection_signature
                self.reject_stable_hits = 1
        stable_hits = int(self.snapshot["stableHitCount"])
        summary = (
            f"地图 {int(best['cardIndex']) + 1} 已通过硬条件，稳定判定 {stable_hits}/{int(settings['stableFrames'])}"
            if hit
            else (
                f"地图 {int(best['cardIndex']) + 1} 当前最高 {float(best['score']) * 100:.1f}%，"
                f"排除结果稳定判定 {self.reject_stable_hits}/{int(settings['stableFrames'])}"
            )
        )
        self._update_active_audit(
            status="reviewing",
            summary=summary,
            decisionCandidates=candidates,
            stableHitCount=stable_hits,
            rejectStableHitCount=self.reject_stable_hits,
            scanSampleCount=self.scan_sample_count,
        )
        if hit and stable_hits >= int(settings["stableFrames"]):
            self._spawn(lambda: self._present_candidate(best))
            return
        if (
            not hit
            and settings["autoReject"]
            and self.reject_stable_hits >= int(settings["stableFrames"])
        ):
            failures = [factor for factor in best["factors"] if factor["hard"] and not factor["passed"]]
            reason = (
                "硬条件未通过：" + "、".join(str(factor["label"]) for factor in failures)
                if failures
                else f"最高条件分 {float(best['score']) * 100:.1f}%，未达到阈值"
            )
            self._spawn(lambda: self._restart(reason))

    def _present_candidate(self, candidate: dict[str, Any]) -> None:
        index = int(candidate["cardIndex"])
        self._update_active_audit(
            status="candidate",
            summary=f"地图 {index + 1} 通过全部硬条件，等待用户确认",
            decision="候选岛等待用户确认",
            selectedCardIndex=index,
            decisionCandidates=self.state()["candidates"],
        )
        self._patch(
            phase="scanning",
            selectedCandidate=candidate,
            lastMessage=f"发现候选岛，正在把光标移到地图 {int(candidate['cardIndex']) + 1}",
        )
        commands: list[dict[str, Any]] = []
        if index >= 2:
            commands.append(press("DOWN", 60, 120))
        if index % 2 == 1:
            commands.append(press("RIGHT", 60, 120))
        self.controller.run(commands)
        self._patch(
            phase="awaitingDecision",
            lastMessage=f"发现候选岛：条件分 {float(candidate['score']) * 100:.1f}%",
        )
        self._log("success", f"第 {index + 1} 张地图通过全部硬条件，等待用户决定")

    @staticmethod
    def _name_value_matches(value: str, score: float, expected: str) -> bool:
        if not expected:
            return not value or score < 0.62
        if score < 0.72:
            return False
        if value == expected:
            return True
        return value.startswith(expected) and len(value) == len(expected) + 1 and value[-1:] in {"l", "I", "1"}

    def _keyboard_frame(self, character: str, scope: str = "full", target_index: int | None = None) -> dict[str, Any]:
        frame, _sequence = self.capture.latest()
        if frame is None:
            raise RuntimeError("采集卡画面尚未就绪，无法识别中文候选栏")
        result = recognize_keyboard_frame(frame, character, scope, target_index)
        result["target"] = character
        result["visionEngine"] = "rapidocr"
        return result

    def _poll_keyboard(
        self,
        character: str,
        predicate: Callable[[dict[str, Any]], bool],
        failure_message: str,
        *,
        stable_hits: int = KEYBOARD_OCR_STABLE_HITS,
        reject_phrases: bool = True,
        attempts: int = 10,
        scope: str = "full",
        target_index: int | None = None,
        retry_limit: int = RECOGNITION_RETRY_LIMIT,
    ) -> dict[str, Any]:
        latest: dict[str, Any] | None = None
        signature = ""
        hits = 0
        last_error: Exception | None = None
        for retry_round in range(retry_limit + 1):
            for _attempt in range(attempts):
                try:
                    latest = self._keyboard_frame(character, scope, target_index)
                    last_error = None
                except Exception as error:  # noqa: BLE001 - capture/OCR hiccups are retryable here
                    last_error = error
                    signature, hits = "", 0
                    time.sleep(KEYBOARD_OCR_POLL_SECONDS)
                    continue
                if reject_phrases and latest["layout"] == "phrases":
                    raise RestartRequired("候选栏进入词语模式，无法安全选择单字")
                if predicate(latest):
                    current_signature = ":".join(
                        str(value)
                        for value in (
                            latest.get("selectedIndex", "none"),
                            latest.get("selectedKey", "none"),
                            latest.get("nameValue", ""),
                            latest.get("index", "miss"),
                        )
                    )
                    if current_signature == signature:
                        hits += 1
                    else:
                        signature, hits = current_signature, 1
                    if hits >= stable_hits:
                        return latest
                else:
                    signature, hits = "", 0
                time.sleep(KEYBOARD_OCR_POLL_SECONDS)
            if retry_round >= retry_limit:
                break
            completed_retry = retry_round + 1
            self._patch(
                lastMessage=(
                    f"{failure_message}；识别结果尚未稳定，"
                    f"正在重新采样 {completed_retry}/{retry_limit}"
                )
            )
            self._log(
                "warning",
                f"{failure_message}；只重试画面识别，不重复发送按键 "
                f"({completed_retry}/{retry_limit})",
            )
            time.sleep(RECOGNITION_RETRY_BASE_SECONDS * (1 + retry_round * 0.5))
        observed = ""
        if latest:
            selected = latest.get("selectedIndex")
            selected_confidence = latest.get("selectedConfidence")
            confidence_text = (
                f"，置信度 {float(selected_confidence) * 100:.0f}%"
                if isinstance(selected_confidence, (int, float))
                else ""
            )
            observed = (
                f"（姓名框“{latest.get('nameValue') or '空'}”，"
                f"高亮候选{'未识别' if selected is None else f'第 {selected + 1} 格'}{confidence_text}，"
                f"键盘光标{latest.get('selectedKey') or '未识别'}）"
            )
        error_detail = f"；最近一次识别异常：{last_error}" if last_error else ""
        raise RestartRequired(
            f"{failure_message}{observed}{error_detail}；已完成 {retry_limit} 轮重试"
        )

    def _enter_name(self) -> None:
        self.handled_name = True
        self._patch(phase="enteringName", lastMessage="正在输入预设名字")
        identity = self._settings()["identity"]
        characters = list(identity["name"].strip())
        self._log("info", f"输入名字：{identity['name']}")
        self._patch(lastMessage="正在清除键盘切页时可能残留的输入")
        self.controller.run([press("B", 45, 45) for _ in range(10)])
        keyboard = self._poll_keyboard(
            characters[0],
            lambda state: self._name_value_matches(state["nameValue"], state["nameScore"], "")
            and state["selectedKey"] is not None
            and state["selectedKeyConfidence"] >= 0.28,
            "OCR 无法确认姓名框已清空或当前键盘光标",
            stable_hits=2,
            reject_phrases=False,
            scope="name",
        )
        cursor = keyboard["selectedKey"]
        confirmed_name = ""
        for index, character in enumerate(characters):
            pinyin = normalize_pinyin(identity["namePinyin"][index])
            self._patch(lastMessage=f"正在输入“{character}”的拼音 {pinyin}")
            commands, cursor = commands_for_pinyin(pinyin, cursor)
            self.controller.run(commands)
            expected = confirmed_name + pinyin
            self._poll_keyboard(
                character,
                lambda state, expected=expected: self._name_value_matches(state["nameValue"], state["nameScore"], expected),
                f"输入拼音后，OCR 未在姓名框读回“{expected}”",
                stable_hits=2,
                reject_phrases=False,
                attempts=7,
                scope="name",
            )
            self._patch(lastMessage=f"本地 OCR 正在定位候选字“{character}”")
            match = self._find_name_candidate_across_pages(character)
            if not match["matched"] or match["index"] is None:
                raise RestartRequired(f"本地 OCR 无法可靠定位候选字“{character}”，不能冒险选择")
            target_index = int(match["index"])
            self._log("info", f"本地 OCR 定位“{character}”为本页第 {target_index + 1} 个候选，置信度 {match['confidence'] * 100:.1f}%")
            self.controller.run(commands_to_candidate_row(cursor))
            keyboard = self._poll_keyboard(
                character,
                lambda state: state["selectedIndex"] is not None and state["selectedConfidence"] >= 0.28,
                f"OCR 未能稳定确认候选栏高亮框，未选择“{character}”",
                stable_hits=2,
                reject_phrases=False,
                attempts=7,
                scope="highlight",
                target_index=target_index,
            )
            self.controller.run(commands_for_candidate_move(int(keyboard["selectedIndex"]), target_index))
            self._poll_keyboard(
                character,
                lambda state, target_index=target_index, character=character: state["layout"] == "singleCharacters"
                and state["matched"]
                and state["index"] == target_index
                and state["selectedIndex"] == target_index
                and state["texts"][target_index] == character
                and state["selectedConfidence"] >= 0.28,
                f"OCR 未能确认当前高亮候选就是“{character}”",
                stable_hits=2,
                reject_phrases=False,
                attempts=8,
                scope="selection",
                target_index=target_index,
            )
            self._patch(lastMessage=f"OCR 已确认高亮“{character}”，正在选择")
            self.controller.press("A", 45, 45)
            confirmed_name += character
            keyboard = self._poll_keyboard(
                character,
                lambda state, expected=confirmed_name: self._name_value_matches(state["nameValue"], state["nameScore"], expected)
                and state["selectedKey"] is not None
                and state["selectedKeyConfidence"] >= 0.28,
                f"选择“{character}”后，OCR 未在姓名框读回“{confirmed_name}”",
                stable_hits=2,
                reject_phrases=False,
                attempts=12,
                scope="name",
            )
            cursor = keyboard["selectedKey"]
            self._log("success", f"姓名框 OCR 已确认：{confirmed_name}")
        self.controller.run([press("PLUS", 80, 500)])
        self._patch(phase="fastForwarding")
        self._arm_transition_retry("nameKeyboard", "PLUS", "提交名字")

    def _find_name_candidate_across_pages(self, character: str) -> dict[str, Any]:
        visited: set[str] = set()
        latest: dict[str, Any] | None = None
        for page_index in range(MAX_CANDIDATE_PAGES):
            self._patch(lastMessage=f"本地 OCR 正在识别“{character}”的第 {page_index + 1} 页候选")
            latest = self._find_stable_name_candidate(character)
            if latest["matched"] and latest["index"] is not None:
                return latest
            visible = "、".join(text for text in latest["texts"] if text) or "未读出文字"
            self._log("info", f"第 {page_index + 1} 页未找到“{character}”（{visible}），切到下一页")
            if latest["pageSignature"] in visited:
                break
            visited.add(latest["pageSignature"])
            if page_index + 1 >= MAX_CANDIDATE_PAGES:
                break
            self.controller.press("R", 80, 520)
        if latest:
            return {**latest, "matched": False, "index": None}
        raise RestartRequired(f"本地 OCR 未返回候选字“{character}”的识别结果")

    def _find_stable_name_candidate(self, character: str) -> dict[str, Any]:
        latest: dict[str, Any] | None = None
        stable_observation = ""
        stable_hits = 0
        for _attempt in range(9):
            latest = self._keyboard_frame(character, "scan")
            if latest["layout"] == "phrases":
                raise RestartRequired(f"候选栏已进入词语模式，无法按单字安全定位“{character}”")
            reliable = latest["matched"] and latest["index"] is not None and latest["confidence"] >= 0.72
            if reliable and latest["confidence"] >= 0.90 and latest["margin"] >= 0.25:
                return latest
            observation = f"{latest['pageSignature']}:{latest['index'] if reliable else 'miss'}"
            if observation == stable_observation:
                stable_hits += 1
            else:
                stable_observation, stable_hits = observation, 1
            if stable_hits >= 2:
                return latest if reliable else {**latest, "matched": False, "index": None}
            time.sleep(KEYBOARD_OCR_POLL_SECONDS)
        if latest:
            return {**latest, "matched": False, "index": None}
        raise RestartRequired(f"OpenCV 未返回候选字“{character}”的识别结果")

    def _poll_birthday(
        self,
        month: int,
        day: int,
        *,
        attempts: int = 5,
        stable_hits_required: int = 2,
        retry_limit: int = RECOGNITION_RETRY_LIMIT,
    ) -> dict[str, Any]:
        stable_hits = 0
        latest: dict[str, Any] | None = None
        last_error: Exception | None = None
        for retry_round in range(retry_limit + 1):
            for _attempt in range(attempts):
                time.sleep(0.16)
                frame, _sequence = self.capture.latest()
                if frame is None:
                    last_error = RuntimeError("采集卡画面尚未就绪")
                    stable_hits = 0
                    continue
                try:
                    latest = recognize_birthday(frame)
                    last_error = None
                except Exception as error:  # noqa: BLE001 - OCR failures are retried without input
                    last_error = error
                    stable_hits = 0
                    continue
                exact = latest["month"] == month and latest["day"] == day and latest["confidence"] >= 0.80
                stable_hits = stable_hits + 1 if exact else 0
                self._patch(
                    lastMessage=(
                        f"正在核对生日：画面为 {latest['month']} 月 {latest['day']} 日"
                        if latest["month"] is not None and latest["day"] is not None
                        else "生日数字尚未可靠识别，正在重试"
                    )
                )
                if stable_hits >= stable_hits_required:
                    return latest
            if retry_round >= retry_limit:
                break
            completed_retry = retry_round + 1
            self._patch(lastMessage=f"生日识别尚未稳定，正在重新采样 {completed_retry}/{retry_limit}")
            self._log(
                "warning",
                f"生日识别尚未稳定；只重试画面识别，不重复发送按键 "
                f"({completed_retry}/{retry_limit})",
            )
            time.sleep(RECOGNITION_RETRY_BASE_SECONDS * (1 + retry_round * 0.5))
        observed = (
            f"{latest['month']} 月 {latest['day']} 日"
            if latest and latest["month"] is not None and latest["day"] is not None
            else "无法可靠读出"
        )
        error_detail = f"；最近一次识别异常：{last_error}" if last_error else ""
        raise RestartRequired(
            f"生日画面校验失败：目标 {month} 月 {day} 日，实际{observed}；"
            f"已完成 {retry_limit} 轮重试，未提交{error_detail}"
        )

    def _enter_birthday(self) -> None:
        self.handled_birthday = True
        settings = self._settings()
        identity = settings["identity"]
        month, day = int(identity["birthMonth"]), int(identity["birthDay"])
        self._patch(phase="enteringBirthday", lastMessage="正在输入预设生日")
        self._log("info", f"输入生日：{month} 月 {day} 日")
        origin = settings["birthdayCursorOrigin"]
        self.controller.run(commands_for_birthday(month, day, int(origin["month"]), int(origin["day"])))
        self._poll_birthday(month, day)
        self._log("success", f"生日画面已核对：{month} 月 {day} 日")
        self.controller.press("PLUS", 80, 500)
        self._patch(phase="fastForwarding")
        self._arm_transition_retry("birthdayPicker", "PLUS", "提交生日")

    def _choose_initial_style(self) -> None:
        self.handled_style = True
        style = self._settings()["identity"]["initialStyle"]
        self._patch(phase="fastForwarding", lastMessage="正在选择预设初始造型")
        self._log("info", f"选择{'左侧' if style == 'left' else '右侧'}初始造型")
        self.controller.run([press("LEFT" if style == "left" else "RIGHT", 80, 140), press("A", 80, 550)])
        self._arm_transition_retry("styleChoice", "A", "提交初始造型", after_ms=550)

    def _confirm_default_appearance(self) -> None:
        self.handled_appearance = True
        self._patch(phase="fastForwarding", lastMessage="正在提交默认形象")
        self._log("info", "形象编辑页已识别，使用 + 快捷键提交默认形象")
        self.controller.press("PLUS", 80, 500)
        self._arm_transition_retry("appearanceEditor", "PLUS", "提交默认形象")

    def _launch_selected_game(self) -> None:
        self._patch(lastMessage="Switch 主界面已识别，正在启动已选中的游戏")
        self._log("info", "Switch 主界面已识别，发送 A 启动当前选中的游戏")
        self.controller.press("A", 80, 500)
        self._arm_transition_retry("homeMenu", "A", "启动已选中的游戏", after_ms=500)

    def _confirm_player_account(self) -> None:
        self._patch(lastMessage="游玩账号页面已识别，正在确认当前选中的账号")
        self._log("info", "游玩账号页面已识别，发送 A 确认当前选中的账号")
        self.controller.press("A", 80, 500)
        self._arm_transition_retry("accountPicker", "A", "确认游玩账号", after_ms=500)

    def _advance_dialogue(self, screen_kind: str) -> None:
        self.last_advance_at = now_ms()
        self._record_advance_press(screen_kind)
        if screen_kind == "dialogue":
            self.controller.press("B", 180, 40)
        else:
            self.controller.press("A", 220, 90)

    def _restart(self, reason: str, audit_status: str = "rejected") -> None:
        self.controller.cancel()
        self._update_active_audit(
            status=audit_status,
            summary=reason,
            decision=reason,
            decisionCandidates=self.state()["candidates"],
        )
        self._patch(phase="restarting", lastMessage=f"{reason}，正在重开游戏")
        self._log("warning", f"{reason}；开始第 {int(self.snapshot['runNumber']) + 1} 轮")
        self.controller.run(RESTART_COMMANDS)
        self._reset_guards()
        self._patch(
            phase="fastForwarding",
            runNumber=int(self.snapshot["runNumber"]) + 1,
            lastMessage="游戏已重开，正在识别对话",
            candidates=[],
            selectedCandidate=None,
            stableHitCount=0,
        )

    def _restart_after_unsafe_state(self, error: RestartRequired) -> None:
        reason = f"危险状态：{error}；已放弃本轮"
        self._restart(reason)

    def _fail(self, error: Exception) -> None:
        message = str(error)
        self.controller.cancel()
        try:
            self._update_active_audit(status="error", summary=message, decision="识别流程异常中止")
        except Exception as audit_error:  # noqa: BLE001
            message = f"{message}；同时无法回写审计状态：{audit_error}"
        self._patch(phase="error", lastMessage=message)
        self._log("error", message)


class BackendRuntime:
    def __init__(
        self,
        data_dir: Path | None = None,
        autostart: bool = False,
        capture_index: int | None = None,
    ) -> None:
        self.instance_id = uuid.uuid4().hex
        self.store = SettingsStore(data_dir)
        devices = discover_capture_devices()
        if capture_index is not None:
            selected = next(
                (
                    device
                    for device in devices
                    if device["index"] == capture_index and device.get("preferred")
                ),
                None,
            )
            if selected is None:
                raise ValueError(f"索引 {capture_index} 不是可用的外接 UVC 采集卡")
            binding = {
                "captureDeviceIndex": capture_index,
                "captureDeviceId": selected.get("id", "") if selected else "",
                "captureDeviceName": selected.get("name", "") if selected else "",
            }
            self.store.update(binding)
        else:
            current = self.store.get()
            selected, _error = resolve_capture_device(current, devices)
            if selected is None:
                selected = next((device for device in devices if device.get("preferred")), None)
            if selected is not None:
                self.store.update(
                    {
                        "captureDeviceIndex": selected["index"],
                        "captureDeviceId": selected.get("id", ""),
                        "captureDeviceName": selected.get("name", ""),
                    }
                )
        self._lock = threading.RLock()
        self._logs: deque[dict[str, Any]] = deque(maxlen=200)
        self._next_log_id = 1
        self._snapshot = copy.deepcopy(INITIAL_RUNTIME)
        self.controller = ControllerClient(self._controller_event)
        self.capture = CaptureManager(self.store.get, self._capture_event)
        self.audits = SelectionAuditStore(self.store.data_dir)
        self.engine = AutomationEngine(
            self.store.get,
            self.capture,
            self.controller,
            self.audits,
            self._set_snapshot,
            self.add_log,
        )
        self.capture.start()
        self.engine.start_worker()
        if self.store.get().get("autoConnectController", True):
            threading.Thread(target=self._auto_pair, name="controller-auto-pair", daemon=True).start()
        if autostart:
            threading.Thread(target=self._delayed_start, name="automation-autostart", daemon=True).start()

    def shutdown(self) -> None:
        self.engine.shutdown()
        self.capture.stop()

    def _auto_pair(self) -> None:
        time.sleep(0.4)
        deadline = time.monotonic() + 30
        last_error: Exception | None = None
        while time.monotonic() < deadline and self.store.get().get("autoConnectController", True):
            try:
                self.controller.start_pairing()
                return
            except Exception as error:  # noqa: BLE001
                last_error = error
                time.sleep(1)
        if last_error is not None:
            self.add_log("warning", f"手柄自动连接未完成：{last_error}")

    def _delayed_start(self) -> None:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            settings = self.store.get()
            capture_ready = self.capture.status()["connected"]
            controller_ready = settings["dryRun"] or self.controller.connected
            if capture_ready and controller_ready:
                try:
                    self.engine.start()
                except Exception as error:  # noqa: BLE001
                    self.add_log("error", f"后端自动启动失败：{error}")
                return
            time.sleep(0.5)
        self.add_log("error", "后端自动启动超时：采集卡或手柄未就绪")

    def _set_snapshot(self, snapshot: dict[str, Any]) -> None:
        with self._lock:
            self._snapshot = copy.deepcopy(snapshot)

    def add_log(self, level: str, message: str) -> None:
        with self._lock:
            self._logs.appendleft(
                {"id": self._next_log_id, "at": now_ms(), "level": level, "message": message}
            )
            self._next_log_id += 1

    def _controller_event(self, kind: str, message: str) -> None:
        self.add_log("error" if kind == "error" else "info", message)

    def _capture_event(self, kind: str, message: str) -> None:
        level = "error" if kind == "error" else "warning" if kind == "warning" else "info"
        self.add_log(level, message)

    def state(self) -> dict[str, Any]:
        with self._lock:
            snapshot = copy.deepcopy(self._snapshot)
            logs = copy.deepcopy(list(self._logs))
        return {
            "ok": True,
            "mode": "headless-backend",
            "version": "3.2",
            "instanceId": self.instance_id,
            "runtime": snapshot,
            "capture": self.capture.status(),
            "controller": self.controller.status(),
            "settings": self.store.get(),
            "logs": logs,
        }

    def capture_devices(self) -> dict[str, Any]:
        settings = self.store.get()
        devices = [device for device in discover_capture_devices() if device.get("preferred")]
        return {
            "devices": devices,
            "selectedIndex": int(settings["captureDeviceIndex"]),
            "selectedId": settings.get("captureDeviceId", ""),
            "selectedName": settings.get("captureDeviceName", ""),
        }

    def audit_history(self) -> dict[str, Any]:
        return {"audits": self.audits.list(), "limit": self.audits.limit}

    def audit(self, audit_id: str) -> dict[str, Any]:
        return self.audits.get(audit_id)

    def audit_image(self, audit_id: str, filename: str) -> Path:
        return self.audits.image_path(audit_id, filename)

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        before = self.store.get()
        payload = copy.deepcopy(payload)
        incoming_id = str(payload.get("captureDeviceId") or "").strip()
        incoming_name = str(payload.get("captureDeviceName") or "").strip()
        devices = discover_capture_devices()
        if incoming_id or incoming_name:
            selected, error = resolve_capture_device(payload, devices)
            if selected is None:
                raise ValueError(error or "已绑定的采集卡当前不在线")
            payload["captureDeviceIndex"] = selected["index"]
            payload["captureDeviceId"] = selected.get("id", "")
            payload["captureDeviceName"] = selected.get("name", "")
        elif "captureDeviceIndex" in payload and int(payload["captureDeviceIndex"]) != before["captureDeviceIndex"]:
            requested_index = int(payload["captureDeviceIndex"])
            selected = next(
                (
                    device
                    for device in devices
                    if device["index"] == requested_index and device.get("preferred")
                ),
                None,
            )
            if selected is None:
                raise ValueError(f"采集设备索引 {requested_index} 当前不存在")
            payload["captureDeviceId"] = selected.get("id", "")
            payload["captureDeviceName"] = selected.get("name", "")
        settings = self.store.update(payload)
        capture_keys = {
            "captureDeviceIndex",
            "captureDeviceId",
            "captureDeviceName",
            "captureWidth",
            "captureHeight",
            "captureFps",
        }
        if any(before.get(key) != settings.get(key) for key in capture_keys):
            self.capture.reconfigure()
        self.controller.set_dry_run(bool(settings["dryRun"]))
        self.add_log("success", "配置已保存到后端；关闭网页后仍然生效")
        return settings

    def action(self, name: str, instance_id: str | None = None) -> dict[str, Any]:
        actions: dict[str, Callable[[], Any]] = {
            "start": self.engine.start,
            "pause": self.engine.pause,
            "resume": self.engine.resume,
            "stop": self.engine.stop,
            "accept": self.engine.accept_candidate,
            "reject": self.engine.reject_candidate,
            "controller-connect": self.controller.start_pairing,
            "controller-disconnect": self.controller.stop_pairing,
            "capture-reconnect": self.capture.reconfigure,
        }
        if name not in actions:
            raise ValueError(f"未知后端动作：{name}")
        if name == "start" and instance_id != self.instance_id:
            raise ValueError("启动请求来自旧的后端会话，请刷新页面后重试")
        actions[name]()
        return self.state()

    def clear_logs(self) -> None:
        with self._lock:
            self._logs.clear()

    def jpeg(self, width: int = 1280, quality: int = 78) -> bytes:
        frame, _sequence = self.capture.latest()
        if frame is None:
            raise RuntimeError("后端采集画面尚未就绪")
        if width > 0 and frame.shape[1] > width:
            height = max(1, round(frame.shape[0] * width / frame.shape[1]))
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("无法编码监看画面")
        return encoded.tobytes()
