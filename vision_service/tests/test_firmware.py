from __future__ import annotations

import hashlib
import json
import struct
import threading
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from esptool.bin_image import ESP32S3FirmwareImage, ELFSection

import firmware_service
import firmware_worker
import firmware_image
from firmware_image import bundled_firmware, validate_firmware
from firmware_service import FirmwareService
from pabotbase2 import ControllerError, PABotBase2Bridge

FILENAME = "PABotBase2-ESP32-S3-test.bin"
PORTS = [{"path": "COM12", "description": "USB UART", "identity": "test-board-1"}]


def firmware_bytes(project: bytes = b"PABotBase2") -> bytes:
    def image(segment: bytes) -> bytes:
        item = ESP32S3FirmwareImage()
        item.chip_id = 9
        item.segments = [ELFSection(b".dram", 0x3FC88000, segment, 0)]
        return item.save(None)

    boot = image(b"boot" * 16)
    descriptor = bytearray(256)
    struct.pack_into("<I", descriptor, 0, 0xABCD5432)
    descriptor[16:20] = b"test"
    descriptor[48:48 + len(project)] = project
    app = image(bytes(descriptor))
    partitions = struct.pack("<HBBII16sI", 0x50AA, 0, 0, 0x10000, 0x100000, b"factory", 0)
    table = partitions + b"\xeb\xeb" + b"\xff" * 14 + hashlib.md5(partitions).digest()
    merged = bytearray(b"\xff" * (0x10000 + len(app)))
    merged[:len(boot)] = boot
    merged[0x8000:0x8000 + len(table)] = table
    merged[0x10000:] = app
    return bytes(merged)


def test_valid_full_firmware_has_verified_metadata():
    data = firmware_bytes()
    info = validate_firmware(data, FILENAME)
    assert info["sha256"] == hashlib.sha256(data).hexdigest()
    assert info["chip"] == "ESP32-S3"
    assert info["version"] == "test"
    assert info["requiredFlashSize"] == 0x110000


def test_bundled_official_image_is_pinned_validated_and_default(tmp_path):
    path, info = bundled_firmware()
    assert path.is_file()
    assert info["source"] == "bundled"
    assert info["release"] == "2026090200"
    assert info["sha256"] == "15ffc4155e7c93d420c06a86abb161c25199397dd7b76ef052c19daa99cdcd79"
    service = FirmwareService(tmp_path, lambda *_: pytest.fail("must not connect"))
    assert service.status()["image"] == info
    assert service._image_path == path
    assert not tmp_path.joinpath("firmware").exists()  # Loading never writes to the installation or user data.


@pytest.mark.parametrize("damage", ["missing", "corrupt", "path"])
def test_missing_or_tampered_bundle_never_becomes_flashable(tmp_path, monkeypatch, damage):
    manifest = json.loads((firmware_image.BUNDLED_ROOT / "manifest.json").read_text())
    if damage == "path": manifest["filename"] = "../../bad.bin"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    if damage == "corrupt": (tmp_path / manifest["filename"]).write_bytes(b"corrupt")
    monkeypatch.setattr(firmware_image, "BUNDLED_ROOT", tmp_path)
    service = FirmwareService(tmp_path / "data", lambda *_: pytest.fail("must not connect"))
    assert service.status()["image"] is None
    assert "内置固件不可用" in service.status()["bundledError"]
    with pytest.raises(ValueError): service.prepare("COM12")


def test_switching_to_bundle_invalidates_confirmation_and_uses_packaged_path(tmp_path, monkeypatch):
    service, _ = make_service(tmp_path, monkeypatch)
    token = service.prepare("COM12")["confirmationToken"]
    service.use_bundled()
    assert service._image_path.parent == firmware_image.BUNDLED_ROOT
    with pytest.raises(ValueError, match="确认"):
        service.start(token, 460800, True)
    service._state["busy"] = True
    with pytest.raises(ValueError, match="进行中"): service.use_bundled()


