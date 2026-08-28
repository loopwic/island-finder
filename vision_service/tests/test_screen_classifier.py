from __future__ import annotations

import cv2
import numpy as np

from screen_classifier import classify_screen


REGIONS = [
    (0.249, 0.291, 0.232, 0.253),
    (0.52, 0.296, 0.232, 0.251),
    (0.2495, 0.5715, 0.23, 0.247),
    (0.5205, 0.5685, 0.2305, 0.2525),
]
def _frame(color: tuple[int, int, int] = (205, 226, 218)) -> np.ndarray:
    return np.full((1080, 1920, 3), color, dtype=np.uint8)


def _system_home_fixture() -> np.ndarray:
    image = np.full((1080, 1920, 3), 244, dtype=np.uint8)
    palette = [
        (40, 165, 235),
        (215, 80, 65),
        (75, 190, 85),
        (185, 70, 205),
        (45, 205, 220),
    ]
    for cover in range(5):
        left = 90 + cover * 355
        right = left + 310
        cv2.rectangle(image, (left, 225), (right, 685), palette[cover], -1)
        for row in range(10):
            for column in range(7):
                color = palette[(cover + row + column + 1) % len(palette)]
                x0 = left + 8 + column * 43
                y0 = 233 + row * 43
                cv2.rectangle(image, (x0, y0), (x0 + 28, y0 + 28), color, -1)
    for index in range(9):
        cv2.circle(image, (430 + index * 135, 815), 24, (150, 150, 150), 4)
    return image


