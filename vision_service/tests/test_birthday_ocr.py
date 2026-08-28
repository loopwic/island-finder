from __future__ import annotations

import numpy as np

from birthday_ocr import _crop_normalized, _numeric_text


def test_numeric_text_accepts_ascii_and_fullwidth_digits_only() -> None:
    assert _numeric_text("10") == "10"
    assert _numeric_text("２９日") == "29"
    assert _numeric_text("月") == ""


def test_normalized_crop_uses_native_frame_coordinates() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    crop = _crop_normalized(image, (0.25, 0.2, 0.75, 0.8))
    assert crop.shape == (60, 100, 3)
