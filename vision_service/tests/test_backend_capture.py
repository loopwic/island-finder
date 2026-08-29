from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import backend
from backend import (
    ADVANCE_STALL_PRESS_LIMIT,
    AutomationEngine,
    BackendRuntime,
    CALIBRATED_CARD_REGIONS,
    DEFAULT_SETTINGS,
    LEGACY_CARD_REGIONS,
    MAP_RENDER_MIN_SATURATION_COVERAGE,
    RECOGNITION_RETRY_LIMIT,
    RestartRequired,
    SettingsStore,
    TRANSITION_RETRY_LIMIT,
    commands_for_english_character,
    _default_data_dir,
    _devices_from_system_profiler,
    _usb_details_from_ioreg,
    effective_capture_mode,
    name_input_mode,
    resolve_capture_device,
    validate_name,
    validate_settings,
)


def _camera_payload(order: tuple[str, ...] = ("FaceTime HD Camera", "Display capture-UVC05")):
    records = {
        "FaceTime HD Camera": {
            "_name": "FaceTime HD Camera",
            "spcamera_model-id": "FaceTime HD Camera",
            "spcamera_unique-id": "facetime-id",
        },
        "Display capture-UVC05": {
            "_name": "Display capture-UVC05",
            "spcamera_model-id": "UVC Camera VendorID_7649 ProductID_61717",
            "spcamera_unique-id": "location-dependent-id",
        },
    }
    return {"SPCameraDataType": [records[name] for name in order]}


def test_default_data_directory_is_inside_the_project(monkeypatch):
    monkeypatch.delenv("ISLAND_FINDER_DATA_DIR", raising=False)

    assert _default_data_dir() == Path(__file__).resolve().parents[2] / "data"


def test_data_directory_environment_override_is_still_supported(monkeypatch, tmp_path):
    custom = tmp_path / "custom-data"
    monkeypatch.setenv("ISLAND_FINDER_DATA_DIR", str(custom))

    assert _default_data_dir() == custom.resolve()


def test_camera_profiler_marks_the_uvc_capture_and_mjpeg_transport():
    devices = _devices_from_system_profiler(_camera_payload())

    assert [device["index"] for device in devices] == [0, 1]
    assert devices[1]["preferred"] is True
    assert devices[1]["transportCodec"] == "MJPEG"
    assert devices[1]["avFoundationId"] == "location-dependent-id"


def test_ioreg_parser_reads_usb_link_and_hardware_serial():
    output = '''
    +-o Display capture-UVC05@02140000  <class IOUSBHostDevice>
      {
        "UsbLinkSpeed" = 480000000
        "USB Serial Number" = "EXAMPLE-SERIAL"
      }
    '''

    details = _usb_details_from_ioreg(output, ["Display capture-UVC05"])

    assert details == {
        "Display capture-UVC05": {
            "usbLinkMbps": 480,
            "usbSerialNumber": "EXAMPLE-SERIAL",
        }
    }


def test_hardware_binding_survives_avfoundation_index_changes():
    devices = _devices_from_system_profiler(
        _camera_payload(("Display capture-UVC05", "FaceTime HD Camera"))
    )
    capture = devices[0]
    capture.update(
        {
            "id": "uvc:UVC Camera VendorID_7649 ProductID_61717:EXAMPLE-SERIAL",
            "usbSerialNumber": "EXAMPLE-SERIAL",
        }
    )
    settings = {
        "captureDeviceId": capture["id"],
        "captureDeviceName": capture["name"],
        "captureDeviceIndex": 9,
    }

    selected, error = resolve_capture_device(settings, devices)

    assert error is None
    assert selected is capture
    assert selected["index"] == 0


def test_builtin_camera_binding_is_rejected():
    devices = _devices_from_system_profiler(_camera_payload())
    settings = {
        "captureDeviceId": "facetime-id",
        "captureDeviceName": "FaceTime HD Camera",
        "captureDeviceIndex": 0,
    }

    selected, error = resolve_capture_device(settings, devices)

    assert selected is None
    assert error is not None
    assert "不是外接 UVC 采集卡" in error


