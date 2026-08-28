from __future__ import annotations

from types import SimpleNamespace

import cv2

from backend import (
    _devices_from_camera_infos,
    _devices_from_system_profiler,
    _opencv_capture_backend,
    resolve_capture_device,
)


def _camera_payload() -> dict[str, object]:
    return {
        "SPCameraDataType": [
            {
                "_name": "FaceTime HD Camera",
                "spcamera_unique-id": "builtin-camera",
                "spcamera_model-id": "FaceTime HD Camera",
            },
            {
                "_name": "Display capture-UVC05",
                "spcamera_unique-id": "capture-card-id",
                "spcamera_model-id": "UVC Camera VendorID_7649 ProductID_61717",
            },
        ]
    }


def test_capture_devices_keep_avfoundation_index_and_friendly_name() -> None:
    devices = _devices_from_system_profiler(_camera_payload())
    assert [(device["index"], device["name"]) for device in devices] == [
        (0, "FaceTime HD Camera"),
        (1, "Display capture-UVC05"),
    ]
    assert devices[1]["preferred"] is True
    assert devices[1]["transportCodec"] == "MJPEG"


def test_capture_device_binding_prefers_stable_id_over_old_index() -> None:
    devices = _devices_from_system_profiler(_camera_payload())
    selected, error = resolve_capture_device(
        {
            "captureDeviceIndex": 0,
            "captureDeviceId": "capture-card-id",
            "captureDeviceName": "Display capture-UVC05",
        },
        devices,
    )
    assert error is None
    assert selected is not None
    assert selected["index"] == 1
    assert selected["name"] == "Display capture-UVC05"


def test_windows_directshow_devices_keep_real_names_and_encoded_indices() -> None:
    devices = _devices_from_camera_infos(
        [
            SimpleNamespace(
                index=700,
                name="Integrated Camera",
                path="device://integrated",
                vid=0x1234,
                pid=0x0001,
                backend=cv2.CAP_DSHOW,
            ),
            SimpleNamespace(
                index=701,
                name="Display capture-UVC05",
                path="device://capture-card",
                vid=0x1DE1,
                pid=0x1815,
                backend=cv2.CAP_DSHOW,
            ),
        ]
    )

    assert [(item["index"], item["name"]) for item in devices] == [
        (700, "Integrated Camera"),
        (701, "Display capture-UVC05"),
    ]
    assert devices[1]["preferred"] is True
    assert devices[1]["backend"] == cv2.CAP_DSHOW
    assert devices[1]["id"].startswith("dshow:")


def test_windows_capture_binding_uses_stable_directshow_id() -> None:
    devices = _devices_from_camera_infos(
        [
            SimpleNamespace(
                index=701,
                name="USB HDMI Capture",
                path="device://capture-card",
                vid=0x1DE1,
                pid=0x1815,
                backend=cv2.CAP_DSHOW,
            )
        ]
    )

    selected, error = resolve_capture_device(
        {
            "captureDeviceIndex": 0,
            "captureDeviceId": devices[0]["id"],
            "captureDeviceName": "USB HDMI Capture",
        },
        devices,
    )

    assert error is None
    assert selected is not None
    assert selected["index"] == 701


def test_opencv_backend_is_platform_specific_and_preserves_enumerator_value() -> None:
    assert _opencv_capture_backend({}, platform="win32") == cv2.CAP_DSHOW
    assert _opencv_capture_backend({}, platform="linux") == cv2.CAP_ANY
    assert (
        _opencv_capture_backend({"backend": cv2.CAP_MSMF}, platform="win32")
        == cv2.CAP_MSMF
    )
