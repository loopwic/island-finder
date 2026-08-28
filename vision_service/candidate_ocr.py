from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from threading import Lock
import unicodedata

import cv2
import numpy as np
from rapidocr import RapidOCR
from rapidocr.ch_ppocr_rec.typings import TextRecInput


# Measured against the 1080p Switch Chinese IME. The crop passed to this
# module spans x=0.03..0.97 of the full frame. Arrow controls sit outside this
# range of centers; these 15 positions are the actual selectable candidates.
CANDIDATE_FIRST_CENTER = 0.104
CANDIDATE_CENTER_STEP = 0.0562
CANDIDATE_SLOT_COUNT = 15
CANDIDATE_HALF_WIDTH = 0.024

KEYBOARD_X_ORIGIN = 0.068
KEYBOARD_X_STEP = 0.0757
KEYBOARD_Y_ORIGIN = 0.572
KEYBOARD_Y_STEP = 0.0785
KEYBOARD_ROWS = (
    "1234567890-",
    "qwertyuiop/",
    "asdfghjkl:\\",
    "zxcvbnm,.?!",
)


@dataclass(frozen=True)
class Recognition:
    text: str
    score: float


_engine: RapidOCR | None = None
_engine_lock = Lock()


def _get_engine() -> RapidOCR:
    global _engine
    if _engine is None:
        # A dedicated recognizer is kept for the service lifetime. RapidOCR
        # mutates call-time flags, so initialization and inference share the
        # same lock in recognize_candidate_strip.
        # All 15 fixed candidate crops fit comfortably in one recognizer batch.
        # This turns 15 sequential ONNX calls into a single vectorized call.
        _engine = RapidOCR(
            params={
                "Global.log_level": "error",
                "Rec.rec_batch_num": CANDIDATE_SLOT_COUNT,
            }
        )
    return _engine


def _single_han(value: str) -> str:
    characters = [
        character
        for character in value.strip()
        if "CJK UNIFIED IDEOGRAPH" in unicodedata.name(character, "")
        or "CJK COMPATIBILITY IDEOGRAPH" in unicodedata.name(character, "")
    ]
    return characters[0] if len(characters) == 1 else ""