def test_usb2_mjpeg_mode_is_not_silently_downscaled():
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings.update({"captureWidth": 1920, "captureHeight": 1080, "captureFps": 30})
    device = {
        "name": "Display capture-UVC05",
        "usbLinkMbps": 480,
        "transportCodec": "MJPEG",
    }

    assert effective_capture_mode(settings, device) == (1920, 1080, 30, None)


def test_null_capture_binding_is_normalized_to_empty_strings():
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings.update({"captureDeviceId": None, "captureDeviceName": None})

    validated = validate_settings(settings)

    assert validated["captureDeviceId"] == ""
    assert validated["captureDeviceName"] == ""


def test_long_windows_directshow_identity_is_not_truncated() -> None:
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    directshow_id = "dshow:7537:6165:" + "usb-instance-segment#" * 20
    settings["captureDeviceId"] = directshow_id

    validated = validate_settings(settings)

    assert len(directshow_id) > 200
    assert validated["captureDeviceId"] == directshow_id


def test_uvc_capture_defaults_to_full_30_fps_preview():
    assert DEFAULT_SETTINGS["captureFps"] == 30


NAME_INPUT_CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts" / "name-input-cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", NAME_INPUT_CASES, ids=lambda case: case["name"] or "empty")
def test_name_input_contract_is_shared_with_the_frontend(case):
    identity = {"name": case["name"], "namePinyin": case["pinyin"]}

    assert name_input_mode(identity) == case["mode"]
    if case["valid"]:
        assert validate_name(identity) == case["mode"]
    else:
        with pytest.raises(ValueError):
            validate_name(identity)


def test_settings_normalize_english_names_to_the_lowercase_keyboard_output():
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["identity"]["name"] = "Nook"

    validated = validate_settings(settings)

    assert validated["identity"]["name"] == "nook"


def test_english_character_plan_uses_the_observed_keyboard_cursor():
    commands, cursor = commands_for_english_character("K", "1")

    assert cursor == "k"
    assert commands[-1]["button"] == "A"
    assert all(command["button"] != "PLUS" for command in commands)


def test_english_name_flow_reads_back_each_letter_and_never_enters_candidate_selection():
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["identity"].update({"name": "nook", "namePinyin": []})
    command_batches: list[list[dict[str, object]]] = []
    controller = SimpleNamespace(run=lambda commands: command_batches.append(commands))
    engine = AutomationEngine(
        lambda: settings,
        SimpleNamespace(),  # type: ignore[arg-type]
        controller,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        lambda _snapshot: None,
        lambda _level, _message: None,
    )
    observations = iter(
        [
            {"nameValue": "", "nameScore": 0.0, "selectedKey": "1", "selectedKeyConfidence": 0.9},
            {"nameValue": "n", "nameScore": 0.95, "selectedKey": "n", "selectedKeyConfidence": 0.9},
            {"nameValue": "no", "nameScore": 0.95, "selectedKey": "o", "selectedKeyConfidence": 0.9},
            {"nameValue": "noo", "nameScore": 0.95, "selectedKey": "o", "selectedKeyConfidence": 0.9},
            {"nameValue": "nook", "nameScore": 0.95, "selectedKey": "k", "selectedKeyConfidence": 0.9},
        ]
    )

    def poll_keyboard(_character, predicate, _failure_message, **_kwargs):
        state = next(observations)
        assert predicate(state)
        return state

    engine._poll_keyboard = poll_keyboard  # type: ignore[method-assign]
    engine._find_name_candidate_across_pages = (  # type: ignore[method-assign]
        lambda _character: pytest.fail("英文姓名不应进入中文候选栏")
    )

    engine._enter_name()

    buttons = [command["button"] for batch in command_batches for command in batch]
    assert buttons.count("B") == 10
    assert buttons.count("A") == 4
    assert buttons.count("PLUS") == 1
    assert "R" not in buttons
    assert engine.transition_retry is not None
    assert engine.transition_retry["screenKind"] == "nameKeyboard"


