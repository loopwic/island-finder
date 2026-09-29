"""Bounded, single-owner firmware jobs; independent of the browser lifetime."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from serial.tools import list_ports

from firmware_image import bundled_firmware, validate_firmware

EVENT_PREFIX = "ISLAND_FIRMWARE_EVENT "
TERMINAL_STAGES = {"succeeded", "needs_reconnect", "failed"}
PREFLIGHT_STAGES = {"preparing", "connecting", "starting_stub", "configuring"}
PREFLIGHT_TIMEOUT = 60


def job_timeout(baud: int) -> int:
    # Capacity ceiling supported by the worker; 8N1 uses ten wire bits/byte.
    return max(1800, int(32 * 1024 * 1024 * 10 / baud * 1.5) + 300)


def serial_ports() -> list[dict[str, str]]:
    return [
        {"path": port.device, "description": port.description or port.device,
         "identity": f"{port.vid}:{port.pid}:{port.serial_number}:{port.location}"}
        for port in list_ports.comports()
        if port.vid is not None and port.pid is not None
        and not (sys.platform == "darwin" and not port.device.startswith("/dev/cu."))
    ]


class FirmwareService:
    def __init__(self, data_dir: Path, maintenance: Callable[[str, str], None]) -> None:
        self.root = data_dir / "firmware"
        self._maintenance = maintenance
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[str] | None = None
        self._image: dict[str, Any] | None = None
        self._image_path: Path | None = None
        self._bundled_error: str | None = None
        self._confirmation: tuple[str, str, str, float] | None = None
        self._closing = False
        self._state: dict[str, Any] = {"busy": False, "stage": "idle", "message": "选择串口，使用内置官方固件", "logs": []}
        # Never restart an interrupted write automatically.
        saved = self.root / "last-job.json"
        if saved.is_file():
            try:
                record = json.loads(saved.read_text(encoding="utf-8"))
                if not isinstance(record, dict) or not isinstance(record.get("logs"), list):
                    raise ValueError("无效的任务记录")
                self._state.update(record)
                if self._state.get("busy"):
                    self._state.update(busy=False, stage="failed", message="上次烧录被中断，不能确认设备状态。请保留备份、重新进入 BOOT 模式后恢复。")
            except (ValueError, OSError):
                pass
        try:
            self.use_bundled()
        except ValueError:
            # A damaged installation must not crash the backend or silently flash
            # an old uploaded image. The UI explains why no image is available.
            pass

    def status(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy({**self._state, "image": self._image, "bundledError": self._bundled_error})

    def use_bundled(self) -> dict[str, Any]:
        with self._lock:
            if self.busy:
                raise ValueError("烧录进行中，不能更换固件")
            self._image = None
            self._image_path = None
            self._confirmation = None
            try:
                self._image_path, self._image = bundled_firmware()
                self._bundled_error = None
            except (OSError, ValueError, KeyError, TypeError) as error:
                self._bundled_error = f"内置固件不可用：{error}"
                raise ValueError(self._bundled_error) from error
            return copy.deepcopy(self._image)

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._state["busy"])

    def _persist(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        pending = self.root / "last-job.tmp"
        pending.write_text(json.dumps(self._state, ensure_ascii=False), encoding="utf-8")
        os.chmod(pending, 0o600)
        pending.replace(self.root / "last-job.json")

    def _update(self, **patch: Any) -> None:
        with self._lock:
            self._state.update(patch)
            try:
                self._persist()
            except OSError as error:
                self._state["logs"] = (self._state["logs"] + [f"任务记录保存失败：{error}"])[-60:]

    def upload(self, data: bytes, filename: str) -> dict[str, Any]:
        with self._lock:
            if self.busy:
                raise ValueError("烧录进行中，不能更换固件")
            self._image = None
            self._image_path = None
            self._confirmation = None
            info = validate_firmware(data, filename)
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            target = self.root / "selected.bin"
            target.write_bytes(data)
            os.chmod(target, 0o600)
            self._image = {**info, "source": "custom"}
            self._image_path = target
            return copy.deepcopy(self._image)

    def prepare(self, port: str) -> dict[str, Any]:
        with self._lock:
            if self.busy or not self._image:
                raise ValueError("请先选择有效固件，并等待当前任务结束")
            device = next((item for item in serial_ports() if item["path"] == port), None)
            if device is None:
                raise ValueError("所选 USB 串口已不在线，请刷新设备列表")
            token = uuid.uuid4().hex
            self._confirmation = (token, port, device["identity"], time.monotonic() + 120)
            return {"confirmationToken": token, "port": port, "image": self._image}

    def start(self, token: str, baud: int, acknowledged: bool, backup_requested: bool = True) -> dict[str, Any]:
        with self._lock:
            if self.busy or self._closing:
                raise ValueError("已有烧录任务，不能重复开始")
            confirmation = self._confirmation
            self._confirmation = None
            if (not confirmation or confirmation[0] != token or time.monotonic() > confirmation[3]
                    or not self._image or acknowledged is not True or baud not in {115200, 460800}
                    or type(backup_requested) is not bool):
                raise ValueError("烧录确认已过期或不完整，请重新确认")
            _, port, identity, _ = confirmation
            if not any(item["path"] == port and item["identity"] == identity for item in serial_ports()):
                raise ValueError("USB 设备已变化，已取消；请重新选择串口")
            owner = uuid.uuid4().hex
            backup_dir = self.root / "backups" / owner
            if backup_requested:
                backup_dir.mkdir(parents=True, mode=0o700)
            self._state = {"busy": True, "stage": "preparing", "jobId": owner, "port": port,
                           "message": "正在释放手柄串口", "logs": [], "startedAt": int(time.time() * 1000),
                           "firmwareSha256": self._image["sha256"], "backupPath": None,
                           "backupRequested": backup_requested, "baud": baud}
            try:
                self._persist()
            except OSError:
                self._state.update(busy=False, stage="failed", message="无法保存烧录任务；未开始写入")
                raise ValueError("无法保存烧录任务，请检查数据目录权限与剩余空间")
            self._thread = threading.Thread(target=self._run, args=(owner, port, baud, copy.deepcopy(self._image), backup_dir if backup_requested else None),
                                            daemon=True, name="firmware-job")
            try:
                self._thread.start()
            except RuntimeError as error:
                self._thread = None
                self._update(busy=False, stage="failed", message="无法启动烧录任务；未开始写入")
                raise ValueError("无法启动烧录任务；未开始写入") from error
            return self.status()

    def _run(self, owner: str, port: str, baud: int, info: dict[str, Any], backup_dir: Path | None) -> None:
        lease_requested = False
        timer: threading.Timer | None = None
        preflight_timer: threading.Timer | None = None
        timeout_message: list[str] = []
        recovery_advice = "请保留备份并检查设备" if backup_dir else "本次未创建备份，请保留日志并检查设备"
        try:
            lease_requested = True
            self._maintenance("start", owner)
            command = [sys.executable, "-u", str(Path(__file__).with_name("firmware_worker.py")),
                       "--port", port, "--image", str(self._image_path),
                       "--filename", info["filename"], "--sha256", info["sha256"],
                       "--baud", str(baud)]
            command += ["--backup", str(backup_dir / "flash-original.bin")] if backup_dir else ["--skip-backup"]
            options: dict[str, Any] = {}
            if os.name == "nt":
                options["creationflags"] = subprocess.CREATE_NO_WINDOW
            with self._lock:
                if self._closing:
                    raise RuntimeError("应用正在退出，未开始写入")
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                                  env={**os.environ, "PYTHONUNBUFFERED": "1", "ISLAND_FINDER_SUPERVISOR_PID": str(os.getpid())},
                                  **options)
                self._process = process
            with process:

                def timeout(preflight: bool = False) -> None:
                    with self._lock:
                        if preflight and self._state["stage"] not in PREFLIGHT_STAGES:
                            return
                        if process.poll() is None:
                            timeout_message.append(
                                "芯片/临时烧录程序初始化超过 60 秒，已停止；尚未进入 Flash 备份和写入阶段"
                                if preflight else f"烧录超过 {deadline // 60} 分钟已停止，{recovery_advice}"
                            )
                            process.kill()

                # Full 32 MiB backups at 115200 can exceed 30 minutes. Bound the
                # whole job by capacity ceiling plus transfer/protocol headroom.
                deadline = job_timeout(baud)
                timer = threading.Timer(deadline, timeout)
                timer.daemon = True
                timer.start()
                preflight_timer = threading.Timer(PREFLIGHT_TIMEOUT, lambda: timeout(preflight=True))
                preflight_timer.daemon = True
                preflight_timer.start()
                assert process.stdout is not None
                for line in process.stdout:
                    line = line.strip()[:2000]
                    if line.startswith(EVENT_PREFIX):
                        self._update(**json.loads(line[len(EVENT_PREFIX):]))
                    elif line:
                        with self._lock:
                            self._state["logs"] = (self._state["logs"] + [line])[-60:]
                code = process.wait()
                if code or self.status()["stage"] not in TERMINAL_STAGES:
                    if self.status()["stage"] != "failed":
                        raise RuntimeError(timeout_message[0] if timeout_message
                                           else f"烧录进程异常退出（{code}）；{recovery_advice}")
        except Exception as error:
            self._update(stage="failed", message=str(error))
        finally:
            if timer:
                timer.cancel()
            if preflight_timer:
                preflight_timer.cancel()
            self._process = None
            if lease_requested:
                try:
                    self._maintenance("stop", owner)
                except Exception as error:
                    with self._lock:
                        self._state["message"] += f"；串口维护锁未能解除：{error}，请重启应用后再配对"
            self._update(busy=False, finishedAt=int(time.time() * 1000))

    def shutdown(self) -> None:
        # Normal desktop close is blocked while busy. Forced shutdown must not
        # leave an unowned process that can continue writing to the serial port.
        with self._lock:
            self._closing = True
            if self._process is not None and self._process.poll() is None:
                self._process.kill()
        if self._thread is not None:
            self._thread.join(timeout=4)
