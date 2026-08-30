from __future__ import annotations

import asyncio
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from analyzer import analyze_map
from backend import BackendRuntime
from birthday_ocr import recognize_birthday
from candidate_ocr import recognize_keyboard_frame
from screen_classifier import classify_screen


SERVICE_VERSION = "3.2"
MAX_IMAGE_BYTES = 16 * 1024 * 1024
STATE_STREAM_INTERVAL_SECONDS = 0.25
STATE_HEARTBEAT_INTERVAL_SECONDS = 5.0
LOCAL_ORIGINS = {
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "http://tauri.localhost",
    "tauri://localhost",
}
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_ROOT = PROJECT_ROOT / "apps" / "web" / "dist"


def _error(status_code: int, error: Exception | str) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=status_code)


def _decode_image(payload: bytes, query: Any, *, allow_rgba: bool) -> np.ndarray:
    if not payload or len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("invalid image payload size")
    encoded = np.frombuffer(payload, dtype=np.uint8)
    if allow_rgba and query.get("format", "") == "rgba":
        frame_width = int(query.get("width", "0"))
        frame_height = int(query.get("height", "0"))
        if frame_width < 640 or frame_height < 360:
            raise ValueError("invalid raw frame dimensions")
        if len(payload) != frame_width * frame_height * 4:
            raise ValueError("raw RGBA payload size does not match dimensions")
        rgba = encoded.reshape((frame_height, frame_width, 4))
        return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("image decode failed")
    return image


def _normalized_regions(query: Any) -> list[tuple[float, float, float, float]]:
    regions_payload = json.loads(query.get("regions", "[]"))
    if not isinstance(regions_payload, list) or len(regions_payload) != 4:
        raise ValueError("exactly four normalized map regions are required")
    regions: list[tuple[float, float, float, float]] = []
    for region in regions_payload:
        if not isinstance(region, dict):
            raise ValueError("invalid map region")
        values = tuple(float(region[key]) for key in ("x", "y", "width", "height"))
        x, y, region_width, region_height = values
        if (
            x < 0
            or y < 0
            or region_width <= 0
            or region_height <= 0
            or x + region_width > 1
            or y + region_height > 1
        ):
            raise ValueError("map region must fit inside the normalized frame")
        regions.append(values)
    return regions


def _observe(sheet: np.ndarray, query: Any) -> dict[str, Any]:
    regions = _normalized_regions(query)
    screen = classify_screen(sheet, regions)
    candidates: list[dict[str, Any]] = []
    if query.get("candidates", "1") != "0" and screen.kind == "mapSelection":
        height, width = sheet.shape[:2]
        for index, (x, y, region_width, region_height) in enumerate(regions):
            x0 = max(0, min(width - 1, round(x * width)))
            y0 = max(0, min(height - 1, round(y * height)))
            x1 = max(x0 + 1, min(width, round((x + region_width) * width)))
            y1 = max(y0 + 1, min(height, round((y + region_height) * height)))
            result = analyze_map(sheet[y0:y1, x0:x1])
            result.update(
                cardIndex=index,
                targetId=None,
                targetName="条件筛选",
                visualSimilarity=None,
                visionEngine="opencv",
            )
            candidates.append(result)
    return {"screen": screen.as_payload(), "candidates": candidates}


def _keyboard_candidates(sheet: np.ndarray, query: Any) -> dict[str, Any]:
    frame_width = int(query.get("width", "0"))
    frame_height = int(query.get("height", "0"))
    target = query.get("target", "")
    scope = query.get("scope", "full")
    raw_target_index = query.get("targetIndex", "")
    target_index = int(raw_target_index) if raw_target_index else None
    height, width = sheet.shape[:2]
    if frame_width < 640 or frame_width != width:
        raise ValueError("invalid source frame width")
    if frame_height < 360 or frame_height != height:
        raise ValueError("invalid source frame height")
    result = recognize_keyboard_frame(sheet, target, scope, target_index)
    result["target"] = target
    result["visionEngine"] = "rapidocr"
    return result