def test_calibrated_map_regions_contain_measured_1080p_map_bounds_with_small_padding():
    measured = [
        (484, 319, 432, 264),
        (1004, 324, 432, 261),
        (485, 622, 429, 257),
        (1005, 619, 431, 263),
    ]
    for region, (map_x, map_y, map_width, map_height) in zip(
        CALIBRATED_CARD_REGIONS,
        measured,
        strict=True,
    ):
        x = round(region["x"] * 1920)
        y = round(region["y"] * 1080)
        width = round(region["width"] * 1920)
        height = round(region["height"] * 1080)
        assert 0 <= map_x - x <= 8
        assert 0 <= map_y - y <= 8
        assert 0 <= x + width - (map_x + map_width) <= 8
        assert 0 <= y + height - (map_y + map_height) <= 8


def test_settings_store_migrates_legacy_map_regions(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"cardRegions": LEGACY_CARD_REGIONS}),
        encoding="utf-8",
    )

    store = SettingsStore(tmp_path)

    assert store.get()["cardRegions"] == CALIBRATED_CARD_REGIONS
    assert json.loads(settings_path.read_text(encoding="utf-8"))["cardRegions"] == CALIBRATED_CARD_REGIONS


def test_settings_store_replaces_browser_custom_map_regions(tmp_path):
    custom_regions = copy.deepcopy(LEGACY_CARD_REGIONS)
    custom_regions[0]["x"] += 0.01
    (tmp_path / "settings.json").write_text(
        json.dumps({"cardRegions": custom_regions}),
        encoding="utf-8",
    )

    store = SettingsStore(tmp_path)

    assert store.get()["cardRegions"] == CALIBRATED_CARD_REGIONS
    persisted = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert persisted["cardRegions"] == CALIBRATED_CARD_REGIONS


def test_settings_store_drops_obsolete_browser_anchor_fields(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "cardRegions": CALIBRATED_CARD_REGIONS,
                "anchorThreshold": 0.84,
                "anchorRegions": {"mapScreen": {"x": 0, "y": 0, "width": 1, "height": 1}},
                "anchors": {"mapScreen": {"capturedAt": "legacy"}},
            }
        ),
        encoding="utf-8",
    )

    store = SettingsStore(tmp_path)

    assert set(store.get()) == set(DEFAULT_SETTINGS)
    persisted = json.loads(settings_path.read_text(encoding="utf-8"))
    assert set(persisted) == set(DEFAULT_SETTINGS)


def test_settings_update_cannot_restore_exact_legacy_map_regions(tmp_path):
    store = SettingsStore(tmp_path)

    updated = store.update({"cardRegions": copy.deepcopy(LEGACY_CARD_REGIONS)})

    assert updated["cardRegions"] == CALIBRATED_CARD_REGIONS
    persisted = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert persisted["cardRegions"] == CALIBRATED_CARD_REGIONS


def _rendered_map_frame() -> np.ndarray:
    frame = np.full((360, 640, 3), 218, dtype=np.uint8)
    colors = ((190, 155, 45), (165, 185, 50), (180, 145, 35), (155, 175, 42))
    for region, color in zip(CALIBRATED_CARD_REGIONS, colors, strict=True):
        x0 = round(region["x"] * frame.shape[1])
        y0 = round(region["y"] * frame.shape[0])
        x1 = round((region["x"] + region["width"]) * frame.shape[1])
        y1 = round((region["y"] + region["height"]) * frame.shape[0])
        frame[y0:y1, x0:x1] = color
        cv2.line(frame, (x0, y0), (x1 - 1, y1 - 1), (70, 150, 55), 5)
        cv2.line(frame, (x1 - 1, y0), (x0, y1 - 1), (175, 185, 75), 5)
    return frame


