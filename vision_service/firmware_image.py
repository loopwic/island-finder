"""Validate full ESP32-S3 PABotBase2 images without opening a device."""
from __future__ import annotations

import hashlib
import io
import json
import re
import struct
from pathlib import Path
from typing import Any

from esptool.bin_image import ESP32S3FirmwareImage

MAX_FIRMWARE_BYTES = 16 * 1024 * 1024
FIRMWARE_NAME = re.compile(r"PABotBase2-ESP32-S3-[A-Za-z0-9_.-]+\.bin", re.IGNORECASE)
BUNDLED_ROOT = Path(__file__).with_name("firmware_assets")


def bundled_firmware() -> tuple[Path, dict[str, Any]]:
    """Read the pinned, offline image shipped with both source and desktop builds."""
    manifest = json.loads((BUNDLED_ROOT / "manifest.json").read_text(encoding="utf-8"))
    filename = manifest["filename"]
    if not isinstance(filename, str) or not FIRMWARE_NAME.fullmatch(filename):
        raise ValueError("内置固件清单中的文件名无效")
    path = BUNDLED_ROOT / filename
    data = path.read_bytes()
    if len(data) != manifest["size"] or hashlib.sha256(data).hexdigest() != manifest["sha256"]:
        raise ValueError("内置固件的大小或 SHA-256 不匹配，请重新安装应用")
    info = validate_firmware(data, filename)
    return path, {**info, "source": "bundled", "release": manifest["release"], "sourceUrl": manifest["sourceUrl"]}


def _image(data: bytes, label: str) -> ESP32S3FirmwareImage:
    try:
        image = ESP32S3FirmwareImage(io.BytesIO(data))
        if image.chip_id != 9 or image.checksum != image.calculate_checksum():
            raise ValueError("芯片类型或校验和不匹配")
        if not image.append_digest or image.stored_digest != image.calc_digest:
            raise ValueError("缺少或不匹配的 SHA-256 摘要")
        return image
    except Exception as error:
        raise ValueError(f"{label}无效：{error}") from error


def validate_firmware(data: bytes, filename: str) -> dict[str, Any]:
    if not FIRMWARE_NAME.fullmatch(filename):
        raise ValueError("请选择官方 PABotBase2-ESP32-S3-<版本>.bin 完整固件")
    if not 0x10000 < len(data) <= MAX_FIRMWARE_BYTES:
        raise ValueError("固件大小无效；不接受单独的 Bootloader 或超过 16 MiB 的文件")
    boot = _image(data[:0x8000], "Bootloader")
    if (boot.data_length or 0) + 32 > 0x8000:
        raise ValueError("Bootloader 超出支持的分区布局")
    table = data[0x8000:0x9000]
    partitions: list[tuple[int, int, int, int]] = []
    table_verified = False
    for index in range(0, len(table), 32):
        entry = table[index:index + 32]
        if entry[:2] == b"\xeb\xeb":
            if hashlib.md5(table[:index]).digest() != entry[16:32]:
                raise ValueError("分区表 MD5 校验失败")
            table_verified = True
            break
        if entry[:2] != b"\xaa\x50":
            raise ValueError("缺少完整分区表或分区表格式不受支持")
        _, kind, subtype, offset, size, _label, flags = struct.unpack("<HBBII16sI", entry)
        if flags or size == 0 or offset < 0x9000 or offset % 4096 or size % 4096:
            raise ValueError("不支持加密分区或异常分区布局")
        if offset + size > MAX_FIRMWARE_BYTES:
            raise ValueError("分区超出支持的 Flash 范围")
        if any(offset < previous + length and previous < offset + size
               for _, _, previous, length in partitions):
            raise ValueError("分区发生重叠")
        partitions.append((kind, subtype, offset, size))
    if not table_verified:
        raise ValueError("缺少分区表校验记录")
    apps = [(offset, size) for kind, subtype, offset, size in partitions
            if kind == 0 and subtype == 0]
    if len(apps) != 1 or apps[0][0] != 0x10000:
        raise ValueError("只支持官方 factory 应用位于 0x10000 的完整固件")
    offset, capacity = apps[0]
    app = _image(data[offset:offset + capacity], "手柄应用")
    if (app.data_length or 0) + 32 > capacity:
        raise ValueError("应用超出分区大小")
    # The IDF application descriptor is at the start of the first data segment.
    descriptor = data[offset + 32:offset + 32 + 256]
    if len(descriptor) != 256 or struct.unpack_from("<I", descriptor)[0] != 0xABCD5432:
        raise ValueError("缺少 ESP-IDF 应用描述符")
    project = descriptor[48:80].split(b"\0", 1)[0].decode("ascii", errors="replace")
    version = descriptor[16:48].split(b"\0", 1)[0].decode("ascii", errors="replace")
    if not project.lower().startswith("pabotbase2"):
        raise ValueError("这不是 PABotBase2 应用，拒绝写入")
    return {
        "filename": filename, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "chip": "ESP32-S3", "project": project, "version": version,
        "flashOffset": "0x0", "requiredFlashSize": max(
            len(data), max(start + size for _, _, start, size in partitions)
        ),
    }
