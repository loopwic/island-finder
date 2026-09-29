from __future__ import annotations

import pytest

import firmware_backup


def test_backup_uses_verified_esptool_reader_with_throttled_progress(monkeypatch):
    times = iter([0, 0.2, 0.5, 1.2, 2.0])
    monkeypatch.setattr(firmware_backup.time, "monotonic", lambda: next(times))
    reports = []
    calls = []
    data = b"x" * 100
    class Chip:
        def flash_set_parameters(self, size): calls.append(("parameters", size))
        def read_flash(self, offset, size, progress_fn):
            assert calls == [("parameters", 100)]
            assert (offset, size) == (0, 100)
            for done in (10, 20, 60, 100): progress_fn(done, size, offset)
            return data
    result = firmware_backup.read_backup(Chip(), 100,
                                        lambda stage, message, **details: reports.append((stage, message, details)))
    assert result == data
    assert [item[2]["percent"] for item in reports] == [0, 60, 100]
    assert reports[-1][2]["estimatedSeconds"] == 0
    assert reports[-1][2]["bytesPerSecond"] == 50
    assert all(item[0] == "backing_up" for item in reports)


def test_backup_never_swallows_serial_or_digest_failure():
    class Chip:
        def flash_set_parameters(self, _size): pass
        def read_flash(self, *_args, **_kwargs): raise ValueError("Digest mismatch")
    with pytest.raises(ValueError, match="Digest mismatch"):
        firmware_backup.read_backup(Chip(), 1024, lambda *_args, **_kwargs: None)