def test_map_gate_rejects_frozen_crossfade_then_accepts_stable_render():
    rendered = _rendered_map_frame()
    neutral = np.full_like(rendered, 218)
    crossfade = cv2.addWeighted(rendered, 0.20, neutral, 0.80, 0)
    engine = AutomationEngine(
        lambda: {},
        None,  # type: ignore[arg-type]
        SimpleNamespace(cancel=lambda: None),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        lambda _snapshot: None,
        lambda _level, _message: None,
    )

    first = engine._map_frame_ready(crossfade, CALIBRATED_CARD_REGIONS, observed_at=0.0)
    frozen = engine._map_frame_ready(crossfade, CALIBRATED_CARD_REGIONS, observed_at=1.0)
    changed = engine._map_frame_ready(rendered, CALIBRATED_CARD_REGIONS, observed_at=1.1)
    stable_once = engine._map_frame_ready(rendered, CALIBRATED_CARD_REGIONS, observed_at=1.4)
    stable_twice = engine._map_frame_ready(rendered, CALIBRATED_CARD_REGIONS, observed_at=1.7)

    assert first[0] is False
    assert frozen[0] is False
    assert frozen[1] < MAP_RENDER_MIN_SATURATION_COVERAGE
    assert changed[0] is False
    assert stable_once[0] is False
    assert stable_twice[0] is True
    assert stable_twice[1] >= MAP_RENDER_MIN_SATURATION_COVERAGE


def _transition_retry_engine():
    presses: list[str] = []
    cancels: list[bool] = []
    controller = SimpleNamespace(
        cancel=lambda: cancels.append(True),
        press=lambda button, _hold_ms, _after_ms: presses.append(button),
        run=lambda _commands: presses.append("RESTART"),
    )
    engine = AutomationEngine(
        lambda: {},
        None,  # type: ignore[arg-type]
        controller,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        lambda _snapshot: None,
        lambda _level, _message: None,
    )

    def run_now(action):
        action()
        return True

    engine._spawn = run_now  # type: ignore[method-assign]
    return engine, presses, cancels


def test_transition_retries_same_confirmed_page_three_times_then_restarts():
    engine, presses, cancels = _transition_retry_engine()
    engine._arm_transition_retry(
        "nameKeyboard",
        "PLUS",
        "提交名字",
        observed_at=0.0,
    )

    assert engine._maybe_retry_transition("nameKeyboard", observed_at=1.19) is True
    assert presses == []
    assert engine._maybe_retry_transition("nameKeyboard", observed_at=1.20) is True
    assert engine._maybe_retry_transition("nameKeyboard", observed_at=3.00) is True
    assert engine._maybe_retry_transition("nameKeyboard", observed_at=5.40) is True
    assert presses == ["PLUS"] * TRANSITION_RETRY_LIMIT

    assert engine._maybe_retry_transition("nameKeyboard", observed_at=8.40) is True
    assert engine.state()["phase"] == "fastForwarding"
    assert engine.state()["lastMessage"] == "游戏已重开，正在识别对话"
    assert presses == ["PLUS"] * TRANSITION_RETRY_LIMIT + ["RESTART"]
    assert cancels == [True]


def test_transition_retry_clears_as_soon_as_page_changes():
    engine, presses, cancels = _transition_retry_engine()
    engine._arm_transition_retry(
        "birthdayPicker",
        "PLUS",
        "提交生日",
        observed_at=0.0,
    )

    assert engine._maybe_retry_transition("choiceDialog", observed_at=0.5) is False
    assert engine.transition_retry is None
    assert presses == []
    assert cancels == []


def test_home_menu_launches_selected_game_and_arms_bounded_retry():
    engine, presses, _cancels = _transition_retry_engine()
    engine._patch(phase="fastForwarding")
    screen = {"kind": "homeMenu", "confidence": 0.95, "signals": {}}
    signature = np.zeros((54, 96), dtype=np.uint8)

    engine._observe(screen, [], signature)
    assert presses == []
    engine._observe(screen, [], signature)

    assert presses == ["A"]
    assert engine.transition_retry is not None
    assert engine.transition_retry["screenKind"] == "homeMenu"
    assert engine.transition_retry["retryCount"] == 0


