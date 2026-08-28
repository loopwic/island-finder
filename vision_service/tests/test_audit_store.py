from __future__ import annotations

import copy
from itertools import count

import cv2
import numpy as np
import pytest

import audit_store
from analyzer import analysis_input_sha256
from audit_store import SelectionAuditStore
from backend import AutomationEngine


REGIONS = [
    {"x": 0.0, "y": 0.0, "width": 0.5, "height": 0.5},
    {"x": 0.5, "y": 0.0, "width": 0.5, "height": 0.5},
    {"x": 0.0, "y": 0.5, "width": 0.5, "height": 0.5},
    {"x": 0.5, "y": 0.5, "width": 0.5, "height": 0.5},
]


def _frame() -> np.ndarray:
    frame = np.zeros((80, 120, 3), dtype=np.uint8)
    colors = ((35, 80, 180), (60, 150, 90), (190, 150, 40), (150, 70, 170))
    for index, color in enumerate(colors):
        row, column = divmod(index, 2)
        frame[row * 40 : (row + 1) * 40, column * 60 : (column + 1) * 60] = color
    return frame


def _candidates(best_index: int = 2) -> list[dict]:
    candidates = []
    for index in range(4):
        score = 0.82 if index == best_index else 0.55 + index * 0.03
        candidates.append(
            {
                "cardIndex": index,
                "score": score,
                "targetId": None,
                "targetName": "条件筛选",
                "hardPass": index == best_index,
                "visualSimilarity": None,
                "analysisConfidence": 0.91,
                "visionEngine": "opencv",
                "factors": [
                    {
                        "key": "airportPlaza",
                        "label": "机场与广场",
                        "score": score,
                        "passed": index == best_index,
                        "hard": True,
                        "summary": "测试判定",
                    }
                ],
            }
        )
    return candidates


def _candidates_for_frame(frame: np.ndarray, best_index: int = 2) -> list[dict]:
    candidates = _candidates(best_index)
    for index, candidate in enumerate(candidates):
        row, column = divmod(index, 2)
        crop = frame[row * 40 : (row + 1) * 40, column * 60 : (column + 1) * 60]
        candidate["analysisInputSha256"] = analysis_input_sha256(crop)
    return candidates


def test_audit_persists_full_frame_four_crops_and_decision(tmp_path):
    store = SelectionAuditStore(tmp_path)

    record = store.create(
        _frame(),
        REGIONS,
        _candidates(),
        run_number=7,
        threshold=0.76,
        stable_frames=3,
        auto_reject=True,
    )

    assert record["runNumber"] == 7
    assert record["status"] == "reviewing"
    assert record["bestCardIndex"] == 2
    assert record["bestScore"] == pytest.approx(0.82)
    assert record["evidenceRevision"] == 1
    assert len(record["frameSha256"]) == 64
    assert len(record["cards"]) == 4
    assert cv2.imread(str(store.image_path(record["id"], record["frameFile"]))).shape[:2] == (80, 120)
    for card in record["cards"]:
        assert card["file"].endswith(".png")
        assert len(card["sha256"]) == 64
        assert len(card["analysisInputSha256"]) == 64
        assert cv2.imread(str(store.image_path(record["id"], card["file"]))).shape[:2] == (40, 60)

    updated = store.update(
        record["id"],
        status="rejected",
        summary="硬条件未通过：机场与广场",
        decision="自动重开",
    )

    assert updated["status"] == "rejected"
    assert store.get(record["id"])["decision"] == "自动重开"
    assert store.list()[0]["id"] == record["id"]


def test_audit_advances_image_and_analysis_as_one_same_frame_evidence(tmp_path):
    store = SelectionAuditStore(tmp_path)
    first_frame = _frame()
    record = store.create(
        first_frame,
        REGIONS,
        _candidates_for_frame(first_frame),
        run_number=1,
        threshold=0.76,
        stable_frames=3,
        auto_reject=True,
    )
    next_frame = np.flip(first_frame, axis=1).copy()
    next_candidates = _candidates_for_frame(next_frame, best_index=1)

    updated = store.replace_evidence(record["id"], next_frame, REGIONS, next_candidates)

    assert updated["evidenceRevision"] == 2
    assert updated["bestCardIndex"] == 1
    assert updated["candidates"] == next_candidates
    for card, candidate in zip(updated["cards"], next_candidates):
        decoded = cv2.imread(str(store.image_path(updated["id"], card["file"])))
        assert analysis_input_sha256(decoded) == candidate["analysisInputSha256"]
        assert card["analysisInputSha256"] == candidate["analysisInputSha256"]

    with pytest.raises(ValueError, match="不是同一帧"):
        store.replace_evidence(record["id"], first_frame, REGIONS, next_candidates)


def test_audit_store_prunes_every_file_beyond_latest_twenty(tmp_path, monkeypatch):
    timestamps = count(1_700_000_000_000)
    monkeypatch.setattr(audit_store, "_now_ms", lambda: next(timestamps))
    store = SelectionAuditStore(tmp_path, limit=20)
    created = [
        store.create(
            _frame(),
            REGIONS,
            _candidates(index % 4),
            run_number=index,
            threshold=0.76,
            stable_frames=3,
            auto_reject=True,
        )
        for index in range(22)
    ]

    remaining = store.list()

    assert len(remaining) == 20
    assert [record["runNumber"] for record in remaining] == list(range(21, 1, -1))
    for removed in created[:2]:
        assert not (store.directory / f"{removed['id']}.json").exists()
        assert not (store.directory / removed["frameFile"]).exists()
        assert all(not (store.directory / card["file"]).exists() for card in removed["cards"])