def _birthday_values(sheet: np.ndarray, query: Any) -> dict[str, Any]:
    frame_width = int(query.get("width", "0"))
    frame_height = int(query.get("height", "0"))
    height, width = sheet.shape[:2]
    if frame_width < 640 or frame_width != width:
        raise ValueError("invalid source frame width")
    if frame_height < 360 or frame_height != height:
        raise ValueError("invalid source frame height")
    return recognize_birthday(sheet)


def _analyze_cards(sheet: np.ndarray, query: Any) -> dict[str, Any]:
    card_count = max(1, min(4, int(query.get("cards", "4"))))
    _height, width = sheet.shape[:2]
    card_width = width // card_count
    candidates: list[dict[str, Any]] = []
    for index in range(card_count):
        x0 = index * card_width
        x1 = width if index == card_count - 1 else (index + 1) * card_width
        result = analyze_map(sheet[:, x0:x1])
        result.update(
            cardIndex=index,
            targetId=None,
            targetName="条件筛选",
            visualSimilarity=None,
            visionEngine="opencv",
        )
        candidates.append(result)
    return {"candidates": candidates}


def _mjpeg_frames(runtime: BackendRuntime) -> Iterator[bytes]:
    last_sequence = -1
    while True:
        payload, sequence = runtime.capture.latest_preview_jpeg(
            wait_seconds=1.0,
            after_sequence=last_sequence,
        )
        if sequence <= last_sequence:
            continue
        last_sequence = sequence
        if payload is None:
            payload = runtime.jpeg(1280, 76)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            + f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
            + payload
            + b"\r\n"
        )