def test_account_picker_confirms_current_player_and_arms_bounded_retry():
    engine, presses, _cancels = _transition_retry_engine()
    engine._patch(phase="fastForwarding")
    screen = {"kind": "accountPicker", "confidence": 0.95, "signals": {}}
    signature = np.zeros((54, 96), dtype=np.uint8)

    engine._observe(screen, [], signature)
    assert presses == []
    engine._observe(screen, [], signature)

    assert presses == ["A"]
    assert engine.transition_retry is not None
    assert engine.transition_retry["screenKind"] == "accountPicker"
    assert engine.transition_retry["retryCount"] == 0


def test_static_advance_page_trips_watchdog_after_bounded_presses():
    engine, _presses, _cancels = _transition_retry_engine()
    signature = np.full((54, 96), 127, dtype=np.uint8)

    assert engine._advance_page_stalled("dialogue", signature) is False
    for _ in range(ADVANCE_STALL_PRESS_LIMIT):
        engine._record_advance_press("dialogue")

    assert engine._advance_page_stalled("dialogue", signature) is True

    changed = np.full((54, 96), 180, dtype=np.uint8)
    assert engine._advance_page_stalled("dialogue", changed) is False
    assert engine.advance_watch_presses == 0


def _recognition_retry_engine():
    logs: list[tuple[str, str]] = []
    engine = AutomationEngine(
        lambda: {},
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(cancel=lambda: None),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        lambda _snapshot: None,
        lambda level, message: logs.append((level, message)),
    )
    return engine, logs


def _keyboard_observation(
    *,
    selected_index: int | None,
    selected_confidence: float,
    layout: str = "singleCharacters",
):
    return {
        "layout": layout,
        "selectedIndex": selected_index,
        "selectedConfidence": selected_confidence,
        "selectedKey": "a",
        "nameValue": "明zao",
        "index": 10,
    }


def _candidate_page(
    signature: str,
    *,
    matched: bool = False,
    index: int | None = None,
    layout: str = "singleCharacters",
):
    texts = [""] * 15
    if matched and index is not None:
        texts[index] = "藻"
    return {
        "layout": layout,
        "matched": matched,
        "index": index,
        "confidence": 0.96 if matched else 0.0,
        "margin": 0.45 if matched else 0.0,
        "texts": texts,
        "pageSignature": signature,
    }


def test_chinese_candidate_search_pages_once_and_returns_the_later_match():
    engine, logs = _recognition_retry_engine()
    presses: list[str] = []
    engine.controller = SimpleNamespace(
        press=lambda button, _hold_ms, _after_ms: presses.append(button)
    )  # type: ignore[assignment]
    stable_pages = iter(
        [_candidate_page("page-1"), _candidate_page("page-2", matched=True, index=4)]
    )
    engine._find_stable_name_candidate = lambda _character: next(stable_pages)  # type: ignore[method-assign]
    engine._wait_for_candidate_page_change = (  # type: ignore[method-assign]
        lambda _character, _signature: _candidate_page("page-2")
    )

    result = engine._find_name_candidate_across_pages("藻")

    assert result["index"] == 4
    assert presses == ["R"]
    assert any("切到下一页" in message for _level, message in logs)


def test_candidate_page_change_waits_for_two_stable_new_frames(monkeypatch):
    monkeypatch.setattr(backend.time, "sleep", lambda _seconds: None)
    engine, _logs = _recognition_retry_engine()
    observations = iter(
        [
            _candidate_page("page-1"),
            _candidate_page("page-2"),
            _candidate_page("page-2"),
        ]
    )
    engine._keyboard_frame = lambda *_args: next(observations)  # type: ignore[method-assign]

    result = engine._wait_for_candidate_page_change("藻", "page-1")

    assert result["pageSignature"] == "page-2"


def test_candidate_page_change_retries_capture_errors_without_repressing_r(monkeypatch):
    monkeypatch.setattr(backend.time, "sleep", lambda _seconds: None)
    engine, logs = _recognition_retry_engine()
    calls = 0

    def keyboard_frame(*_args):
        nonlocal calls
        calls += 1
        if calls <= 12:
            raise RuntimeError("temporary capture timeout")
        return _candidate_page("page-2")

    engine._keyboard_frame = keyboard_frame  # type: ignore[method-assign]

    result = engine._wait_for_candidate_page_change("藻", "page-1")

    assert result["pageSignature"] == "page-2"
    assert len(logs) == 1
    assert "不重复按 R" in logs[0][1]