def test_audit_image_endpoint_lookup_rejects_unregistered_names(tmp_path):
    store = SelectionAuditStore(tmp_path)
    record = store.create(
        _frame(),
        REGIONS,
        _candidates(),
        run_number=1,
        threshold=0.76,
        stable_frames=3,
        auto_reject=True,
    )

    with pytest.raises(KeyError):
        store.image_path(record["id"], "../settings.json")
    with pytest.raises(ValueError):
        store.get("../../settings")


def test_audit_requires_exactly_four_candidates(tmp_path):
    store = SelectionAuditStore(tmp_path)

    with pytest.raises(ValueError, match="四张地图"):
        store.create(
            _frame(),
            REGIONS,
            _candidates()[:3],
            run_number=1,
            threshold=0.76,
            stable_frames=3,
            auto_reject=True,
        )


class _FakeController:
    def __init__(self) -> None:
        self.runs: list[list[dict]] = []
        self.presses: list[tuple[str, int, int]] = []

    def run(self, commands: list[dict]) -> None:
        self.runs.append(commands)

    def press(self, button: str, hold_ms: int, after_ms: int) -> None:
        self.presses.append((button, hold_ms, after_ms))

    def cancel(self) -> None:
        return


def _engine_with_audit(tmp_path, candidates: list[dict], *, stable_frames: int = 2):
    settings = {
        "threshold": 0.76,
        "stableFrames": stable_frames,
        "autoReject": True,
    }
    store = SelectionAuditStore(tmp_path)
    record = store.create(
        _frame(),
        REGIONS,
        candidates,
        run_number=4,
        threshold=settings["threshold"],
        stable_frames=stable_frames,
        auto_reject=True,
    )
    controller = _FakeController()
    engine = AutomationEngine(
        lambda: settings,
        None,  # type: ignore[arg-type]
        controller,  # type: ignore[arg-type]
        store,
        lambda _snapshot: None,
        lambda _level, _message: None,
    )
    engine.snapshot.update({"runNumber": 4, "candidates": candidates})
    engine.active_audit_id = record["id"]
    engine._spawn = lambda action: bool(action() or True)  # type: ignore[method-assign]
    return engine, controller, store, record


def test_engine_updates_one_audit_through_candidate_and_acceptance(tmp_path):
    candidates = _candidates()
    engine, controller, store, record = _engine_with_audit(tmp_path, candidates)

    engine._scan(candidates)
    engine._scan(candidates)

    candidate_record = store.get(record["id"])
    assert candidate_record["status"] == "candidate"
    assert candidate_record["selectedCardIndex"] == 2
    assert len(store.list()) == 1

    engine._accept_candidate()

    accepted = store.get(record["id"])
    assert accepted["status"] == "accepted"
    assert accepted["decision"] == "用户确认保留"
    assert controller.presses == [("A", 80, 250)]
    assert engine.active_audit_id is None


def test_engine_scan_keeps_captured_evidence_and_tracks_later_decision_separately(tmp_path):
    captured = _candidates(best_index=0)
    later = _candidates(best_index=2)
    engine, _controller, store, record = _engine_with_audit(
        tmp_path,
        captured,
        stable_frames=3,
    )

    engine._scan(later)

    updated = store.get(record["id"])
    assert updated["candidates"] == captured
    assert updated["decisionCandidates"] == later
    assert updated["bestCardIndex"] == 0
    assert updated["decisionBestCardIndex"] == 2


def test_engine_finalizes_failed_audit_before_restart(tmp_path):
    candidates = _candidates()
    for candidate in candidates:
        candidate["hardPass"] = False
        candidate["factors"][0]["passed"] = False
    engine, controller, store, record = _engine_with_audit(tmp_path, candidates)

    engine._scan(candidates)
    engine._scan(candidates)

    rejected = store.get(record["id"])
    assert rejected["status"] == "rejected"
    assert "硬条件未通过" in rejected["decision"]
    assert len(controller.runs) == 1
    assert engine.active_audit_id is None


def test_engine_rejection_requires_consecutive_matching_failure_results(tmp_path):
    rocks_failed = _candidates()
    for candidate in rocks_failed:
        candidate["hardPass"] = False
        candidate["factors"][0]["passed"] = False
        candidate["factors"][0]["key"] = "coastalRocks"

    beach_failed = copy.deepcopy(rocks_failed)
    for candidate in beach_failed:
        candidate["factors"][0]["key"] = "beachShape"

    engine, controller, store, record = _engine_with_audit(
        tmp_path,
        rocks_failed,
        stable_frames=3,
    )

    engine._scan(rocks_failed)
    engine._scan(beach_failed)
    engine._scan(rocks_failed)
    engine._scan(rocks_failed)

    reviewing = store.get(record["id"])
    assert reviewing["status"] == "reviewing"
    assert reviewing["rejectStableHitCount"] == 2
    assert controller.runs == []

    engine._scan(rocks_failed)

    rejected = store.get(record["id"])
    assert rejected["status"] == "rejected"
    assert len(controller.runs) == 1
