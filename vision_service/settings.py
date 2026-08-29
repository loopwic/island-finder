from __future__ import annotations

import copy
import json
import os
import re
import threading
from pathlib import Path
from typing import Any


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


def validate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    identity = settings.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("身份配置无效")
    normalized_name = str(identity.get("name", "")).strip()[:10]
    identity["name"] = (
        normalized_name.lower()
        if re.fullmatch(r"[A-Za-z]+", normalized_name)
        else normalized_name
    )
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
    settings["captureDeviceIndex"] = max(
        0,
        min(2_048, int(settings.get("captureDeviceIndex", 0))),
    )
    settings["captureDeviceId"] = str(settings.get("captureDeviceId") or "")[:1_024]
    settings["captureDeviceName"] = str(settings.get("captureDeviceName") or "")[:200]
    settings["captureWidth"] = max(640, min(3840, int(settings.get("captureWidth", 1920))))
    settings["captureHeight"] = max(360, min(2160, int(settings.get("captureHeight", 1080))))
    settings["captureFps"] = max(3, min(30, int(settings.get("captureFps", 30))))
    for key in ("autoReject", "dryRun", "autoConnectController"):
        settings[key] = bool(settings.get(key, DEFAULT_SETTINGS[key]))

    # Map crops are backend-owned measured coordinates. Browser settings are
    # deliberately ignored so stale UI state cannot corrupt audit evidence.
    settings["cardRegions"] = copy.deepcopy(CALIBRATED_CARD_REGIONS)
    for region in settings["cardRegions"]:
        if not isinstance(region, dict):
            raise ValueError("地图识别框无效")
        x, y, width, height = (float(region[key]) for key in ("x", "y", "width", "height"))
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
            raise ValueError("地图识别框必须位于画面内")
        region.update({"x": x, "y": y, "width": width, "height": height})
    return {key: copy.deepcopy(settings[key]) for key in DEFAULT_SETTINGS}


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
