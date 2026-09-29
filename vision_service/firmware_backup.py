"""Full-device backup with bounded reads and user-visible transfer progress."""
from __future__ import annotations

import time
from typing import Callable


def read_backup(esp, size: int, report: Callable[..., None]) -> bytes:
    # Equivalent to esptool.cmds.read_flash's parameter setup; the capacity was
    # already detected and validated by the caller. Keep esptool's packet-size
    # checks and device-vs-host MD5 verification in ESPLoader.read_flash().
    esp.flash_set_parameters(size)
    started = time.monotonic()
    last_report = started
    report("backing_up", f"正在备份整片 {size / 1048576:g} MiB Flash：0%",
           bytesRead=0, totalBytes=size, percent=0)

    def progress(done: int, total: int, _offset: int) -> None:
        nonlocal last_report
        now = time.monotonic()
        if now - last_report < 1 and done != total:
            return
        last_report = now
        speed = done / max(now - started, 0.001)
        remaining = max(0, round((total - done) / speed)) if speed else 0
        percent = round(done / total * 100, 1)
        report("backing_up",
               f"备份 {percent:.1f}% · {done / 1048576:.2f}/{total / 1048576:g} MiB"
               f" · {speed / 1024:.1f} KiB/s · 预计剩余 {remaining // 60}分{remaining % 60:02d}秒",
               bytesRead=done, totalBytes=total, percent=percent,
               bytesPerSecond=round(speed), estimatedSeconds=remaining)

    return esp.read_flash(0, size, progress_fn=progress)