def _recognition_variants(crop: np.ndarray) -> list[np.ndarray]:
    enlarged = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(gray)
    clahe = cv2.resize(clahe, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.cvtColor(clahe, cv2.COLOR_GRAY2BGR)
    return [enlarged, clahe]


def _recognize_one(engine: RapidOCR, crop: np.ndarray) -> list[Recognition]:
    return _recognize_batch(engine, [crop])[0]


def _batch_output(engine: RapidOCR, images: list[np.ndarray]) -> list[Recognition]:
    output = engine.text_rec(TextRecInput(img=images, return_word_box=False))
    texts = getattr(output, "txts", None) or ()
    scores = getattr(output, "scores", None) or ()
    results: list[Recognition] = []
    for index in range(len(images)):
        text = _single_han(str(texts[index])) if index < len(texts) else ""
        score = float(scores[index]) if index < len(scores) and text else 0.0
        results.append(Recognition(text=text, score=score))
    return results


def _recognize_batch(
    engine: RapidOCR,
    crops: list[np.ndarray],
) -> list[list[Recognition]]:
    variants = [_recognition_variants(crop) for crop in crops]
    primary = _batch_output(engine, [item[0] for item in variants])
    results = [[item] for item in primary]
    fallback_indices = [
        index
        for index, item in enumerate(primary)
        if not item.text or item.score < 0.82
    ]
    if fallback_indices:
        fallback = _batch_output(
            engine,
            [variants[index][1] for index in fallback_indices],
        )
        for index, item in zip(fallback_indices, fallback, strict=True):
            results[index].append(item)
    return results


def _page_signature(texts: list[str], strip: np.ndarray) -> str:
    recognized = [text for text in texts if text]
    if len(recognized) >= 4:
        return sha1("|".join(texts).encode("utf-8")).hexdigest()[:16]
    # A small high-pass fingerprint keeps empty or low-confidence pages
    # distinguishable while suppressing the animated scene visible behind the
    # translucent candidate bar.
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    high_pass = cv2.absdiff(gray, cv2.GaussianBlur(gray, (9, 9), 0))
    fingerprint = cv2.resize(high_pass, (32, 8), interpolation=cv2.INTER_AREA)
    threshold = float(np.median(fingerprint))
    bits = np.packbits((fingerprint > threshold).astype(np.uint8)).tobytes()
    return sha1(bits).hexdigest()[:16]


def _candidate_boxes(strip: np.ndarray) -> list[dict[str, int]]:
    height, width = strip.shape[:2]
    boxes: list[dict[str, int]] = []
    for index in range(CANDIDATE_SLOT_COUNT):
        center = (CANDIDATE_FIRST_CENTER + index * CANDIDATE_CENTER_STEP) * width
        x0 = max(0, round(center - CANDIDATE_HALF_WIDTH * width))
        x1 = min(width, round(center + CANDIDATE_HALF_WIDTH * width))
        y0 = max(0, round(height * 0.02))
        y1 = min(height, round(height * 0.98))
        boxes.append(
            {
                "index": index,
                "x": x0,
                "y": y0,
                "width": x1 - x0,
                "height": y1 - y0,
            }
        )
    return boxes


def candidate_layout(texts: list[str]) -> str:
    recognized_slot_count = sum(bool(text) for text in texts)
    if recognized_slot_count >= 11:
        return "singleCharacters"
    if recognized_slot_count >= 2:
        return "phrases"
    return "unknown"


def _teal_mask(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    return (
        (hue >= 64)
        & (hue <= 106)
        & (saturation >= 48)
        & (value >= 72)
    ).astype(np.uint8) * 255


def selected_candidate(strip: np.ndarray) -> tuple[int | None, float]:
    mask = _teal_mask(strip)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    strip_area = max(1, strip.shape[0] * strip.shape[1])
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        x, y, width, height = cv2.boundingRect(contour)
        if area / strip_area < 0.0015 or height < strip.shape[0] * 0.35:
            continue
        candidates.append((area, (x, y, width, height)))
    if not candidates:
        return None, 0.0
    area, (x, _y, width, _height) = max(candidates, key=lambda item: item[0])
    center = x + width / 2
    centers = [
        (CANDIDATE_FIRST_CENTER + index * CANDIDATE_CENTER_STEP) * strip.shape[1]
        for index in range(CANDIDATE_SLOT_COUNT)
    ]
    index = min(range(CANDIDATE_SLOT_COUNT), key=lambda item: abs(centers[item] - center))
    distance = abs(centers[index] - center) / max(1.0, CANDIDATE_CENTER_STEP * strip.shape[1])
    confidence = max(0.0, min(1.0, area / (strip_area * 0.008))) * max(0.0, 1.0 - distance)
    return index, confidence


def selected_keyboard_key(image: np.ndarray) -> tuple[str | None, float]:
    height, width = image.shape[:2]
    y0 = round(height * 0.53)
    y1 = round(height * 0.94)
    x0 = round(width * 0.03)
    x1 = round(width * 0.97)
    roi = image[y0:y1, x0:x1]
    mask = _teal_mask(roi)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = max(1, height * width)
    nodes: list[tuple[str, float, float]] = []
    for row_index, keys in enumerate(KEYBOARD_ROWS):
        for column_index, key in enumerate(keys):
            nodes.append(
                (
                    key,
                    KEYBOARD_X_ORIGIN + column_index * KEYBOARD_X_STEP,
                    KEYBOARD_Y_ORIGIN + row_index * KEYBOARD_Y_STEP,
                )
            )
    matches: list[tuple[float, str]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        x, y, contour_width, contour_height = cv2.boundingRect(contour)
        if area / frame_area < 0.00018 or contour_width < width * 0.025 or contour_height < height * 0.025:
            continue
        center_x = (x0 + x + contour_width / 2) / width
        center_y = (y0 + y + contour_height / 2) / height
        key, node_x, node_y = min(
            nodes,
            key=lambda node: ((node[1] - center_x) / KEYBOARD_X_STEP) ** 2
            + ((node[2] - center_y) / KEYBOARD_Y_STEP) ** 2,
        )
        distance = (
            ((node_x - center_x) / KEYBOARD_X_STEP) ** 2
            + ((node_y - center_y) / KEYBOARD_Y_STEP) ** 2
        ) ** 0.5
        if distance <= 0.58:
            score = max(0.0, min(1.0, area / (frame_area * 0.0012))) * max(0.0, 1.0 - distance)
            matches.append((score, key))
    if not matches:
        return None, 0.0
    score, key = max(matches)
    return key, score


def _clean_name_value(value: str) -> str:
    return "".join(
        character
        for character in value.strip().replace(" ", "")
        if character.isascii() and character.isalnum()
        or "CJK UNIFIED IDEOGRAPH" in unicodedata.name(character, "")
        or "CJK COMPATIBILITY IDEOGRAPH" in unicodedata.name(character, "")
    )


def recognize_name_value(image: np.ndarray) -> tuple[str, float]:
    height, width = image.shape[:2]
    crop = image[
        round(height * 0.20) : round(height * 0.31),
        round(width * 0.32) : round(width * 0.68),
    ]
    results: list[tuple[str, float]] = []
    with _engine_lock:
        engine = _get_engine()
        for scale in (2, 3):
            enlarged = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            output = engine(
                enlarged,
                use_det=False,
                use_cls=False,
                use_rec=True,
                text_score=0.0,
            )
            texts = getattr(output, "txts", None) or ()
            scores = getattr(output, "scores", None) or ()
            raw_text = str(texts[0]) if texts else ""
            text = _clean_name_value(raw_text)
            score = float(scores[0]) if scores and text else 0.0
            results.append((text, score))
            if text and score >= 0.90:
                break
    return max(results, key=lambda item: item[1], default=("", 0.0))


def recognize_candidate_strip(strip: np.ndarray, target: str) -> dict[str, object]:
    if strip.size == 0:
        raise ValueError("候选栏画面为空")
    if len(target) != 1 or not _single_han(target):
        raise ValueError("候选栏目标必须是单个汉字")

    boxes = _candidate_boxes(strip)
    texts: list[str] = []
    ocr_scores: list[float] = []
    target_scores: list[float] = []
    target_votes: list[int] = []

    crops = [
        strip[
            box["y"] : box["y"] + box["height"],
            box["x"] : box["x"] + box["width"],
        ]
        for box in boxes
    ]
    with _engine_lock:
        variants_by_slot = _recognize_batch(_get_engine(), crops)
    for index, variants in enumerate(variants_by_slot):
        best = max(variants, key=lambda item: item.score)
        exact_scores = [item.score for item in variants if item.text == target]
        exact_score = max(exact_scores, default=0.0)

        texts.append(best.text)
        ocr_scores.append(best.score)
        target_scores.append(exact_score)
        target_votes.append(sum(item.text == target for item in variants))

    ranking = sorted(range(len(target_scores)), key=target_scores.__getitem__, reverse=True)
    best_position = ranking[0]
    best_score = target_scores[best_position]
    second_score = target_scores[ranking[1]] if len(ranking) > 1 else 0.0
    layout = candidate_layout(texts)
    # Exact character agreement is much safer than approximate glyph distance.
    # One very strong prediction is sufficient; otherwise both preprocessing
    # variants must agree before the endpoint reports a match.
    matched = layout == "singleCharacters" and (
        best_score >= 0.80
        or (target_votes[best_position] >= 2 and best_score >= 0.55)
    )

    selected_index, selected_confidence = selected_candidate(strip)
    return {
        "matched": matched,
        "index": best_position if matched else None,
        "candidateCount": CANDIDATE_SLOT_COUNT,
        "confidence": best_score,
        "bestScore": best_score,
        "margin": max(0.0, best_score - second_score),
        "scores": target_scores,
        "ocrScores": ocr_scores,
        "texts": texts,
        "layout": layout,
        "pageSignature": _page_signature(texts, strip),
        "boxes": boxes,
        "selectedIndex": selected_index,
        "selectedConfidence": selected_confidence,
    }


def recognize_candidate_selection(
    strip: np.ndarray,
    target: str,
    target_index: int,
) -> dict[str, object]:
    if strip.size == 0:
        raise ValueError("候选栏画面为空")
    if len(target) != 1 or not _single_han(target):
        raise ValueError("候选栏目标必须是单个汉字")
    if target_index < 0 or target_index >= CANDIDATE_SLOT_COUNT:
        raise ValueError("候选栏目标位置无效")

    boxes = _candidate_boxes(strip)
    box = boxes[target_index]
    x0 = box["x"]
    y0 = box["y"]
    crop = strip[
        y0 : y0 + box["height"],
        x0 : x0 + box["width"],
    ]
    with _engine_lock:
        variants = _recognize_one(_get_engine(), crop)
    best = max(variants, key=lambda item: item.score)
    exact_scores = [item.score for item in variants if item.text == target]
    exact_score = max(exact_scores, default=0.0)
    target_votes = sum(item.text == target for item in variants)
    matched = exact_score >= 0.80 or (target_votes >= 2 and exact_score >= 0.55)
    texts = [""] * CANDIDATE_SLOT_COUNT
    texts[target_index] = best.text
    scores = [0.0] * CANDIDATE_SLOT_COUNT
    scores[target_index] = exact_score
    ocr_scores = [0.0] * CANDIDATE_SLOT_COUNT
    ocr_scores[target_index] = best.score
    selected_index, selected_confidence = selected_candidate(strip)
    return {
        "matched": matched,
        "index": target_index if matched else None,
        "candidateCount": CANDIDATE_SLOT_COUNT,
        "confidence": exact_score,
        "bestScore": exact_score,
        "margin": exact_score,
        "scores": scores,
        "ocrScores": ocr_scores,
        "texts": texts,
        "layout": "singleCharacters" if matched else "unknown",
        "pageSignature": _page_signature(texts, strip),
        "boxes": boxes,
        "selectedIndex": selected_index,
        "selectedConfidence": selected_confidence,
    }


def _empty_candidate_result(strip: np.ndarray) -> dict[str, object]:
    selected_index, selected_confidence = selected_candidate(strip)
    texts = [""] * CANDIDATE_SLOT_COUNT
    return {
        "matched": False,
        "index": None,
        "candidateCount": CANDIDATE_SLOT_COUNT,
        "confidence": 0.0,
        "bestScore": 0.0,
        "margin": 0.0,
        "scores": [0.0] * CANDIDATE_SLOT_COUNT,
        "ocrScores": [0.0] * CANDIDATE_SLOT_COUNT,
        "texts": texts,
        "layout": "unknown",
        "pageSignature": _page_signature(texts, strip),
        "boxes": _candidate_boxes(strip),
        "selectedIndex": selected_index,
        "selectedConfidence": selected_confidence,
    }


def recognize_keyboard_frame(
    image: np.ndarray,
    target: str,
    scope: str = "full",
    target_index: int | None = None,
) -> dict[str, object]:
    if scope not in {"full", "name", "scan", "highlight", "selection"}:
        raise ValueError("无效的键盘 OCR 范围")
    height, width = image.shape[:2]
    bar_x = round(width * 0.03)
    bar_y = round(height * 0.448)
    bar_width = round(width * 0.94)
    bar_height = round(height * 0.098)
    strip = image[bar_y : bar_y + bar_height, bar_x : bar_x + bar_width]
    if scope in {"full", "scan"}:
        result = recognize_candidate_strip(strip, target)
    elif scope == "selection":
        if target_index is None:
            raise ValueError("候选高亮复核缺少目标位置")
        result = recognize_candidate_selection(strip, target, target_index)
    else:
        result = _empty_candidate_result(strip)

    if scope in {"full", "name"}:
        key, key_confidence = selected_keyboard_key(image)
        name_value, name_score = recognize_name_value(image)
    else:
        key, key_confidence = None, 0.0
        name_value, name_score = "", 0.0
    result.update(
        {
            "selectedKey": key,
            "selectedKeyConfidence": key_confidence,
            "nameValue": name_value,
            "nameScore": name_score,
            "scope": scope,
            "candidateBar": {
                "x": bar_x,
                "y": bar_y,
                "width": bar_width,
                "height": bar_height,
            },
        }
    )
    return result