def test_invalid_upload_does_not_leave_a_previous_flashable_image(tmp_path, monkeypatch):
    service, _ = make_service(tmp_path, monkeypatch)
    with pytest.raises(ValueError): service.upload(b"bad", FILENAME)
    assert service.status()["image"] is None
    assert service.use_bundled()["source"] == "bundled"


@pytest.mark.parametrize("record", ["[]", "null", '{"logs": null}'])
def test_bad_saved_record_does_not_break_firmware_startup(tmp_path, record):
    root = tmp_path / "firmware"
    root.mkdir()
    (root / "last-job.json").write_text(record)
    assert FirmwareService(tmp_path, lambda *_: None).busy is False


@pytest.mark.parametrize("name", ["bootloader.bin", "PABotBase2-ESP32-test.bin", "../PABotBase2-ESP32-S3-test.bin"])
def test_reject_wrong_files_and_paths(name):
    with pytest.raises(ValueError, match="完整固件"):
        validate_firmware(firmware_bytes(), name)


@pytest.mark.parametrize("offset", [12, 50, 0x8010, 0x10000 + 40, -1])
def test_reject_corrupted_chip_partition_and_app(offset):
    damaged = bytearray(firmware_bytes())
    damaged[offset] ^= 1
    with pytest.raises(ValueError):
        validate_firmware(bytes(damaged), FILENAME)


def test_reject_placeholder_or_non_pabotbase_app():
    with pytest.raises(ValueError, match="不是 PABotBase"):
        validate_firmware(firmware_bytes(b"led-off-placeholder"), FILENAME)
    with pytest.raises(ValueError, match="大小"):
        validate_firmware(firmware_bytes()[:0x8000], FILENAME)


def make_service(tmp_path, monkeypatch):
    monkeypatch.setattr(firmware_service, "serial_ports", lambda: PORTS)
    calls = []
    service = FirmwareService(tmp_path, lambda action, owner: calls.append(action))
    service.upload(firmware_bytes(), FILENAME)
    return service, calls


def test_confirmation_is_required_single_use_and_bound_to_device(tmp_path, monkeypatch):
    service, _ = make_service(tmp_path, monkeypatch)
    token = service.prepare("COM12")["confirmationToken"]
    monkeypatch.setattr(firmware_service, "serial_ports", lambda: [{**PORTS[0], "identity": "replacement"}])
    with pytest.raises(ValueError, match="设备已变化"):
        service.start(token, 460800, True)
    with pytest.raises(ValueError, match="确认"):
        service.start(token, 460800, True)


def test_confirmation_expires_and_upload_invalidates_it(tmp_path, monkeypatch):
    service, _ = make_service(tmp_path, monkeypatch)
    token = service.prepare("COM12")["confirmationToken"]
    service.upload(firmware_bytes(), FILENAME)
    with pytest.raises(ValueError, match="确认"):
        service.start(token, 460800, True)
    token = service.prepare("COM12")["confirmationToken"]
    monkeypatch.setattr(firmware_service.time, "monotonic", lambda: 10**20)
    with pytest.raises(ValueError, match="确认"):
        service.start(token, 460800, True)


def test_busy_blocks_upload_and_double_start(tmp_path, monkeypatch):
    service, _ = make_service(tmp_path, monkeypatch)
    service._state["busy"] = True
    with pytest.raises(ValueError, match="进行中"):
        service.upload(firmware_bytes(), FILENAME)
    with pytest.raises(ValueError, match="已有"):
        service.start("anything", 460800, True)


def test_worker_failure_restores_lease_and_persists_failure(tmp_path, monkeypatch):
    service, calls = make_service(tmp_path, monkeypatch)
    def fail(*args, **kwargs):
        raise OSError("simulated process failure")
    monkeypatch.setattr(firmware_service.subprocess, "Popen", fail)
    token = service.prepare("COM12")["confirmationToken"]
    service.start(token, 460800, True)
    service._thread.join(timeout=3)
    assert calls == ["start", "stop"]
    assert service.status()["stage"] == "failed"
    assert service.busy is False
    assert FirmwareService(tmp_path, lambda *_: None).status()["stage"] == "failed"