def test_candidate_page_change_stops_immediately_on_phrase_layout(monkeypatch):
    monkeypatch.setattr(backend.time, "sleep", lambda _seconds: None)
    engine, _logs = _recognition_retry_engine()
    engine._keyboard_frame = (  # type: ignore[method-assign]
        lambda *_args: _candidate_page("phrase-page", layout="phrases")
    )

    with pytest.raises(RestartRequired, match="翻页后进入词语模式"):
        engine._wait_for_candidate_page_change("藻", "page-1")


def test_keyboard_recognition_retries_low_confidence_without_replaying_input(monkeypatch):
    monkeypatch.setattr(backend.time, "sleep", lambda _seconds: None)
    engine, logs = _recognition_retry_engine()
    observations = iter(
        [
            _keyboard_observation(selected_index=10, selected_confidence=0.12),
            _keyboard_observation(selected_index=10, selected_confidence=0.18),
            _keyboard_observation(selected_index=10, selected_confidence=0.64),
            _keyboard_observation(selected_index=10, selected_confidence=0.66),
        ]
    )
    engine._keyboard_frame = lambda *_args: next(observations)  # type: ignore[method-assign]

    result = engine._poll_keyboard(
        "藻",
        lambda state: state["selectedConfidence"] >= 0.28,
        "未能稳定确认高亮",
        attempts=2,
        stable_hits=2,
    )

    assert result["selectedIndex"] == 10
    assert len(logs) == 1
    assert "只重试画面识别，不重复发送按键" in logs[0][1]
    assert f"1/{RECOGNITION_RETRY_LIMIT}" in logs[0][1]


def test_keyboard_recognition_recovers_from_a_transient_frame_error(monkeypatch):
    monkeypatch.setattr(backend.time, "sleep", lambda _seconds: None)
    engine, logs = _recognition_retry_engine()
    observations = iter(
        [
            RuntimeError("temporary capture timeout"),
            _keyboard_observation(selected_index=10, selected_confidence=0.65),
            _keyboard_observation(selected_index=10, selected_confidence=0.67),
        ]
    )

    def keyboard_frame(*_args):
        observation = next(observations)
        if isinstance(observation, Exception):
            raise observation
        return observation

    engine._keyboard_frame = keyboard_frame  # type: ignore[method-assign]

    result = engine._poll_keyboard(
        "藻",
        lambda state: state["selectedConfidence"] >= 0.28,
        "未能稳定确认高亮",
        attempts=2,
        stable_hits=2,
    )

    assert result["selectedIndex"] == 10
    assert len(logs) == 1


def test_keyboard_phrase_layout_still_stops_immediately(monkeypatch):
    monkeypatch.setattr(backend.time, "sleep", lambda _seconds: None)
    engine, logs = _recognition_retry_engine()
    calls = 0

    def phrase_frame(*_args):
        nonlocal calls
        calls += 1
        return _keyboard_observation(
            selected_index=0,
            selected_confidence=0.90,
            layout="phrases",
        )

    engine._keyboard_frame = phrase_frame  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="候选栏进入词语模式"):
        engine._poll_keyboard(
            "藻",
            lambda _state: True,
            "不应进入普通重试",
            attempts=2,
        )

    assert calls == 1
    assert logs == []


def test_keyboard_recognition_exhausts_exactly_three_retry_rounds(monkeypatch):
    monkeypatch.setattr(backend.time, "sleep", lambda _seconds: None)
    engine, logs = _recognition_retry_engine()
    calls = 0

    def uncertain_frame(*_args):
        nonlocal calls
        calls += 1
        return _keyboard_observation(selected_index=10, selected_confidence=0.10)

    engine._keyboard_frame = uncertain_frame  # type: ignore[method-assign]

    with pytest.raises(RestartRequired, match=f"已完成 {RECOGNITION_RETRY_LIMIT} 轮重试"):
        engine._poll_keyboard(
            "藻",
            lambda state: state["selectedConfidence"] >= 0.28,
            "未能稳定确认高亮",
            attempts=2,
            stable_hits=2,
        )

    assert calls == 2 * (RECOGNITION_RETRY_LIMIT + 1)
    assert len(logs) == RECOGNITION_RETRY_LIMIT


