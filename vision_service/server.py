from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import uvicorn

from analyzer import analyze_map
from backend import BackendRuntime
from http_api import create_app
from parent_watch import start_parent_watch


DEFAULT_SERVICE_PORT = 48_197


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
    app = create_app(runtime)
    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        access_log=False,
        log_level="warning",
        ws_ping_interval=5.0,
        ws_ping_timeout=10.0,
    )
    server = uvicorn.Server(config)
    start_parent_watch(lambda: setattr(server, "should_exit", True))
    print(
        f"Island FastAPI backend listening on http://{args.host}:{args.port} "
        f"and ws://{args.host}:{args.port}/v1/ws",
        flush=True,
    )
    try:
        server.run()
    finally:
        runtime.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