@pytest.mark.parametrize("backup_started", [False, True])
def test_preflight_deadline_releases_lease_but_does_not_kill_backup(tmp_path, monkeypatch, backup_started):
    service, calls = make_service(tmp_path, monkeypatch)
    killed = threading.Event()
    monkeypatch.setattr(firmware_service, "PREFLIGHT_TIMEOUT", 0.02)
    class Process:
        code = None
        def __init__(self, *_args, **_kwargs): self.stdout = self.lines()
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def poll(self): return self.code
        def kill(self):
            self.code = -9
            killed.set()
        def wait(self): return self.code
        def lines(self):
            if backup_started:
                yield firmware_service.EVENT_PREFIX + json.dumps({"stage": "backing_up"})
                assert not killed.wait(0.1)
                yield firmware_service.EVENT_PREFIX + json.dumps({"stage": "succeeded"})
                self.code = 0
            else:
                yield firmware_service.EVENT_PREFIX + json.dumps({"stage": "starting_stub"})
                assert killed.wait(1), "preflight watchdog did not stop stalled worker"
    monkeypatch.setattr(firmware_service.subprocess, "Popen", Process)
    token = service.prepare("COM12")["confirmationToken"]
    service.start(token, 460800, True)
    service._thread.join(timeout=2)
    assert not service._thread.is_alive()
    assert calls == ["start", "stop"]
    assert service.busy is False
    assert service.status()["stage"] == ("succeeded" if backup_started else "failed")
    if not backup_started: assert "尚未进入" in service.status()["message"]


def test_interrupted_job_is_reported_without_resuming(tmp_path):
    root = tmp_path / "firmware"
    root.mkdir()
    (root / "last-job.json").write_text(json.dumps({"busy": True, "stage": "writing", "logs": []}))
    service = FirmwareService(tmp_path, lambda *_: pytest.fail("must not connect"))
    assert service.busy is False
    assert service.status()["stage"] == "failed"
    assert "中断" in service.status()["message"]


def test_controller_maintenance_excludes_pairing_and_other_owners():
    bridge = PABotBase2Bridge()
    bridge.begin_maintenance("a" * 32)
    with pytest.raises(ControllerError, match="维护中"):
        bridge.start()
    with pytest.raises(ControllerError):
        bridge.begin_maintenance("b" * 32)
    with pytest.raises(ControllerError):
        bridge.end_maintenance("b" * 32)
    assert bridge.status()["maintenance"] is True
    bridge.end_maintenance("a" * 32)
    assert bridge.status()["maintenance"] is False


class FakeChip:
    CHIP_NAME = "ESP32-S3"
    secure_download_mode = False
    def __init__(self):
        self._port = SimpleNamespace(timeout=None, write_timeout=None)
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def get_secure_boot_enabled(self): return False
    def get_flash_encryption_enabled(self): return False
    def change_baud(self, _baud): pass