def test_birthday_recognition_retries_observation_only(monkeypatch):
    monkeypatch.setattr(backend.time, "sleep", lambda _seconds: None)
    engine, logs = _recognition_retry_engine()
    frame = np.zeros((80, 120, 3), dtype=np.uint8)
    engine.capture = SimpleNamespace(latest=lambda: (frame, 1))  # type: ignore[assignment]
    observations = iter(
        [
            {"month": None, "day": None, "confidence": 0.0},
            {"month": 4, "day": 8, "confidence": 0.92},
            {"month": 4, "day": 8, "confidence": 0.93},
        ]
    )
    monkeypatch.setattr(backend, "recognize_birthday", lambda _frame: next(observations))

    result = engine._poll_birthday(4, 8, attempts=1, stable_hits_required=2)

    assert result["month"] == 4
    assert result["day"] == 8
    assert len(logs) == 2
    assert all("不重复发送按键" in message for _level, message in logs)


def test_spawn_turns_a_dangerous_recognition_state_into_a_restart():
    engine, _logs = _recognition_retry_engine()
    restarted = threading.Event()
    reasons: list[str] = []

    def restart_after(error: RestartRequired):
        reasons.append(str(error))
        restarted.set()

    def unsafe_action():
        raise RestartRequired("候选栏进入词语模式")

    engine._restart_after_unsafe_state = restart_after  # type: ignore[method-assign]

    assert engine._spawn(unsafe_action) is True
    assert restarted.wait(1.0) is True
    assert reasons == ["候选栏进入词语模式"]
    assert engine.state()["phase"] != "error"


def _runtime_action_harness():
    calls: list[str] = []
    runtime = BackendRuntime.__new__(BackendRuntime)
    runtime.instance_id = "current-instance"
    runtime._lock = threading.RLock()
    runtime._start_authorization = None
    runtime.engine = SimpleNamespace(
        start=lambda: calls.append("start"),
        pause=lambda: calls.append("pause"),
        resume=lambda: calls.append("resume"),
        stop=lambda: calls.append("stop"),
        accept_candidate=lambda: calls.append("accept"),
        reject_candidate=lambda: calls.append("reject"),
    )
    runtime.controller = SimpleNamespace(
        start_pairing=lambda: calls.append("controller-connect"),
        stop_pairing=lambda: calls.append("controller-disconnect"),
    )
    runtime.capture = SimpleNamespace(reconfigure=lambda: calls.append("capture-reconnect"))
    runtime.state = lambda: {"ok": True}  # type: ignore[method-assign]
    return runtime, calls


def test_stale_frontend_session_cannot_start_new_backend_instance():
    runtime, calls = _runtime_action_harness()

    with pytest.raises(ValueError, match="旧的后端会话"):
        runtime.arm_start("stale-instance")

    assert calls == []
    token = runtime.arm_start("current-instance")["startToken"]
    assert runtime.action("start", "current-instance", token) == {"ok": True}
    assert calls == ["start"]


def test_start_requires_fresh_single_use_page_confirmation():
    runtime, calls = _runtime_action_harness()

    with pytest.raises(ValueError, match="未经当前页面确认"):
        runtime.action("start", "current-instance")

    token = runtime.arm_start("current-instance")["startToken"]
    with pytest.raises(ValueError, match="未经当前页面确认"):
        runtime.action("start", "current-instance", "wrong-token")
    with pytest.raises(ValueError, match="未经当前页面确认"):
        runtime.action("start", "current-instance", token)

    assert calls == []


def test_emergency_stop_does_not_require_instance_token():
    runtime, calls = _runtime_action_harness()

    assert runtime.action("stop") == {"ok": True}
    assert calls == ["stop"]
