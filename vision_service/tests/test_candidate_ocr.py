from __future__ import annotations

import cv2
import numpy as np
from types import SimpleNamespace

from candidate_ocr import (
    _clean_name_value,
    _page_signature,
    _recognize_batch,
    _single_han,
    candidate_layout,
    selected_candidate,
    selected_keyboard_key,
)


def test_candidate_slots_are_recognized_in_one_batch() -> None:
    class FakeRecognizer:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, request: object) -> SimpleNamespace:
            self.calls += 1
            images = getattr(request, "img")
            return SimpleNamespace(
                txts=tuple("明" for _image in images),
                scores=tuple(0.99 for _image in images),
            )

    recognizer = FakeRecognizer()
    engine = SimpleNamespace(text_rec=recognizer)
    crops = [np.full((80, 80, 3), 220, dtype=np.uint8) for _index in range(15)]
    results = _recognize_batch(engine, crops)  # type: ignore[arg-type]
    assert recognizer.calls == 1
    assert len(results) == 15
    assert all(slot[0].text == "明" for slot in results)


def test_single_han_rejects_words_and_non_han_text() -> None:
    assert _single_han("明") == "明"
    assert _single_han(" 明 ") == "明"
    assert _single_han("明白") == ""
    assert _single_han("ming") == ""


def test_candidate_layout_distinguishes_fixed_single_slots_from_phrases() -> None:
    assert candidate_layout(["名"] + ["明"] * 14) == "singleCharacters"
    assert candidate_layout(["名", "", "明", "", "命", "", "鸣", "", "", "", "", "", "", ""]) == "phrases"
    assert candidate_layout(["", "", ""]) == "unknown"


def test_page_signature_uses_stable_ocr_text_when_enough_slots_are_read() -> None:
    texts = ["明", "命", "鸣", "冥", "暝", "铭", "名", "茗", "螟", "溟"]
    dark = np.zeros((80, 800, 3), dtype=np.uint8)
    bright = np.full((80, 800, 3), 255, dtype=np.uint8)
    assert _page_signature(texts, dark) == _page_signature(texts, bright)


def _teal_bgr() -> tuple[int, int, int]:
    hsv = np.uint8([[[85, 220, 220]]])
    return tuple(int(value) for value in cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0])


def test_detects_highlighted_candidate_slot() -> None:
    strip = np.full((106, 1_805, 3), 160, dtype=np.uint8)
    center = round((0.104 + 1 * 0.0562) * strip.shape[1])
    cv2.rectangle(strip, (center - 42, 14), (center + 42, 94), _teal_bgr(), 5)
    index, confidence = selected_candidate(strip)
    assert index == 1
    assert confidence >= 0.5


def test_detects_highlighted_keyboard_key() -> None:
    image = np.full((1_080, 1_920, 3), 160, dtype=np.uint8)
    center = (round((0.068 + 4 * 0.0757) * 1_920), round((0.572 + 2 * 0.0785) * 1_080))
    cv2.rectangle(
        image,
        (center[0] - 62, center[1] - 35),
        (center[0] + 62, center[1] + 35),
        _teal_bgr(),
        6,
    )
    key, confidence = selected_keyboard_key(image)
    assert key == "g"
    assert confidence >= 0.5


def test_clean_name_value_keeps_only_entered_name_characters() -> None:
    assert _clean_name_value(" 小森| ") == "小森"
    assert _clean_name_value("示例aq9") == "示例aq9"
