from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTROLLER_PORT = 32_145
VISION_PORT = 48_197
CONTROL_PORT = 32_146
RUNTIME_SERVICE = "island-finder-runtime"


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    script: Path
    port: int
    arguments: tuple[str, ...] = ()


def _port_is_open(port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _request_json(url: str, *, method: str = "GET", timeout: float = 0.8) -> dict[str, object]:
    request = Request(url, method=method)
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback-only API
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"本地运行时返回了无效响应：{url}")
    return payload


def _release_controller() -> None:
    for endpoint in ("/v1/release-all", "/v1/pairing/stop"):
        try:
            _request_json(
                f"http://127.0.0.1:{CONTROLLER_PORT}{endpoint}",
                method="POST",
                timeout=1.0,
            )
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, json.JSONDecodeError):
            pass


def _wait_for_port(port: int, process: subprocess.Popen[bytes], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(f"服务在端口 {port} 就绪前退出，退出码 {exit_code}")
        if _port_is_open(port):
            return
        time.sleep(0.1)
    raise RuntimeError(f"服务在 {timeout:.0f} 秒内没有监听端口 {port}")


def _spawn(spec: ServiceSpec) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {
        "cwd": PROJECT_ROOT,
        "env": {
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "ISLAND_FINDER_SUPERVISOR_PID": str(os.getpid()),
        },
        "stdin": subprocess.DEVNULL,
        "stdout": None,
        "stderr": None,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(  # noqa: S603 - commands are fixed project scripts
        [sys.executable, str(spec.script), *spec.arguments],
        **options,
    )


def _terminate(process: subprocess.Popen[bytes], timeout: float = 4.0) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)


class RuntimeControlServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, stop_event: threading.Event) -> None:
        super().__init__(("127.0.0.1", CONTROL_PORT), RuntimeControlHandler)
        self.stop_event = stop_event


class RuntimeControlHandler(BaseHTTPRequestHandler):
    server_version = "IslandRuntime/1.0"

    def _respond(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self._respond(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        self._respond(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": RUNTIME_SERVICE,
                "projectRoot": str(PROJECT_ROOT),
                "pid": os.getpid(),
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/shutdown":
            self._respond(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        self._respond(HTTPStatus.ACCEPTED, {"ok": True})
        self.server.stop_event.set()  # type: ignore[attr-defined]

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _cleanup_previous_runtime() -> None:
    if not _port_is_open(CONTROL_PORT):
        return
    try:
        status = _request_json(f"http://127.0.0.1:{CONTROL_PORT}/health")
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"运行时控制端口 {CONTROL_PORT} 已被未知程序占用，拒绝自动停止"
        ) from error
    if status.get("service") != RUNTIME_SERVICE or status.get("projectRoot") != str(PROJECT_ROOT):
        raise RuntimeError(
            f"运行时控制端口 {CONTROL_PORT} 不属于当前 Island Finder 项目，拒绝自动停止"
        )
    _request_json(
        f"http://127.0.0.1:{CONTROL_PORT}/shutdown",
        method="POST",
        timeout=1.0,
    )
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        if not _port_is_open(CONTROL_PORT):
            return
        time.sleep(0.1)
    raise RuntimeError("旧 Island Finder 运行时未能在 8 秒内停止")


def _watch_stdin(file_descriptor: int, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        payload = os.read(file_descriptor, 1024)
        if not payload or b"shutdown" in payload.lower():
            stop_event.set()
            return


def _watch_parent(parent_pid: int, stop_event: threading.Event) -> None:
    if parent_pid <= 1:
        return
    while not stop_event.wait(0.5):
        try:
            os.kill(parent_pid, 0)
        except OSError:
            stop_event.set()
            return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Island Finder desktop runtime supervisor")
    parser.add_argument("--parent-pid", type=int, default=0)
    parser.add_argument("--autostart", action="store_true")
    parser.add_argument("--cleanup-only", action="store_true")
    parser.add_argument("--watch-stdin", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _cleanup_previous_runtime()
    if args.cleanup_only:
        return 0

    for port, label in ((CONTROLLER_PORT, "控制器"), (VISION_PORT, "视觉后端")):
        if _port_is_open(port):
            raise RuntimeError(f"{label}端口 {port} 已被未知程序占用，拒绝重复启动")

    stop_event = threading.Event()
    control_server = RuntimeControlServer(stop_event)
    control_thread = threading.Thread(target=control_server.serve_forever, daemon=True)
    control_thread.start()

    if args.watch_stdin:
        threading.Thread(
            target=_watch_stdin,
            args=(sys.stdin.fileno(), stop_event),
            daemon=True,
        ).start()
    if args.parent_pid:
        threading.Thread(
            target=_watch_parent,
            args=(args.parent_pid, stop_event),
            daemon=True,
        ).start()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    services = [
        ServiceSpec(
            "控制器服务",
            PROJECT_ROOT / "vision_service" / "controller_server.py",
            CONTROLLER_PORT,
        ),
        ServiceSpec(
            "视觉后端",
            PROJECT_ROOT / "vision_service" / "server.py",
            VISION_PORT,
            ("--autostart",) if args.autostart else (),
        ),
    ]
    children: list[tuple[ServiceSpec, subprocess.Popen[bytes]]] = []
    exit_code = 0
    try:
        for spec in services:
            process = _spawn(spec)
            children.append((spec, process))
            _wait_for_port(spec.port, process, 30.0)
        print(
            "Island Finder 运行时已就绪："
            f"vision=127.0.0.1:{VISION_PORT}, controller=127.0.0.1:{CONTROLLER_PORT}",
            flush=True,
        )
        while not stop_event.wait(0.25):
            for spec, process in children:
                child_exit = process.poll()
                if child_exit is not None:
                    print(
                        f"{spec.name}意外退出（退出码 {child_exit}），正在安全停止其余服务。",
                        file=sys.stderr,
                        flush=True,
                    )
                    exit_code = child_exit or 1
                    stop_event.set()
                    break
    finally:
        _release_controller()
        for _spec, process in reversed(children):
            _terminate(process)
        control_server.shutdown()
        control_server.server_close()
        control_thread.join(timeout=1.0)
        print("Island Finder 运行时已停止，手柄按键已释放。", flush=True)
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
