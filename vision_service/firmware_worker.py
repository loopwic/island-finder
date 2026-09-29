"""Isolated esptool worker. Only the confirmed firmware job launches this file."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from esptool.cmds import (
    attach_flash, detect_chip, detect_flash_size, reset_chip,
    run_stub, verify_flash, write_flash,
)

from firmware_image import validate_firmware
from firmware_backup import read_backup
from firmware_transport import firmware_port
from pabotbase2 import PABotBase2Bridge
from parent_watch import start_parent_watch

EVENT_PREFIX = "ISLAND_FIRMWARE_EVENT "
SERIAL_READ_TIMEOUT = 8.0
_last_stage = "preparing"


def start_stub(esp):
    # esptool 5.1 command() temporarily sets a timeout, but restores the
    # original value. Its raw OHAI read in run_stub() otherwise waits forever
    # because pyserial defaults to timeout=None. Pin the base timeout too.
    esp._port.timeout = SERIAL_READ_TIMEOUT
    esp._port.write_timeout = 10.0
    event("starting_stub", "芯片已识别，正在以 115200 启动临时烧录程序；握手读取超时为 8 秒")
    try:
        return run_stub(esp)
    except Exception as error:
        raise ValueError(
            f"临时烧录程序启动/握手失败：{error}；未开始备份或写入。"
            "请检查 UART 接线，必要时重新进入 BOOT 模式后再确认重试"
        ) from error


def event(stage: str, message: str, **details: object) -> None:
    global _last_stage
    _last_stage = stage
    print(EVENT_PREFIX + json.dumps({"stage": stage, "message": message, **details},
                                   ensure_ascii=False), flush=True)


def flash(port: str, image_path: Path, filename: str, expected_sha256: str,
          backup: Path | None, baud: int) -> None:
    data = image_path.read_bytes()
    metadata = validate_firmware(data, filename)
    if metadata["sha256"] != expected_sha256:
        raise ValueError("确认后的固件文件发生变化，已取消")
    event("connecting", "正在进入下载模式；若连接失败，请按住 BOOT 再按 RESET")
    # Auto-detect, then reject every chip except S3 before any flash operation.
    with firmware_port(port) as connection, detect_chip(port=connection, baud=115200, connect_attempts=3) as esp:
        if esp.CHIP_NAME != "ESP32-S3":
            raise ValueError(f"检测到 {esp.CHIP_NAME}，只支持 ESP32-S3")
        if (esp.secure_download_mode or esp.get_secure_boot_enabled()
                or esp.get_flash_encryption_enabled()):
            raise ValueError("设备启用了安全启动、加密或安全下载模式；拒绝写入")
        # Match esptool's CLI: upload/start the stub at ROM speed first.
        # Changing the ROM baud before the stub starts can lose its OHAI reply.
        esp = start_stub(esp)
        event("configuring", "临时烧录程序握手成功，正在配置串口并识别 Flash 容量")
        if baud != 115200:
            esp.change_baud(baud)
        attach_flash(esp)
        size_label = detect_flash_size(esp)
        sizes = {f"{mb}MB": mb * 1024 * 1024 for mb in (2, 4, 8, 16, 32)}
        flash_size = sizes.get(size_label or "")
        if flash_size is None or metadata["requiredFlashSize"] > flash_size:
            raise ValueError(f"Flash 容量不支持或不足：{size_label}")
        backup_details = {"backupPath": None, "backupRequested": backup is not None}
        if backup is not None:
            event("backing_up", f"正在备份整片 {size_label} Flash，请勿拔线或关闭应用")
            original = read_backup(esp, flash_size, event)
            if original is None or len(original) != flash_size:
                raise ValueError("完整备份失败，未写入任何固件")
            with backup.open("xb") as output:
                os.chmod(backup, 0o600)
                output.write(original)
                output.flush()
                os.fsync(output.fileno())
            digest = hashlib.sha256(original).hexdigest()
            if hashlib.sha256(backup.read_bytes()).hexdigest() != digest:
                raise ValueError("备份落盘校验失败，未写入任何固件")
            backup_details.update(backupPath=str(backup), backupSha256=digest)
        else:
            esp.flash_set_parameters(flash_size)
        event("writing", ("完整备份已保存，" if backup else "按确认选择跳过备份，") + "正在写入固件；请勿断电",
              **backup_details, flashSize=flash_size)
        write_flash(esp, [(0, data)], no_progress=True)
        event("verifying", "正在校验 Flash 中的固件")
        verify_flash(esp, [(0, data)])
        event("rebooting", "写入校验通过，正在重启并检查 PABotBase2 协议")
        reset_chip(esp, "hard-reset")
    # This handshake sends no buttons and does not start game automation.
    bridge = PABotBase2Bridge()
    if bridge.probe_firmware(port):
        event("succeeded", "烧录、写入校验及 PABotBase2 握手均已完成；可重新连接 Switch")
    else:
        event("needs_reconnect", "写入校验已通过，但尚未确认 PABotBase2 握手；请重插 UART 后启动配对，不要直接重复烧录")


def failure_message(stage: str, error: Exception, backup_requested: bool = True) -> str:
    before_write = stage in {"preparing", "connecting", "starting_stub", "configuring", "backing_up"}
    advice = ("未执行 Flash 擦除或写入，原固件未被本次任务覆盖。" if before_write else
              "已进入写入或校验阶段，" + ("请保留备份，" if backup_requested else "本次未创建备份，")
              + "重新进入 BOOT 模式后可使用官方固件恢复；不要自动重复烧录。")
    return f"烧录未完成（{stage}）：{error}。{advice}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--filename", required=True)
    parser.add_argument("--sha256", required=True)
    backup_options = parser.add_mutually_exclusive_group(required=True)
    backup_options.add_argument("--backup", type=Path)
    backup_options.add_argument("--skip-backup", action="store_true")
    parser.add_argument("--baud", type=int, choices=(115200, 460800), required=True)
    args = parser.parse_args()
    start_parent_watch(lambda: os._exit(2))
    try:
        flash(args.port, args.image, args.filename, args.sha256, args.backup, args.baud)
    except Exception as error:
        event("failed", failure_message(_last_stage, error, args.backup is not None))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
