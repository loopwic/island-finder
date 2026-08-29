from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import cv2
import numpy as np


AUDIT_LIMIT = 20
_AUDIT_ID = re.compile(r"^[0-9]{13}-[0-9a-f]{8}$")
_SUMMARY_FIELDS = (
    "id",
    "createdAt",
    "updatedAt",
    "runNumber",
    "status",
    "summary",
    "decision",
    "bestCardIndex",
    "bestScore",
    "selectedCardIndex",
)


def _now_ms() -> int:
    return round(time.time() * 1000)


def _crop(frame: np.ndarray, region: dict[str, float]) -> np.ndarray:
    height, width = frame.shape[:2]
    x0 = max(0, min(width - 1, round(float(region["x"]) * width)))
    y0 = max(0, min(height - 1, round(float(region["y"]) * height)))
    x1 = max(x0 + 1, min(width, round((float(region["x"]) + float(region["width"])) * width)))
    y1 = max(y0 + 1, min(height, round((float(region["y"]) + float(region["height"])) * height)))
    return frame[y0:y1, x0:x1]


def _jpeg(image: np.ndarray, quality: int) -> bytes:
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("无法编码审计图像")
    return encoded.tobytes()


def _png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 5])
    if not ok:
        raise RuntimeError("无法编码审计图像")
    return encoded.tobytes()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _pixel_sha256(image: np.ndarray) -> str:
    return _sha256(np.ascontiguousarray(image).tobytes())


def _best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: float(candidate.get("score", 0)))