def _account_picker_fixture() -> np.ndarray:
    image = np.full((1080, 1920, 3), 244, dtype=np.uint8)
    palette = [(55, 165, 230), (210, 85, 70), (80, 180, 90), (175, 75, 195)]
    for cover in range(5):
        left = 90 + cover * 355
        cv2.rectangle(image, (left, 210), (left + 310, 430), palette[cover % 4], -1)
        for stripe in range(8):
            y = 218 + stripe * 25
            cv2.line(
                image,
                (left + 10, y),
                (left + 300, y + 18),
                palette[(cover + stripe + 1) % 4],
                8,
            )
    cv2.rectangle(image, (0, 454), (1919, 1079), (246, 246, 246), -1)
    cv2.circle(image, (960, 650), 92, (224, 224, 224), -1)
    cv2.circle(image, (960, 650), 92, (70, 70, 70), 7)
    for row in range(7):
        width = 420 - row * 25
        y = 760 + row * 24
        cv2.rectangle(image, (960 - width // 2, y), (960 + width // 2, y + 8), (80, 80, 80), -1)
    return image


def test_no_signal_stops_input() -> None:
    result = classify_screen(np.zeros((1080, 1920, 3), dtype=np.uint8), REGIONS)
    assert result.kind == "noSignal"
    assert result.confidence >= 0.9


def test_dark_frame_with_colored_loading_icon_is_not_no_signal() -> None:
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    cv2.circle(image, (1740, 930), 70, (55, 185, 95), -1)
    cv2.circle(image, (1785, 975), 48, (215, 178, 65), -1)
    result = classify_screen(image, REGIONS)
    assert result.kind == "loading"
    assert result.confidence >= 0.72


def test_large_dialogue_bubble_is_not_birthday_without_confirm_button() -> None:
    image = _frame((120, 142, 130))
    cv2.ellipse(image, (960, 790), (650, 250), 0, 0, 360, (225, 239, 239), -1)
    result = classify_screen(image, REGIONS)
    assert result.kind == "dialogue"


def test_ns2_home_menu_geometry_never_falls_through_to_dialogue() -> None:
    image = _system_home_fixture()
    result = classify_screen(image, REGIONS)

    assert result.kind == "homeMenu"
    assert result.confidence >= 0.85
    assert result.signals["homeTopNeutral"] >= 0.88
    assert result.signals["homeGameColor"] >= 0.20
    assert result.signals["homeIconNeutral"] >= 0.78


def test_ns2_account_picker_geometry_never_falls_through_to_dialogue() -> None:
    image = _account_picker_fixture()
    result = classify_screen(image, REGIONS)

    assert result.kind == "accountPicker"
    assert result.confidence >= 0.85
    assert result.signals["accountTopNeutral"] >= 0.90
    assert result.signals["accountCoverColor"] >= 0.12
    assert result.signals["accountPanelNeutral"] >= 0.90
    assert result.signals["accountPanelColor"] <= 0.06


def test_birthday_form_wins_over_generic_teal_choice_button() -> None:
    image = _frame((170, 196, 182))
    cv2.rectangle(image, (320, 150), (1600, 880), (225, 239, 239), -1)
    teal_hsv = np.uint8([[[85, 175, 210]]])
    teal_bgr = tuple(
        int(value) for value in cv2.cvtColor(teal_hsv, cv2.COLOR_HSV2BGR)[0, 0]
    )
    cv2.rectangle(image, (470, 320), (730, 690), teal_bgr, 34)
    cv2.rectangle(image, (840, 320), (1100, 690), teal_bgr, 34)
    cv2.rectangle(image, (1210, 400), (1530, 650), teal_bgr, -1)
    for y in range(265, 760, 68):
        cv2.line(image, (410, y), (1160, y), (82, 94, 88), 7)
    result = classify_screen(image, REGIONS)
    assert result.kind == "birthdayPicker"


def test_avatar_confirmation_is_not_mistaken_for_birthday_form() -> None:
    image = _frame((170, 196, 182))
    cv2.ellipse(image, (1250, 610), (560, 340), 0, 0, 360, (225, 239, 239), -1)
    skin_hsv = np.uint8([[[14, 105, 215]]])
    skin_bgr = tuple(
        int(value) for value in cv2.cvtColor(skin_hsv, cv2.COLOR_HSV2BGR)[0, 0]
    )
    cv2.circle(image, (480, 410), 155, skin_bgr, -1)
    teal_hsv = np.uint8([[[85, 175, 210]]])
    teal_bgr = tuple(
        int(value) for value in cv2.cvtColor(teal_hsv, cv2.COLOR_HSV2BGR)[0, 0]
    )
    cv2.rectangle(image, (1060, 475), (1510, 615), teal_bgr, -1)
    cv2.rectangle(image, (1060, 655), (1510, 795), teal_bgr, -1)
    result = classify_screen(image, REGIONS)
    assert result.kind == "choiceDialog"
    assert result.signals["birthdayAvatarSkin"] >= 0.055


def test_detects_appearance_editor_geometry() -> None:
    image = _frame()
    cv2.rectangle(image, (920, 55), (1790, 290), (65, 184, 102), -1)
    colors = [(150, 190, 235), (120, 166, 218), (105, 150, 205), (85, 126, 180)]
    for row in range(2):
        for column in range(4):
            cv2.circle(image, (1080 + column * 205, 440 + row * 170), 72, colors[column], -1)
    cv2.rectangle(image, (1100, 760), (1660, 930), (177, 205, 76), -1)
    result = classify_screen(image, REGIONS)
    assert result.kind == "appearanceEditor"
    assert result.confidence >= 0.7


def test_detects_wide_dialogue_bubble() -> None:
    image = _frame((95, 118, 104))
    cv2.ellipse(image, (960, 790), (650, 250), 0, 0, 360, (220, 239, 244), -1)
    cv2.circle(image, (960, 1000), 18, (45, 190, 245), -1)
    result = classify_screen(image, REGIONS)
    assert result.kind == "dialogue"


def test_detects_upper_right_yellow_choice_bubble_before_dialogue() -> None:
    image = _frame((95, 118, 104))
    cv2.ellipse(image, (900, 790), (610, 245), 0, 0, 360, (220, 239, 244), -1)
    yellow_hsv = np.uint8([[[30, 92, 235]]])
    yellow_bgr = tuple(
        int(value) for value in cv2.cvtColor(yellow_hsv, cv2.COLOR_HSV2BGR)[0, 0]
    )
    cv2.ellipse(image, (1570, 220), (300, 145), 0, 0, 360, yellow_bgr, -1)
    result = classify_screen(image, REGIONS)
    assert result.kind == "choiceDialog"
    assert result.signals["yellowChoice"] >= 0.48


def test_detects_compact_region_choice_bubble_before_dialogue() -> None:
    image = _frame((95, 118, 104))
    cv2.ellipse(image, (900, 790), (610, 245), 0, 0, 360, (220, 239, 244), -1)
    yellow_hsv = np.uint8([[[30, 92, 235]]])
    yellow_bgr = tuple(
        int(value) for value in cv2.cvtColor(yellow_hsv, cv2.COLOR_HSV2BGR)[0, 0]
    )
    # The region/hemisphere picker is compact enough that its old component
    # score fell below 0.42 even though it is clearly a horizontal choice.
    cv2.ellipse(image, (1580, 240), (210, 130), 0, 0, 360, yellow_bgr, -1)
    result = classify_screen(image, REGIONS)
    assert result.kind == "choiceDialog"
    assert result.signals["yellowChoiceArea"] >= 0.075
    assert result.signals["yellowChoiceComponent"] >= 0.22


def test_round_upper_right_character_does_not_turn_dialogue_into_choice() -> None:
    image = _frame((95, 118, 104))
    cv2.ellipse(image, (900, 790), (610, 245), 0, 0, 360, (220, 239, 244), -1)
    brown_hsv = np.uint8([[[27, 105, 205]]])
    brown_bgr = tuple(
        int(value) for value in cv2.cvtColor(brown_hsv, cv2.COLOR_HSV2BGR)[0, 0]
    )
    cv2.circle(image, (1540, 215), 125, brown_bgr, -1)
    result = classify_screen(image, REGIONS)
    assert result.kind == "dialogue"


def test_detects_keyboard_grid_before_pale_dialogue_geometry() -> None:
    image = _frame((165, 185, 172))
    cv2.rectangle(image, (80, 310), (1840, 980), (115, 135, 128), -1)
    for row in range(4):
        for column in range(10):
            x0 = 120 + column * 165
            y0 = 370 + row * 125
            cv2.rectangle(image, (x0, y0), (x0 + 125, y0 + 82), (196, 210, 194), -1)
    result = classify_screen(image, REGIONS)
    assert result.kind == "nameKeyboard"


def test_detects_four_map_cards() -> None:
    image = _frame((200, 215, 205))
    for x, y, width, height in REGIONS:
        x0, y0 = round(x * 1920), round(y * 1080)
        x1, y1 = round((x + width) * 1920), round((y + height) * 1080)
        cv2.rectangle(image, (x0, y0), (x1, y1), (190, 182, 80), -1)
        cv2.ellipse(
            image,
            ((x0 + x1) // 2, (y0 + y1) // 2),
            ((x1 - x0) // 3, (y1 - y0) // 3),
            0,
            0,
            360,
            (75, 170, 70),
            -1,
        )
    result = classify_screen(image, REGIONS)
    assert result.kind == "mapSelection"
    assert result.confidence >= 0.75


def test_detects_map_cards_from_low_power_transport_frame() -> None:
    image = _frame((200, 215, 205))
    for x, y, width, height in REGIONS:
        x0, y0 = round(x * 1920), round(y * 1080)
        x1, y1 = round((x + width) * 1920), round((y + height) * 1080)
        cv2.rectangle(image, (x0, y0), (x1, y1), (190, 182, 80), -1)
        cv2.ellipse(
            image,
            ((x0 + x1) // 2, (y0 + y1) // 2),
            ((x1 - x0) // 3, (y1 - y0) // 3),
            0,
            0,
            360,
            (75, 170, 70),
            -1,
        )
    low_power_frame = cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA)
    result = classify_screen(low_power_frame, REGIONS)
    assert result.kind == "mapSelection"
    assert result.confidence >= 0.75
