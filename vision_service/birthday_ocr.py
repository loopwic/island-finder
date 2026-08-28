from __future__ import annotations

from dataclasses import dataclass
import re

import cv2
import numpy as np

from candidate_ocr import _engine_lock, _get_engine


@dataclass(frozen=True)
class NumericRecognition:
    value: int | None
    score: float
    text: str


def _numeric_text(value: str) -> str:
    normalized = value.strip().translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    match = re.search(r"\d{1,2}", normalized)
    return match.group(0) if match else ""


def _recognize_number(crop: np.ndarray) -> NumericRecognition:
    if crop.size == 0:
        return NumericRecognition(value=None, score=0.0, text="")
    variants = [
        cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
        cv2.resize(
            cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY),
            None,
            fx=3,
            fy=3,
            interpolation=cv2.INTER_CUBIC,
        ),
    ]
    results: list[NumericRecognition] = []
    engine = _get_engine()
    for variant in variants:
        output = engine(
            variant,
            use_det=False,
            use_cls=False,
            use_rec=True,
            text_score=0.0,
        )
        texts = getattr(output, "txts", None) or ()
        scores = getattr(output, "scores", None) or ()
        raw_text = str(texts[0]) if texts else ""
        digits = _numeric_text(raw_text)
        score = float(scores[0]) if scores and digits else 0.0
        results.append(
            NumericRecognition(
                value=int(digits) if digits else None,
                score=score,
                text=raw_text,
            )
        )
    return max(results, key=lambda item: item.score)


def _crop_normalized(
    image: np.ndarray,
    bounds: tuple[float, float, float, float],
) -> np.ndarray:
    height, width = image.shape[:2]
    x0, y0, x1, y1 = bounds
    return image[
        round(y0 * height) : round(y1 * height),
        round(x0 * width) : round(x1 * width),
    ]


def recognize_birthday(image: np.ndarray) -> dict[str, object]:
    if image.size == 0:
        raise ValueError("生日画面为空")

    # Tight digit-only crops measured from the native 16:9 Switch frame.
    # Excluding 月/日 and the confirm button prevents them from influencing
    # recognition. Both one- and two-digit values fit inside these regions.
    month_crop = _crop_normalized(image, (0.31, 0.37, 0.39, 0.54))
    day_crop = _crop_normalized(image, (0.44, 0.37, 0.52, 0.54))
    with _engine_lock:
        month = _recognize_number(month_crop)
        day = _recognize_number(day_crop)

    month_valid = month.value is not None and 1 <= month.value <= 12
    day_valid = day.value is not None and 1 <= day.value <= 31
    confidence = min(month.score, day.score) if month_valid and day_valid else 0.0
    return {
        "month": month.value if month_valid else None,
        "day": day.value if day_valid else None,
        "confidence": confidence,
        "monthScore": month.score,
        "dayScore": day.score,
        "rawTexts": [month.text, day.text],
        "visionEngine": "rapidocr",
    }
