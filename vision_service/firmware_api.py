from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, PlainTextResponse

from firmware_image import MAX_FIRMWARE_BYTES
import firmware_service


def install_firmware_routes(app: FastAPI, runtime: Any, origins: set[str]) -> None:
    def authorize(request: Request) -> None:
        origin = request.headers.get("origin")
        if origin is not None and origin not in origins:
            raise ValueError("不允许此页面操作固件")
        if request.headers.get("X-Island-Finder-Instance") != runtime.instance_id:
            raise ValueError("固件请求来自旧会话，请重新连接后端")

    def require_idle() -> None:
        if runtime.engine.state()["phase"] != "idle" or runtime.engine.busy:
            raise ValueError("请先停止自动选岛；暂停状态下也不能烧录")

    async def body(request: Request, limit: int) -> bytes:
        result = bytearray()
        async for chunk in request.stream():
            result.extend(chunk)
            if len(result) > limit:
                raise ValueError("固件请求体超过大小限制")
        return bytes(result)

    @app.get("/v1/firmware/status")
    def status() -> dict[str, Any]:
        return runtime.firmware.status()

    @app.get("/v1/firmware/close-guard")
    def close_guard() -> PlainTextResponse:
        return PlainTextResponse("busy" if runtime.firmware.busy else "idle")

    @app.get("/v1/firmware/ports")
    def ports(request: Request) -> JSONResponse:
        try:
            authorize(request)
            return JSONResponse({"ports": firmware_service.serial_ports()})
        except (ValueError, OSError) as error:
            return JSONResponse({"error": str(error)}, status_code=400)

    @app.post("/v1/firmware/image")
    async def upload(request: Request) -> JSONResponse:
        try:
            authorize(request)
            data = await body(request, MAX_FIRMWARE_BYTES)
            info = await run_in_threadpool(runtime.firmware.upload, data, request.query_params.get("filename", ""))
            return JSONResponse(info)
        except (ValueError, OSError) as error:
            return JSONResponse({"error": str(error)}, status_code=400)

    def operate(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        with runtime._action_lock:
            require_idle()
            if operation == "bundled":
                return runtime.firmware.use_bundled()
            if operation == "prepare":
                return runtime.firmware.prepare(str(payload.get("port", "")))
            return runtime.firmware.start(str(payload.get("confirmationToken", "")),
                                          payload.get("baud", 460800), payload.get("acknowledged", False),
                                          payload.get("backupRequested", True))

    @app.post("/v1/firmware/{operation}")
    async def action(operation: str, request: Request) -> JSONResponse:
        try:
            authorize(request)
            if operation not in {"bundled", "prepare", "flash"}:
                return JSONResponse({"error": "未知固件操作"}, status_code=404)
            payload = json.loads(await body(request, 4096))
            if not isinstance(payload, dict):
                raise ValueError("请求体必须为对象")
            return JSONResponse(await run_in_threadpool(operate, operation, payload))
        except (ValueError, TypeError, OSError) as error:
            return JSONResponse({"error": str(error)}, status_code=400)