class SelectionAuditStore:
    def __init__(self, data_dir: Path, limit: int = AUDIT_LIMIT) -> None:
        self.directory = data_dir / "selection-audits"
        self.limit = max(1, int(limit))
        self._lock = threading.RLock()
        with self._lock:
            self._prune_locked()

    def _validate_id(self, audit_id: str) -> str:
        if not _AUDIT_ID.fullmatch(audit_id):
            raise ValueError("审计记录 ID 无效")
        return audit_id

    def _record_path(self, audit_id: str) -> Path:
        return self.directory / f"{self._validate_id(audit_id)}.json"

    def _read_locked(self, audit_id: str) -> dict[str, Any]:
        path = self._record_path(audit_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise KeyError(audit_id) from error
        if not isinstance(payload, dict):
            raise ValueError("审计记录格式无效")
        return payload

    def _write_json_locked(self, payload: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._record_path(str(payload["id"]))
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _write_image_locked(self, name: str, payload: bytes) -> None:
        path = self.directory / name
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)

    def _list_locked(self) -> list[dict[str, Any]]:
        if not self.directory.is_dir():
            return []
        records: list[dict[str, Any]] = []
        for path in self.directory.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and _AUDIT_ID.fullmatch(str(payload.get("id", ""))):
                records.append(payload)
        return sorted(records, key=lambda item: int(item.get("createdAt", 0)), reverse=True)

    def _delete_locked(self, payload: dict[str, Any]) -> None:
        audit_id = self._validate_id(str(payload["id"]))
        names = [str(payload.get("frameFile", ""))]
        names.extend(str(card.get("file", "")) for card in payload.get("cards", []) if isinstance(card, dict))
        for name in names:
            if name.startswith(f"{audit_id}-") and Path(name).suffix.lower() in {".jpg", ".png"}:
                (self.directory / name).unlink(missing_ok=True)
        self._record_path(audit_id).unlink(missing_ok=True)

    def _prune_locked(self) -> None:
        records = self._list_locked()
        for payload in records[self.limit :]:
            self._delete_locked(payload)

    def create(
        self,
        frame: np.ndarray,
        regions: list[dict[str, float]],
        candidates: list[dict[str, Any]],
        *,
        run_number: int,
        threshold: float,
        stable_frames: int,
        auto_reject: bool,
    ) -> dict[str, Any]:
        if frame is None or frame.size == 0:
            raise ValueError("审计画面为空")
        if len(regions) != 4 or len(candidates) != 4:
            raise ValueError("审计记录必须包含四张地图")
        created_at = _now_ms()
        audit_id = f"{created_at}-{uuid.uuid4().hex[:8]}"
        frame_file = f"{audit_id}-frame.jpg"
        cards: list[dict[str, Any]] = []
        written: list[Path] = []
        with self._lock:
            try:
                self.directory.mkdir(parents=True, exist_ok=True)
                frame_payload = _jpeg(frame, 88)
                self._write_image_locked(frame_file, frame_payload)
                written.append(self.directory / frame_file)
                for index, region in enumerate(regions):
                    filename = f"{audit_id}-card-{index + 1}.png"
                    crop = _crop(frame, region)
                    card_payload = _png(crop)
                    pixel_sha256 = _pixel_sha256(crop)
                    candidate_sha256 = candidates[index].get("analysisInputSha256")
                    if candidate_sha256 is not None and candidate_sha256 != pixel_sha256:
                        raise ValueError(f"地图 {index + 1} 的分析结果与审计裁切图不是同一帧")
                    self._write_image_locked(filename, card_payload)
                    written.append(self.directory / filename)
                    cards.append(
                        {
                            "cardIndex": index,
                            "file": filename,
                            "width": int(crop.shape[1]),
                            "height": int(crop.shape[0]),
                            "sha256": _sha256(card_payload),
                            "analysisInputSha256": pixel_sha256,
                        }
                    )
                best = _best_candidate(candidates)
                payload: dict[str, Any] = {
                    "id": audit_id,
                    "createdAt": created_at,
                    "updatedAt": created_at,
                    "runNumber": int(run_number),
                    "status": "reviewing",
                    "summary": "已捕获四岛地图，正在等待稳定判定",
                    "decision": None,
                    "threshold": float(threshold),
                    "stableFrames": int(stable_frames),
                    "autoReject": bool(auto_reject),
                    "frameWidth": int(frame.shape[1]),
                    "frameHeight": int(frame.shape[0]),
                    "frameFile": frame_file,
                    "frameSha256": _sha256(frame_payload),
                    "evidenceRevision": 1,
                    "regions": copy.deepcopy(regions),
                    "cards": cards,
                    "candidates": copy.deepcopy(candidates),
                    "decisionCandidates": copy.deepcopy(candidates),
                    "analysisRevision": candidates[0].get("analysisRevision"),
                    "bestCardIndex": None if best is None else int(best["cardIndex"]),
                    "bestScore": None if best is None else float(best["score"]),
                }
                self._write_json_locked(payload)
                self._prune_locked()
                return copy.deepcopy(payload)
            except Exception:
                for path in written:
                    path.unlink(missing_ok=True)
                self._record_path(audit_id).unlink(missing_ok=True)
                raise

    def update(self, audit_id: str, **patch: Any) -> dict[str, Any]:
        with self._lock:
            payload = self._read_locked(audit_id)
            payload.update(copy.deepcopy(patch))
            payload["updatedAt"] = _now_ms()
            candidates = payload.get("candidates", [])
            if isinstance(candidates, list):
                best = _best_candidate([item for item in candidates if isinstance(item, dict)])
                payload["analysisRevision"] = next(
                    (
                        item.get("analysisRevision")
                        for item in candidates
                        if isinstance(item, dict) and item.get("analysisRevision")
                    ),
                    payload.get("analysisRevision"),
                )
                payload["bestCardIndex"] = None if best is None else int(best["cardIndex"])
                payload["bestScore"] = None if best is None else float(best["score"])
            decision_candidates = payload.get("decisionCandidates", [])
            if isinstance(decision_candidates, list):
                decision_best = _best_candidate(
                    [item for item in decision_candidates if isinstance(item, dict)]
                )
                payload["decisionBestCardIndex"] = (
                    None if decision_best is None else int(decision_best["cardIndex"])
                )
                payload["decisionBestScore"] = (
                    None if decision_best is None else float(decision_best["score"])
                )
            self._write_json_locked(payload)
            return copy.deepcopy(payload)

    def replace_evidence(
        self,
        audit_id: str,
        frame: np.ndarray,
        regions: list[dict[str, float]],
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Atomically advance the audit image and analysis to the same frame."""
        if frame is None or frame.size == 0:
            raise ValueError("审计画面为空")
        if len(regions) != 4 or len(candidates) != 4:
            raise ValueError("审计记录必须包含四张地图")
        with self._lock:
            payload = self._read_locked(audit_id)
            frame_file = str(payload["frameFile"])
            frame_payload = _jpeg(frame, 88)
            cards: list[dict[str, Any]] = []
            card_payloads: list[tuple[str, bytes]] = []
            existing_cards = {
                int(card["cardIndex"]): card
                for card in payload.get("cards", [])
                if isinstance(card, dict)
            }
            for index, region in enumerate(regions):
                crop = _crop(frame, region)
                pixel_sha256 = _pixel_sha256(crop)
                candidate_sha256 = candidates[index].get("analysisInputSha256")
                if candidate_sha256 is not None and candidate_sha256 != pixel_sha256:
                    raise ValueError(f"地图 {index + 1} 的分析结果与审计裁切图不是同一帧")
                old_file = str(existing_cards.get(index, {}).get("file", ""))
                filename = (
                    old_file
                    if old_file.endswith(".png")
                    else f"{audit_id}-card-{index + 1}.png"
                )
                card_payload = _png(crop)
                card_payloads.append((filename, card_payload))
                cards.append(
                    {
                        "cardIndex": index,
                        "file": filename,
                        "width": int(crop.shape[1]),
                        "height": int(crop.shape[0]),
                        "sha256": _sha256(card_payload),
                        "analysisInputSha256": pixel_sha256,
                    }
                )

            self._write_image_locked(frame_file, frame_payload)
            for filename, card_payload in card_payloads:
                self._write_image_locked(filename, card_payload)
            for card in existing_cards.values():
                old_file = str(card.get("file", ""))
                if old_file.endswith(".jpg"):
                    (self.directory / old_file).unlink(missing_ok=True)

            payload.update(
                {
                    "updatedAt": _now_ms(),
                    "frameWidth": int(frame.shape[1]),
                    "frameHeight": int(frame.shape[0]),
                    "frameSha256": _sha256(frame_payload),
                    "regions": copy.deepcopy(regions),
                    "cards": cards,
                    "candidates": copy.deepcopy(candidates),
                    "decisionCandidates": copy.deepcopy(candidates),
                    "evidenceRevision": int(payload.get("evidenceRevision", 1)) + 1,
                }
            )
            best = _best_candidate(candidates)
            payload["analysisRevision"] = candidates[0].get("analysisRevision")
            payload["bestCardIndex"] = None if best is None else int(best["cardIndex"])
            payload["bestScore"] = None if best is None else float(best["score"])
            payload["decisionBestCardIndex"] = payload["bestCardIndex"]
            payload["decisionBestScore"] = payload["bestScore"]
            self._write_json_locked(payload)
            return copy.deepcopy(payload)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._list_locked()[: self.limit])

    def list_summaries(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    key: copy.deepcopy(payload.get(key))
                    for key in _SUMMARY_FIELDS
                }
                for payload in self._list_locked()[: self.limit]
            ]

    def get(self, audit_id: str) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._read_locked(audit_id))

    def image_path(self, audit_id: str, filename: str) -> Path:
        with self._lock:
            payload = self._read_locked(audit_id)
            allowed = {str(payload.get("frameFile", ""))}
            allowed.update(
                str(card.get("file", ""))
                for card in payload.get("cards", [])
                if isinstance(card, dict)
            )
            if (
                filename not in allowed
                or not filename.startswith(f"{audit_id}-")
                or Path(filename).suffix.lower() not in {".jpg", ".png"}
            ):
                raise KeyError(filename)
            path = self.directory / filename
            if not path.is_file():
                raise KeyError(filename)
            return path
