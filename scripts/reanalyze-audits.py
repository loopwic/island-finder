from __future__ import annotations

import copy
import sys
import time
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vision_service"))

from analyzer import ANALYZER_VERSION, analysis_input_sha256, analyze_map  # noqa: E402
from audit_store import SelectionAuditStore  # noqa: E402
from backend import _default_data_dir  # noqa: E402


def _candidate_revision(candidate: object) -> str:
    return str(candidate.get("analysisRevision") or "unknown") if isinstance(candidate, dict) else "unknown"


def main() -> None:
    store = SelectionAuditStore(_default_data_dir())
    updated = 0
    for record in store.list():
        current_revision = str(record.get("analysisRevision") or "unknown")
        decision_candidates = [
            item for item in record.get("decisionCandidates", []) if isinstance(item, dict)
        ]
        decision_revisions = {_candidate_revision(item) for item in decision_candidates}
        needs_decision_repair = decision_revisions != {ANALYZER_VERSION}
        existing_previous_analyses = copy.deepcopy(record.get("previousAnalyses", []))
        latest_historical = (
            existing_previous_analyses[-1]
            if existing_previous_analyses
            and isinstance(existing_previous_analyses[-1], dict)
            else None
        )
        needs_historical_text_repair = bool(
            current_revision == ANALYZER_VERSION
            and record.get("status") == "rejected"
            and latest_historical
            and (
                record.get("summary") != latest_historical.get("summary")
                or record.get("decision") != latest_historical.get("decision")
            )
        )
        if (
            current_revision == ANALYZER_VERSION
            and not needs_decision_repair
            and not needs_historical_text_repair
        ):
            continue

        old_candidates = [item for item in record.get("candidates", []) if isinstance(item, dict)]
        old_by_card = {int(item.get("cardIndex", -1)): item for item in old_candidates}
        candidates: list[dict] = []
        for card in record.get("cards", []):
            card_index = int(card["cardIndex"])
            image_path = store.image_path(str(record["id"]), str(card["file"]))
            image = cv2.imread(str(image_path))
            if image is None:
                raise RuntimeError(f"无法读取审计裁切图：{image_path}")
            result = analyze_map(image)
            previous = old_by_card.get(card_index, {})
            result.update(
                {
                    "cardIndex": card_index,
                    "analysisInputSha256": analysis_input_sha256(image),
                    "targetId": previous.get("targetId"),
                    "targetName": previous.get("targetName", "条件筛选"),
                    "visualSimilarity": previous.get("visualSimilarity"),
                    "visionEngine": "opencv",
                }
            )
            candidates.append(result)

        archived_at = round(time.time() * 1000)
        previous_analyses = existing_previous_analyses
        if current_revision != ANALYZER_VERSION:
            previous_analyses.append(
                {
                    "analysisRevision": current_revision,
                    "archivedAt": archived_at,
                    "candidates": copy.deepcopy(old_candidates),
                    "decisionCandidates": copy.deepcopy(decision_candidates),
                    "summary": record.get("summary"),
                    "decision": record.get("decision"),
                    "bestCardIndex": record.get("bestCardIndex"),
                    "bestScore": record.get("bestScore"),
                    "decisionBestCardIndex": record.get("decisionBestCardIndex"),
                    "decisionBestScore": record.get("decisionBestScore"),
                }
            )
        elif previous_analyses:
            # r13 records reanalyzed by the older script already contain the
            # candidate snapshot but not its matching summary/decision. The
            # current top-level text still belongs to that archived revision,
            # so complete the archive before replacing it with r14 wording.
            latest = previous_analyses[-1]
            if latest.get("analysisRevision") != ANALYZER_VERSION:
                latest.setdefault("decisionCandidates", copy.deepcopy(decision_candidates))
                latest.setdefault("summary", record.get("summary"))
                latest.setdefault("decision", record.get("decision"))
                latest.setdefault("bestCardIndex", record.get("bestCardIndex"))
                latest.setdefault("bestScore", record.get("bestScore"))
                latest.setdefault("decisionBestCardIndex", record.get("decisionBestCardIndex"))
                latest.setdefault("decisionBestScore", record.get("decisionBestScore"))

        patch: dict = {
            "candidates": candidates,
            "decisionCandidates": copy.deepcopy(candidates),
            "previousAnalyses": previous_analyses[-3:],
            "reanalyzedAt": archived_at,
        }
        # Reanalysis updates the current factor evidence, never the action that
        # actually happened. A historical auto-reject must continue to say why
        # it was rejected at the time, even when a newer rule now recognizes a
        # valid candidate. Older reanalysis scripts rewrote this text; repair it
        # from the archived revision when encountered.
        if needs_historical_text_repair and latest_historical is not None:
            patch.update(
                {
                    "summary": latest_historical.get("summary"),
                    "decision": latest_historical.get("decision"),
                }
            )
        store.update(str(record["id"]), **patch)
        updated += 1
        action = "repair" if current_revision == ANALYZER_VERSION else f"{current_revision} -> {ANALYZER_VERSION}"
        print(f"{record['id']}: {action}")

    print(f"updated {updated} audit record(s)")


if __name__ == "__main__":
    main()
