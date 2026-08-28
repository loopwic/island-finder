from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import cv2
import numpy as np

from analyzer import analyze_map
from backend import BackendRuntime
from birthday_ocr import recognize_birthday
from candidate_ocr import recognize_keyboard_frame
from screen_classifier import classify_screen


SERVICE_VERSION = "3.2"
DEFAULT_SERVICE_PORT = 48_197
LOCAL_ORIGINS = {"http://127.0.0.1:4173", "http://localhost:4173"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_ROOT = PROJECT_ROOT / "dist"


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class VisionHandler(BaseHTTPRequestHandler):
    server_version = "IslandVision/1.0"

    def _headers(self, status: HTTPStatus, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        origin = self.headers.get("Origin", "")
        if origin in LOCAL_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Island-Finder-Instance")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._headers(HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._headers(HTTPStatus.OK)
            self.wfile.write(
                _json_bytes(
                    {
                        "ok": True,
                        "engine": "opencv",
                        "keyboardOcr": "rapidocr",
                        "mode": "headless-backend",
                        "version": SERVICE_VERSION,
                    }
                )
            )
            return
        if parsed.path == "/v1/state":
            self._headers(HTTPStatus.OK)
            self.wfile.write(_json_bytes(self.server.backend.state()))  # type: ignore[attr-defined]
            return
        if parsed.path == "/v1/settings":
            self._headers(HTTPStatus.OK)
            self.wfile.write(_json_bytes(self.server.backend.store.get()))  # type: ignore[attr-defined]
            return
        if parsed.path == "/v1/capture-devices":
            self._headers(HTTPStatus.OK)
            self.wfile.write(
                _json_bytes(self.server.backend.capture_devices())  # type: ignore[attr-defined]
            )
            return
        if parsed.path == "/v1/audits":
            self._headers(HTTPStatus.OK)
            self.wfile.write(
                _json_bytes(self.server.backend.audit_history())  # type: ignore[attr-defined]
            )
            return
        audit_parts = [unquote(part) for part in parsed.path.split("/") if part]
        if len(audit_parts) == 3 and audit_parts[:2] == ["v1", "audits"]:
            try:
                payload = self.server.backend.audit(audit_parts[2])  # type: ignore[attr-defined]
                self._headers(HTTPStatus.OK)
                self.wfile.write(_json_bytes(payload))
            except KeyError:
                self._headers(HTTPStatus.NOT_FOUND)
                self.wfile.write(_json_bytes({"error": "audit not found"}))
            except ValueError as error:
                self._headers(HTTPStatus.BAD_REQUEST)
                self.wfile.write(_json_bytes({"error": str(error)}))
            return
        if (
            len(audit_parts) == 5
            and audit_parts[:2] == ["v1", "audits"]
            and audit_parts[3] == "images"
        ):
            try:
                path = self.server.backend.audit_image(  # type: ignore[attr-defined]
                    audit_parts[2],
                    audit_parts[4],
                )
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self._headers(HTTPStatus.OK, content_type)
                self.wfile.write(path.read_bytes())
            except KeyError:
                self._headers(HTTPStatus.NOT_FOUND)
                self.wfile.write(_json_bytes({"error": "audit image not found"}))
            except ValueError as error:
                self._headers(HTTPStatus.BAD_REQUEST)
                self.wfile.write(_json_bytes({"error": str(error)}))
            return
        if parsed.path == "/v1/frame.jpg":
            try:
                query = parse_qs(parsed.query)
                width = max(320, min(1920, int(query.get("width", ["1280"])[0])))
                quality = max(45, min(92, int(query.get("quality", ["78"])[0])))
                payload = self.server.backend.jpeg(width, quality)  # type: ignore[attr-defined]
                self._headers(HTTPStatus.OK, "image/jpeg")
                self.wfile.write(payload)
            except Exception as error:  # noqa: BLE001
                self._headers(HTTPStatus.SERVICE_UNAVAILABLE)
                self.wfile.write(_json_bytes({"error": str(error)}))
            return
        if parsed.path == "/v1/stream.mjpg":
            self._stream_mjpeg()
            return
        self._serve_static(parsed.path)

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/v1/settings":
            self._headers(HTTPStatus.NOT_FOUND)
            self.wfile.write(_json_bytes({"error": "not found"}))
            return
        self._handle_settings_update()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/v1/settings":
            self._handle_settings_update()
            return
        if parsed.path.startswith("/v1/actions/"):
            try:
                action = parsed.path.removeprefix("/v1/actions/")
                payload = self.server.backend.action(  # type: ignore[attr-defined]
                    action,
                    self.headers.get("X-Island-Finder-Instance"),
                )
                self._headers(HTTPStatus.OK)
                self.wfile.write(_json_bytes(payload))
            except Exception as error:  # noqa: BLE001
                self._headers(HTTPStatus.BAD_REQUEST)
                self.wfile.write(_json_bytes({"error": str(error)}))
            return
        if parsed.path == "/v1/logs/clear":
            self.server.backend.clear_logs()  # type: ignore[attr-defined]
            self._headers(HTTPStatus.OK)
            self.wfile.write(_json_bytes({"ok": True}))
            return
        if parsed.path not in {"/analyze", "/birthday-values", "/keyboard-candidates", "/observe"}:
            self._headers(HTTPStatus.NOT_FOUND)
            self.wfile.write(_json_bytes({"error": "not found"}))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16 * 1024 * 1024:
                raise ValueError("invalid image payload size")
            query = parse_qs(parsed.query)
            encoded = np.frombuffer(self.rfile.read(length), dtype=np.uint8)
            if (
                parsed.path in {"/observe", "/birthday-values", "/keyboard-candidates"}
                and query.get("format", [""])[0] == "rgba"
            ):
                frame_width = int(query.get("width", ["0"])[0])
                frame_height = int(query.get("height", ["0"])[0])
                if frame_width < 640 or frame_height < 360:
                    raise ValueError("invalid raw frame dimensions")
                expected_length = frame_width * frame_height * 4
                if length != expected_length:
                    raise ValueError("raw RGBA payload size does not match dimensions")
                rgba = encoded.reshape((frame_height, frame_width, 4))
                sheet = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
            else:
                sheet = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                if sheet is None:
                    raise ValueError("image decode failed")
            if parsed.path == "/observe":
                regions_payload = json.loads(query.get("regions", ["[]"])[0])
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

                screen = classify_screen(sheet, regions)
                candidates = []
                include_candidates = query.get("candidates", ["1"])[0] != "0"
                if include_candidates and screen.kind == "mapSelection":
                    height, width = sheet.shape[:2]
                    for index, (x, y, region_width, region_height) in enumerate(regions):
                        x0 = max(0, min(width - 1, round(x * width)))
                        y0 = max(0, min(height - 1, round(y * height)))
                        x1 = max(x0 + 1, min(width, round((x + region_width) * width)))
                        y1 = max(y0 + 1, min(height, round((y + region_height) * height)))
                        result = analyze_map(sheet[y0:y1, x0:x1])
                        result["cardIndex"] = index
                        result["targetId"] = None
                        result["targetName"] = "条件筛选"
                        result["visualSimilarity"] = None
                        result["visionEngine"] = "opencv"
                        candidates.append(result)
                self._headers(HTTPStatus.OK)
                self.wfile.write(
                    _json_bytes({"screen": screen.as_payload(), "candidates": candidates})
                )
                return

            if parsed.path == "/keyboard-candidates":
                frame_width = int(query.get("width", ["0"])[0])
                frame_height = int(query.get("height", ["0"])[0])
                target = query.get("target", [""])[0]
                scope = query.get("scope", ["full"])[0]
                raw_target_index = query.get("targetIndex", [""])[0]
                target_index = int(raw_target_index) if raw_target_index else None
                height, width = sheet.shape[:2]
                if frame_width < 640 or frame_width != width:
                    raise ValueError("invalid source frame width")
                if frame_height < 360 or frame_height != height:
                    raise ValueError("invalid source frame height")
                result = recognize_keyboard_frame(sheet, target, scope, target_index)
                result["target"] = target
                result["visionEngine"] = "rapidocr"
                self._headers(HTTPStatus.OK)
                self.wfile.write(_json_bytes(result))
                return

            if parsed.path == "/birthday-values":
                frame_width = int(query.get("width", ["0"])[0])
                frame_height = int(query.get("height", ["0"])[0])
                height, width = sheet.shape[:2]
                if frame_width < 640 or frame_width != width:
                    raise ValueError("invalid source frame width")
                if frame_height < 360 or frame_height != height:
                    raise ValueError("invalid source frame height")
                result = recognize_birthday(sheet)
                self._headers(HTTPStatus.OK)
                self.wfile.write(_json_bytes(result))
                return

            card_count = max(1, min(4, int(query.get("cards", ["4"])[0])))
            height, width = sheet.shape[:2]
            card_width = width // card_count
            candidates = []
            for index in range(card_count):
                x0 = index * card_width
                x1 = width if index == card_count - 1 else (index + 1) * card_width
                result = analyze_map(sheet[:, x0:x1])
                result["cardIndex"] = index
                result["targetId"] = None
                result["targetName"] = "条件筛选"
                result["visualSimilarity"] = None
                result["visionEngine"] = "opencv"
                candidates.append(result)
            self._headers(HTTPStatus.OK)
            self.wfile.write(_json_bytes({"candidates": candidates}))
        except Exception as error:  # noqa: BLE001
            self._headers(HTTPStatus.BAD_REQUEST)
            self.wfile.write(_json_bytes({"error": str(error)}))

    def _read_json(self, maximum: int = 16 * 1024 * 1024) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > maximum:
            raise ValueError("invalid JSON payload size")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object")
        return payload

    def _handle_settings_update(self) -> None:
        try:
            settings = self.server.backend.update_settings(self._read_json())  # type: ignore[attr-defined]
            self._headers(HTTPStatus.OK)
            self.wfile.write(_json_bytes(settings))
        except Exception as error:  # noqa: BLE001
            self._headers(HTTPStatus.BAD_REQUEST)
            self.wfile.write(_json_bytes({"error": str(error)}))

    def _stream_mjpeg(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        last_sequence = -1
        try:
            while True:
                payload, sequence = self.server.backend.capture.latest_preview_jpeg(  # type: ignore[attr-defined]
                    wait_seconds=1.0,
                    after_sequence=last_sequence,
                )
                if sequence <= last_sequence:
                    continue
                last_sequence = sequence
                if payload is None:
                    payload = self.server.backend.jpeg(1280, 76)  # type: ignore[attr-defined]
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
                self.wfile.write(payload)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            return

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (DIST_ROOT / relative).resolve()
        try:
            candidate.relative_to(DIST_ROOT.resolve())
        except ValueError:
            self._headers(HTTPStatus.FORBIDDEN)
            self.wfile.write(_json_bytes({"error": "forbidden"}))
            return
        if not candidate.is_file() and "." not in Path(relative).name:
            candidate = DIST_ROOT / "index.html"
        if not candidate.is_file():
            self._headers(HTTPStatus.NOT_FOUND)
            self.wfile.write(_json_bytes({"error": "UI 尚未构建；运行 npm run build"}))
            return
        content_type, _encoding = mimetypes.guess_type(candidate.name)
        self._headers(HTTPStatus.OK, content_type or "application/octet-stream")
        self.wfile.write(candidate.read_bytes())

    def log_message(self, message_format: str, *args: object) -> None:
        message = message_format % args
        if ' 200 ' in message or ' 204 ' in message:
            return
        print(f"[vision] {self.address_string()} {message}")


def analyze_file(path: Path, debug_path: Path | None) -> int:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"无法读取图片：{path}")
    result = analyze_map(image, include_debug=debug_path is not None)
    if debug_path is not None:
        debug = result.pop("debugImage")
        result.pop("masks", None)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(debug_path), debug):
            raise SystemExit(f"无法写入调试图：{debug_path}")
        result["debugPath"] = str(debug_path.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Island Finder OpenCV vision service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=DEFAULT_SERVICE_PORT, type=int)
    parser.add_argument("--analyze", type=Path)
    parser.add_argument("--debug-output", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--capture-index", type=int)
    parser.add_argument("--autostart", action="store_true")
    args = parser.parse_args()
    if args.analyze:
        return analyze_file(args.analyze, args.debug_output)
    runtime = BackendRuntime(
        data_dir=args.data_dir,
        autostart=args.autostart,
        capture_index=args.capture_index,
    )
    server = ThreadingHTTPServer((args.host, args.port), VisionHandler)
    server.backend = runtime  # type: ignore[attr-defined]
    print(f"Island headless backend listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        runtime.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