def worker_harness(tmp_path, monkeypatch, *, backup_requested=True):
    image_path = tmp_path / "image.bin"
    data = firmware_bytes()
    image_path.write_bytes(data)
    backup = tmp_path / "backup.bin"
    calls = []
    chip = FakeChip()
    chip.flash_set_parameters = lambda size: calls.append(("flash_size", size))
    monkeypatch.setattr(firmware_worker, "firmware_port", nullcontext)
    monkeypatch.setattr(firmware_worker, "detect_chip", lambda **_: chip)
    monkeypatch.setattr(firmware_worker, "run_stub", lambda value: value)
    monkeypatch.setattr(firmware_worker, "attach_flash", lambda _: None)
    monkeypatch.setattr(firmware_worker, "detect_flash_size", lambda _: "2MB")
    monkeypatch.setattr(firmware_worker, "read_backup", lambda *_, **__: b"\xff" * (2 * 1024 * 1024))
    def write(*args, **kwargs):
        if backup_requested:
            assert backup.is_file()
            assert backup.stat().st_size == 2 * 1024 * 1024
        else:
            assert not backup.exists()
        assert args[1] == [(0, data)]
        assert not kwargs.get("force") and not kwargs.get("erase_all")
        calls.append("write")
    monkeypatch.setattr(firmware_worker, "write_flash", write)
    monkeypatch.setattr(firmware_worker, "verify_flash", lambda *_: calls.append("verify"))
    monkeypatch.setattr(firmware_worker, "reset_chip", lambda *_: calls.append("reset"))
    monkeypatch.setattr(PABotBase2Bridge, "probe_firmware", lambda *_: True)
    args = ("COM12", image_path, FILENAME, hashlib.sha256(data).hexdigest(), backup if backup_requested else None, 460800)
    return args, chip, calls


def test_flash_orders_full_backup_write_verify_and_reset(tmp_path, monkeypatch, capsys):
    args, _, calls = worker_harness(tmp_path, monkeypatch)
    firmware_worker.flash(*args)
    assert calls == ["write", "verify", "reset"]
    assert '"stage": "succeeded"' in capsys.readouterr().out


def test_direct_flash_skips_read_but_keeps_capacity_write_verify_and_reset(tmp_path, monkeypatch, capsys):
    args, _, calls = worker_harness(tmp_path, monkeypatch, backup_requested=False)
    monkeypatch.setattr(firmware_worker, "read_backup", lambda *_: pytest.fail("must not read full flash"))
    firmware_worker.flash(*args)
    assert calls == [("flash_size", 2 * 1024 * 1024), "write", "verify", "reset"]
    output = capsys.readouterr().out
    assert '"backupRequested": false' in output and '"backupPath": null' in output
    assert '"stage": "succeeded"' in output
    assert '"stage": "backing_up"' not in output


@pytest.mark.parametrize("failure", ["chip", "encrypted", "secure", "small", "backup", "image-changed"])
@pytest.mark.parametrize("backup_requested", [False, True])
def test_flash_never_writes_when_preflight_or_backup_fails(tmp_path, monkeypatch, failure, backup_requested):
    if failure == "backup" and not backup_requested:
        return  # No backup operation in direct-write mode.
    args, chip, calls = worker_harness(tmp_path, monkeypatch, backup_requested=backup_requested)
    if failure == "chip": chip.CHIP_NAME = "ESP32"
    if failure == "encrypted": chip.get_flash_encryption_enabled = lambda: True
    if failure == "secure": chip.secure_download_mode = True
    if failure == "small": monkeypatch.setattr(firmware_worker, "detect_flash_size", lambda _: "1MB")
    if failure == "backup": monkeypatch.setattr(firmware_worker, "read_backup", lambda *_, **__: b"short")
    if failure == "image-changed": args = (*args[:3], "wrong", *args[4:])
    with pytest.raises(ValueError): firmware_worker.flash(*args)
    assert calls == []


def test_no_success_if_written_data_cannot_be_verified(tmp_path, monkeypatch):
    args, _, calls = worker_harness(tmp_path, monkeypatch)
    def fail(*_): raise ValueError("bad readback")
    monkeypatch.setattr(firmware_worker, "verify_flash", fail)
    with pytest.raises(ValueError, match="bad readback"):
        firmware_worker.flash(*args)
    assert calls == ["write"]


def test_stub_must_start_with_bounded_io_before_raising_baud(tmp_path, monkeypatch, capsys):
    args, chip, calls = worker_harness(tmp_path, monkeypatch)
    order = []
    def stub(value):
        assert value._port.timeout == 8.0
        assert value._port.write_timeout == 10.0
        assert order == []
        order.append("stub")
        return value
    def baud(value):
        assert value == 460800 and order == ["stub"]
        order.append("baud")
    monkeypatch.setattr(firmware_worker, "run_stub", stub)
    chip.change_baud = baud
    firmware_worker.flash(*args)
    assert order == ["stub", "baud"]
    assert calls == ["write", "verify", "reset"]
    logs = capsys.readouterr().out
    assert '"stage": "starting_stub"' in logs and '"stage": "configuring"' in logs


