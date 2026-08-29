from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from pabotbase2 import ControllerError, PABotBase2Bridge, protocol_self_test


HOST = "127.0.0.1"
PORT = 32_145


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


class ControllerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], bridge: PABotBase2Bridge) -> None:
        super().__init__(address, ControllerRequestHandler)
        self.bridge = bridge


class ControllerRequestHandler(BaseHTTPRequestHandler):
    server_version = "IslandController/0.5"

    @property
    def bridge(self) -> PABotBase2Bridge:
        return self.server.bridge  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        try:
            print(
                f"[controller] {self.address_string()} {format % args}",
                flush=True,
            )
        except (BrokenPipeError, OSError):
            # A closed inherited terminal must not abort HTTP responses while
            # an orphaned controller is being recovered by the stack owner.
            pass

    def _respond(self, status: int, payload: Any) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ControllerError("Content-Length 无效", status=400) from error
        if not 0 <= length <= 64 * 1024:
            raise ControllerError("请求体过大", status=400)
        if length == 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ControllerError("JSON 请求体无效", status=400) from error
        if not isinstance(payload, dict):
            raise ControllerError("JSON 请求体必须是对象", status=400)
        return payload

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._respond(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/v1/status":
            self._respond(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
            return
        try:
            self._respond(HTTPStatus.OK, self.bridge.status())
        except ControllerError as error:
            self._respond(error.status, {"error": str(error)})
        except Exception as error:  # noqa: BLE001
            self._respond(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"控制器状态读取失败：{error}"},
            )

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/v1/pairing/start":
                self.bridge.start()
                payload = self.bridge.status()
            elif path == "/v1/pairing/stop":
                self.bridge.stop()
                payload = self.bridge.status()
            elif path == "/v1/release-all":
                self.bridge.release_all()
                payload = {"ok": True}
            elif path == "/v1/press":
                command = self._read_json()
                if command.get("type") != "press":
                    raise ControllerError("仅支持 press 命令", status=400)
                self.bridge.press(
                    str(command.get("button", "")),
                    int(command.get("hold_ms", 0)),
                )
                payload = {"ok": True}
            else:
                self._respond(
                    HTTPStatus.NOT_FOUND,
                    {"error": "接口不存在"},
                )
                return
            self._respond(HTTPStatus.OK, payload)
        except ControllerError as error:
            self._respond(error.status, {"error": str(error)})
        except (TypeError, ValueError) as error:
            self._respond(HTTPStatus.BAD_REQUEST, {"error": str(error)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Island Finder 跨平台 PABotBase2 手柄服务",
    )
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bridge = PABotBase2Bridge()

    if args.self_test:
        failures = protocol_self_test()
        if failures:
            for failure in failures:
                print(
                    f"PABotBase2 protocol self-test failed: {failure}",
                    file=sys.stderr,
                )
            return 1
        print("PABotBase2 protocol self-test: PASS")
        return 0

    if args.diagnose:
        payload = bridge.status()
        payload["candidatePorts"] = bridge.candidate_ports()
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 0

    server = ControllerHTTPServer((args.host, args.port), bridge)
    stopped = threading.Event()

    def shutdown(_signum: int, _frame: object) -> None:
        if stopped.is_set():
            return
        stopped.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    print(f"Island Controller Service 已启动：http://{args.host}:{args.port}")
    print("支持 macOS 与 Windows；连接 PABotBase2 后再启用真实控制。")
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        bridge.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