def create_app(runtime: BackendRuntime) -> FastAPI:
    app = FastAPI(title="Island Finder Vision", version=SERVICE_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(LOCAL_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-Island-Finder-Instance",
            "X-Island-Finder-Start-Token",
        ],
    )

    @app.middleware("http")
    async def no_store(request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "engine": "opencv",
            "keyboardOcr": "rapidocr",
            "mode": "headless-backend",
            "version": SERVICE_VERSION,
            "transport": "fastapi-websocket",
        }

    @app.get("/v1/state")
    def state() -> dict[str, Any]:
        return runtime.state()

    @app.websocket("/v1/ws")
    async def state_stream(websocket: WebSocket) -> None:
        origin = websocket.headers.get("origin")
        if origin is not None and origin not in LOCAL_ORIGINS:
            await websocket.close(code=1008, reason="origin not allowed")
            return
        await websocket.accept()
        sequence = 0
        previous_state = ""
        last_sent_at = 0.0
        state_task: asyncio.Task[dict[str, Any]] | None = None
        try:
            while True:
                if state_task is None:
                    state_task = asyncio.create_task(run_in_threadpool(runtime.state))
                done, _pending = await asyncio.wait(
                    {state_task},
                    timeout=STATE_STREAM_INTERVAL_SECONDS,
                )
                now = time.monotonic()
                if state_task in done:
                    snapshot = state_task.result()
                    state_task = None
                    encoded = json.dumps(
                        snapshot,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    changed = encoded != previous_state
                    if changed:
                        sequence += 1
                        await websocket.send_json(
                            {
                                "type": "state",
                                "sequence": sequence,
                                "sentAt": int(time.time() * 1000),
                                "state": snapshot,
                            }
                        )
                        previous_state = encoded
                        last_sent_at = now
                    elif now - last_sent_at >= STATE_HEARTBEAT_INTERVAL_SECONDS:
                        sequence += 1
                        await websocket.send_json(
                            {
                                "type": "heartbeat",
                                "sequence": sequence,
                                "sentAt": int(time.time() * 1000),
                            }
                        )
                        last_sent_at = now
                    await asyncio.sleep(STATE_STREAM_INTERVAL_SECONDS)
                elif now - last_sent_at >= STATE_HEARTBEAT_INTERVAL_SECONDS:
                    sequence += 1
                    await websocket.send_json(
                        {
                            "type": "heartbeat",
                            "sequence": sequence,
                            "sentAt": int(time.time() * 1000),
                        }
                    )
                    last_sent_at = now
        except (WebSocketDisconnect, RuntimeError):
            return
        finally:
            if state_task is not None:
                state_task.cancel()

    @app.get("/v1/settings")
    def settings() -> dict[str, Any]:
        return runtime.store.get()

    async def save_settings(request: Request) -> Response:
        try:
            payload = json.loads((await request.body()).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON payload must be an object")
            return JSONResponse(await run_in_threadpool(runtime.update_settings, payload))
        except Exception as error:  # noqa: BLE001
            return _error(400, error)

    app.add_api_route("/v1/settings", save_settings, methods=["POST", "PUT"])

    @app.get("/v1/capture-devices")
    def capture_devices() -> dict[str, Any]:
        return runtime.capture_devices()

    @app.get("/v1/audits")
    def audit_history() -> dict[str, Any]:
        return runtime.audit_history()

    @app.get("/v1/audits/{audit_id}")
    def audit(audit_id: str) -> Response:
        try:
            return JSONResponse(runtime.audit(audit_id))
        except KeyError:
            return _error(404, "audit not found")
        except ValueError as error:
            return _error(400, error)

    @app.get("/v1/audits/{audit_id}/images/{filename}")
    def audit_image(audit_id: str, filename: str) -> Response:
        try:
            path = runtime.audit_image(audit_id, filename)
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            return FileResponse(path, media_type=content_type)
        except KeyError:
            return _error(404, "audit image not found")
        except ValueError as error:
            return _error(400, error)

    @app.get("/v1/frame.jpg")
    def frame(width: int = 1280, quality: int = 78) -> Response:
        try:
            payload = runtime.jpeg(max(320, min(1920, width)), max(45, min(92, quality)))
            return Response(payload, media_type="image/jpeg")
        except Exception as error:  # noqa: BLE001
            return _error(503, error)

    @app.get("/v1/stream.mjpg")
    def mjpeg_stream() -> StreamingResponse:
        return StreamingResponse(
            _mjpeg_frames(runtime),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={"Connection": "close"},
        )

    @app.post("/v1/actions/{action}")
    def action(action: str, request: Request) -> Response:
        try:
            instance_id = request.headers.get("X-Island-Finder-Instance")
            if action == "arm-start":
                payload = runtime.arm_start(instance_id)
            else:
                payload = runtime.action(
                    action,
                    instance_id,
                    request.headers.get("X-Island-Finder-Start-Token"),
                )
            return JSONResponse(payload)
        except Exception as error:  # noqa: BLE001
            return _error(400, error)

    @app.post("/v1/logs/clear")
    def clear_logs() -> dict[str, bool]:
        runtime.clear_logs()
        return {"ok": True}

    @app.post("/{operation}")
    async def vision_operation(operation: str, request: Request) -> Response:
        if operation not in {"analyze", "birthday-values", "keyboard-candidates", "observe"}:
            raise HTTPException(status_code=404, detail="not found")
        try:
            payload = await request.body()
            query = request.query_params
            sheet = await run_in_threadpool(
                _decode_image,
                payload,
                query,
                allow_rgba=operation in {"observe", "birthday-values", "keyboard-candidates"},
            )
            if operation == "observe":
                result = await run_in_threadpool(_observe, sheet, query)
            elif operation == "keyboard-candidates":
                result = await run_in_threadpool(_keyboard_candidates, sheet, query)
            elif operation == "birthday-values":
                result = await run_in_threadpool(_birthday_values, sheet, query)
            else:
                result = await run_in_threadpool(_analyze_cards, sheet, query)
            return JSONResponse(result)
        except Exception as error:  # noqa: BLE001
            return _error(400, error)

    @app.get("/{request_path:path}")
    def static_files(request_path: str) -> Response:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (DIST_ROOT / relative).resolve()
        try:
            candidate.relative_to(DIST_ROOT.resolve())
        except ValueError:
            return _error(403, "forbidden")
        if not candidate.is_file() and "." not in Path(relative).name:
            candidate = DIST_ROOT / "index.html"
        if not candidate.is_file():
            return _error(404, "UI 尚未构建；运行 npm run build")
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        return FileResponse(candidate, media_type=content_type)

    return app