def test_real_esptool_silent_stub_handshake_has_read_timeout(monkeypatch):
    # Real esptool raw SLIP/OHAI read on an in-memory serial loop: no hardware.
    import serial
    from esptool.targets import ESP32S3ROM
    with serial.serial_for_url("loop://") as port:
        chip = ESP32S3ROM(port)
        chip.sync_stub_detected = False
        chip.get_secure_boot_enabled = lambda: False
        chip.mem_begin = lambda *_: None
        chip.mem_block = lambda *_: None
        chip.mem_finish = lambda *_: None
        monkeypatch.setattr(firmware_worker, "SERIAL_READ_TIMEOUT", 0.02)
        with pytest.raises(ValueError, match="未开始备份或写入"):
            firmware_worker.start_stub(chip)
        assert port.timeout == 0.02


def test_stub_failure_never_changes_speed_or_writes(tmp_path, monkeypatch):
    args, chip, calls = worker_harness(tmp_path, monkeypatch)
    def fail(_): raise TimeoutError("no OHAI")
    monkeypatch.setattr(firmware_worker, "run_stub", fail)
    chip.change_baud = lambda _: pytest.fail("must not change speed before stub handshake")
    with pytest.raises(ValueError, match="未开始备份或写入"):
        firmware_worker.flash(*args)
    assert not args[4].exists()
    assert calls == []


def test_unconfirmed_protocol_is_not_reported_as_success(tmp_path, monkeypatch, capsys):
    args, _, _ = worker_harness(tmp_path, monkeypatch)
    monkeypatch.setattr(PABotBase2Bridge, "probe_firmware", lambda *_: False)
    firmware_worker.flash(*args)
    assert '"stage": "needs_reconnect"' in capsys.readouterr().out


@pytest.mark.parametrize("stage", ["connecting", "starting_stub", "configuring", "backing_up", "writing", "verifying"])
def test_failure_message_distinguishes_prewrite_from_flash_mutation(stage):
    message = firmware_worker.failure_message(stage, ValueError("serial error"))
    assert stage in message and "serial error" in message
    if stage in {"writing", "verifying"}:
        assert "未执行" not in message and "保留备份" in message
    else:
        assert "未执行 Flash 擦除或写入" in message


def test_compatibility_backup_budget_covers_capacity_and_protocol_overhead():
    assert firmware_service.job_timeout(460800) == 1800
    assert firmware_service.job_timeout(115200) > 32 * 1024 * 1024 * 10 / 115200 * 1.5


def test_direct_flash_failure_never_claims_a_backup_exists():
    message = firmware_worker.failure_message("writing", ValueError("serial noise"), False)
    assert "本次未创建备份" in message and "保留备份" not in message


@pytest.mark.parametrize("backup_requested", [True, False])
def test_service_passes_explicit_backup_choice_to_worker(tmp_path, monkeypatch, backup_requested):
    service, calls = make_service(tmp_path, monkeypatch)
    commands = []
    def capture(command, **_):
        commands.append(command)
        raise OSError("test only, no hardware")
    monkeypatch.setattr(firmware_service.subprocess, "Popen", capture)
    token = service.prepare("COM12")["confirmationToken"]
    service.start(token, 460800, True, backup_requested)
    service._thread.join(timeout=3)
    assert len(commands) == 1
    assert ("--backup" in commands[0]) is backup_requested
    assert ("--skip-backup" in commands[0]) is not backup_requested
    assert service.status()["backupRequested"] is backup_requested
    assert (tmp_path / "firmware" / "backups").exists() is backup_requested
    assert calls == ["start", "stop"]
