from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np


ScreenKind = Literal[
    "noSignal",
    "loading",
    "nameKeyboard",
    "birthdayPicker",
    "styleChoice",
    "appearanceEditor",
    "choiceDialog",
    "mapSelection",
    "homeMenu",
    "accountPicker",
    "dialogue",
    "startupPrompt",
    "unknown",
]


@dataclass(frozen=True)
class ScreenResult:
    kind: ScreenKind
    confidence: float
    signals: dict[str, float]

    def as_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "confidence": round(float(self.confidence), 4),
            "signals": {key: round(float(value), 4) for key, value in self.signals.items()},
        }


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _crop(image: np.ndarray, region: tuple[float, float, float, float]) -> np.ndarray:
    height, width = image.shape[:2]
    x, y, region_width, region_height = region
    x0 = max(0, min(width - 1, round(x * width)))
    y0 = max(0, min(height - 1, round(y * height)))
    x1 = max(x0 + 1, min(width, round((x + region_width) * width)))
    y1 = max(y0 + 1, min(height, round((y + region_height) * height)))
    return image[y0:y1, x0:x1]


def _fraction(mask: np.ndarray, region: tuple[float, float, float, float] | None = None) -> float:
    target = _crop(mask, region) if region is not None else mask
    return float(np.count_nonzero(target)) / max(1, target.size)


def _wide_component_score(mask: np.ndarray, region: tuple[float, float, float, float]) -> float:
    target = _crop(mask, region)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(target, 8)
    if count <= 1:
        return 0.0
    height, width = target.shape
    best = 0.0
    for index in range(1, count):
        _x, _y, component_width, component_height, area = (int(value) for value in stats[index])
        width_ratio = component_width / max(1, width)
        height_ratio = component_height / max(1, height)
        area_ratio = area / max(1, target.size)
        score = (
            _clamp01((width_ratio - 0.28) / 0.55) * 0.46
            + _clamp01((height_ratio - 0.12) / 0.66) * 0.24
            + _clamp01((area_ratio - 0.08) / 0.55) * 0.30
        )
        best = max(best, score)
    return best


def _horizontal_bubble_score(
    mask: np.ndarray,
    region: tuple[float, float, float, float],
) -> float:
    """Find one large, clearly horizontal choice bubble, excluding faces/posters."""
    target = _crop(mask, region)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(target, 8)
    if count <= 1:
        return 0.0
    height, width = target.shape
    best = 0.0
    for index in range(1, count):
        _x, _y, component_width, component_height, area = (
            int(value) for value in stats[index]
        )
        width_ratio = component_width / max(1, width)
        height_ratio = component_height / max(1, height)
        area_ratio = area / max(1, target.size)
        aspect = component_width / max(1, component_height)
        if (
            aspect < 1.55
            or width_ratio < 0.48
            or height_ratio < 0.16
            or area_ratio < 0.055
        ):
            continue
        score = (
            _clamp01((aspect - 1.55) / 1.55) * 0.28
            + _clamp01((width_ratio - 0.48) / 0.48) * 0.34
            + _clamp01((area_ratio - 0.055) / 0.38) * 0.38
        )
        best = max(best, score)
    return best


def _keyboard_grid(gray: np.ndarray) -> tuple[int, int, float]:
    """Measure repeated rounded key faces arranged in three or more rows."""
    lower = _crop(gray, (0.03, 0.30, 0.94, 0.62))
    blurred = cv2.GaussianBlur(lower, (3, 3), 0)
    edges = cv2.Canny(blurred, 28, 92)
    edges = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
    )
    contours, _hierarchy = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    height, width = lower.shape
    centers: list[tuple[float, float]] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        area_ratio = box_width * box_height / max(1, width * height)
        aspect = box_width / max(1, box_height)
        if (
            0.0025 <= area_ratio <= 0.045
            and 0.75 <= aspect <= 4.8
            and box_width >= width * 0.035
            and box_height >= height * 0.055
        ):
            centers.append((x + box_width / 2, y + box_height / 2))

    row_centers: list[float] = []
    row_counts: list[int] = []
    for _x, center_y in sorted(centers, key=lambda point: point[1]):
        nearest = next(
            (
                index
                for index, row_center in enumerate(row_centers)
                if abs(center_y - row_center) <= height * 0.065
            ),
            None,
        )
        if nearest is None:
            row_centers.append(center_y)
            row_counts.append(1)
        else:
            count = row_counts[nearest]
            row_centers[nearest] = (row_centers[nearest] * count + center_y) / (count + 1)
            row_counts[nearest] = count + 1
    usable_rows = [count for count in row_counts if count >= 5]
    tile_count = sum(usable_rows)
    row_count = len(usable_rows)
    score = min(
        _clamp01((tile_count - 12) / 24),
        _clamp01((row_count - 1) / 3),
    )
    return tile_count, row_count, score


def _map_card_score(card: np.ndarray) -> float:
    if card.size == 0:
        return 0.0
    value = cv2.cvtColor(card, cv2.COLOR_BGR2HSV)[:, :, 2]
    bright_reference = float(np.percentile(value, 90))
    brightness_scale = min(2.4, max(1.0, 150.0 / max(1.0, bright_reference)))
    if brightness_scale > 1.02:
        card = cv2.convertScaleAbs(card, alpha=brightness_scale)
    blue, green, red = cv2.split(card)
    water = (
        (green.astype(np.int16) > red.astype(np.int16) + 10)
        & (blue.astype(np.int16) > red.astype(np.int16) + 7)
        & (green > 70)
        & (blue > 65)
    )
    grass = (
        (green.astype(np.int16) > red.astype(np.int16) + 15)
        & (green.astype(np.int16) > blue.astype(np.int16) + 8)
        & (green > 62)
    )
    water_ratio = float(np.count_nonzero(water)) / max(1, water.size)
    grass_ratio = float(np.count_nonzero(grass)) / max(1, grass.size)
    balance = min(
        _clamp01((water_ratio - 0.035) / 0.18),
        _clamp01((grass_ratio - 0.035) / 0.16),
    )
    coverage = _clamp01((water_ratio + grass_ratio - 0.13) / 0.42)
    return balance * 0.68 + coverage * 0.32


def classify_screen(
    image: np.ndarray,
    card_regions: list[tuple[float, float, float, float]] | None = None,
) -> ScreenResult:
    if image.size == 0:
        raise ValueError("原始画面为空")
    height, width = image.shape[:2]
    if width < 640 or height < 360:
        raise ValueError("原始画面分辨率不足")

    # Classification is scale-independent and starts from the complete frame;
    # the browser only downsizes/encodes it and never crops, thresholds, or
    # interprets the page. Fine map scoring uses separate lossless card crops.
    frame = cv2.resize(image, (480, 270), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    dark = value <= 34
    dark_dialogue_bright = (value >= 150) & (saturation <= 90)
    dark_dialogue_yellow = (
        (hue >= 15)
        & (hue <= 40)
        & (saturation >= 90)
        & (value >= 90)
    )
    # HDMI limited-range capture and the game's inactive/transition dimming can
    # lower the same cream dialogue bubble by roughly 35-45 value points.
    cream = (value >= 108) & (saturation <= 104)
    teal = (hue >= 68) & (hue <= 104) & (saturation >= 52) & (value >= 78)
    leaf_green = (hue >= 31) & (hue <= 72) & (saturation >= 65) & (value >= 72)
    skin = (hue <= 24) & (saturation >= 28) & (saturation <= 176) & (value >= 104)
    yellow = (hue >= 19) & (hue <= 38) & (saturation >= 90) & (value >= 120)
    # Setup questions use a large pale-yellow choice bubble in the upper-right.
    # Its saturation is much lower than the small yellow dialogue accents, so
    # keep a separate mask and require the lower dialogue bubble as context.
    pale_choice_yellow = (
        (hue >= 16)
        & (hue <= 43)
        & (saturation >= 32)
        & (saturation <= 210)
        & (value >= 118)
    )

    dark_ratio = _fraction(dark)
    luminance_mean = float(gray.mean()) / 255
    luminance_std = float(gray.std()) / 255
    colorful = (saturation >= 72) & (value >= 58)
    bright_neutral = (saturation <= 42) & (value >= 190)
    system_neutral = (saturation <= 48) & (value >= 140)
    loading_corner_color = _fraction(colorful, (0.80, 0.70, 0.20, 0.30))
    dark_dialogue_text = _fraction(
        dark_dialogue_bright,
        (0.20, 0.56, 0.60, 0.28),
    )
    dark_dialogue_cursor = _fraction(
        dark_dialogue_yellow,
        (0.40, 0.78, 0.20, 0.18),
    )
    if dark_ratio >= 0.92 or (luminance_mean <= 0.075 and luminance_std <= 0.08):
        if dark_dialogue_text >= 0.004 and dark_dialogue_cursor >= 0.004:
            return ScreenResult(
                "dialogue",
                _clamp01(
                    0.72
                    + min(dark_dialogue_text, 0.02) * 8
                    + min(dark_dialogue_cursor, 0.02) * 6
                ),
                {
                    "dark": dark_ratio,
                    "luminance": luminance_mean,
                    "variation": luminance_std,
                    "darkDialogueText": dark_dialogue_text,
                    "darkDialogueCursor": dark_dialogue_cursor,
                },
            )
        if loading_corner_color >= 0.018:
            return ScreenResult(
                "loading",
                _clamp01(0.72 + loading_corner_color * 2.8),
                {
                    "dark": dark_ratio,
                    "luminance": luminance_mean,
                    "variation": luminance_std,
                    "loadingCorner": loading_corner_color,
                },
            )
        return ScreenResult(
            "noSignal",
            _clamp01(max(dark_ratio, 1 - luminance_mean * 5)),
            {
                "dark": dark_ratio,
                "luminance": luminance_mean,
                "variation": luminance_std,
                "loadingCorner": loading_corner_color,
            },
        )

    if luminance_std <= 0.035:
        return ScreenResult(
            "loading",
            _clamp01(1 - luminance_std * 18),
            {"dark": dark_ratio, "luminance": luminance_mean, "variation": luminance_std},
        )

    map_scores: list[float] = []
    for region in card_regions or []:
        native_card = _crop(image, region)
        map_scores.append(_map_card_score(native_card))
    map_hits = sum(score >= 0.54 for score in map_scores)
    map_score = float(np.mean(sorted(map_scores, reverse=True)[:3])) if len(map_scores) >= 3 else 0.0

    keyboard_tiles, keyboard_rows, keyboard_score = _keyboard_grid(gray)

    # Nintendo Switch 2 HOME uses an unusually specific composition: an almost
    # blank white system bar, a colourful horizontal game-cover strip, and a
    # second mostly-white strip containing the system icons. Without this
    # detector the white background forms one huge connected cream component
    # and can look exactly like a dialogue bubble to the generic classifier.
    home_top_neutral = _fraction(bright_neutral, (0.0, 0.0, 1.0, 0.18))
    home_game_color = _fraction(colorful, (0.04, 0.20, 0.92, 0.50))
    home_icon_neutral = _fraction(bright_neutral, (0.10, 0.68, 0.80, 0.16))
    home_game_edges = cv2.Canny(_crop(gray, (0.04, 0.20, 0.92, 0.50)), 45, 130)
    home_game_edge_ratio = float(np.count_nonzero(home_game_edges)) / max(
        1,
        home_game_edges.size,
    )
    home_score = (
        _clamp01((home_top_neutral - 0.82) / 0.16) * 0.28
        + _clamp01((home_game_color - 0.18) / 0.30) * 0.30
        + _clamp01((home_icon_neutral - 0.72) / 0.25) * 0.24
        + _clamp01((home_game_edge_ratio - 0.09) / 0.18) * 0.18
    )

    # The NS2 player-account sheet dims the game-cover area to grey while a
    # nearly solid white panel fills the lower half. It must not fall through
    # to the generic dialogue detector: B closes this sheet and creates a
    # HOME -> account picker -> HOME loop.
    account_top_neutral = _fraction(system_neutral, (0.0, 0.0, 1.0, 0.18))
    account_cover_color = _fraction(colorful, (0.04, 0.18, 0.92, 0.28))
    account_panel_neutral = _fraction(bright_neutral, (0.0, 0.42, 1.0, 0.43))
    account_panel_color = _fraction(colorful, (0.0, 0.42, 1.0, 0.43))
    account_center_edges = cv2.Canny(_crop(gray, (0.32, 0.48, 0.40, 0.31)), 45, 130)
    account_center_edge_ratio = float(np.count_nonzero(account_center_edges)) / max(
        1,
        account_center_edges.size,
    )
    account_score = (
        _clamp01((account_top_neutral - 0.84) / 0.15) * 0.18
        + _clamp01((account_cover_color - 0.08) / 0.20) * 0.23
        + _clamp01((account_panel_neutral - 0.84) / 0.15) * 0.32
        + (1 - _clamp01((account_panel_color - 0.015) / 0.08)) * 0.15
        + _clamp01((account_center_edge_ratio - 0.015) / 0.07) * 0.12
    )

    tabs_green = _fraction(leaf_green, (0.48, 0.05, 0.45, 0.25))
    palette_skin = _fraction(skin, (0.48, 0.25, 0.45, 0.39))
    editor_teal = _fraction(teal, (0.50, 0.68, 0.38, 0.22))
    editor_score = (
        _clamp01((tabs_green - 0.055) / 0.25) * 0.42
        + _clamp01((palette_skin - 0.055) / 0.25) * 0.32
        + _clamp01((editor_teal - 0.025) / 0.23) * 0.26
    )

    center_cream = _fraction(cream, (0.42, 0.20, 0.48, 0.58))
    center_teal = _fraction(teal, (0.43, 0.36, 0.45, 0.42))
    choice_teal_mask = _crop(teal.astype(np.uint8) * 255, (0.43, 0.30, 0.45, 0.50))
    choice_count, _choice_labels, choice_stats, _choice_centroids = cv2.connectedComponentsWithStats(
        choice_teal_mask,
        8,
    )
    choice_buttons = 0
    for index in range(1, choice_count):
        _x, _y, component_width, component_height, area = (
            int(value) for value in choice_stats[index]
        )
        aspect = component_width / max(1, component_height)
        if area / max(1, choice_teal_mask.size) >= 0.018 and aspect >= 1.7:
            choice_buttons += 1
    choice_component = _wide_component_score(cream.astype(np.uint8) * 255, (0.38, 0.15, 0.55, 0.72))
    choice_score = (
        _clamp01((center_cream - 0.24) / 0.53) * 0.42
        + _clamp01((center_teal - 0.035) / 0.25) * 0.34
        + choice_component * 0.24
    )

    lower_cream = _fraction(cream, (0.12, 0.52, 0.76, 0.43))
    dialogue_component = _wide_component_score(cream.astype(np.uint8) * 255, (0.08, 0.45, 0.84, 0.52))
    lower_yellow = _fraction(yellow, (0.30, 0.76, 0.40, 0.22))
    dialogue_score = (
        _clamp01((lower_cream - 0.22) / 0.54) * 0.48
        + dialogue_component * 0.42
        + _clamp01((lower_yellow - 0.001) / 0.025) * 0.10
    )
    upper_right_choice_yellow = _fraction(
        pale_choice_yellow,
        (0.62, 0.05, 0.36, 0.40),
    )
    upper_right_choice_component = _horizontal_bubble_score(
        pale_choice_yellow.astype(np.uint8) * 255,
        (0.62, 0.05, 0.36, 0.40),
    )
    yellow_choice_score = (
        _clamp01((upper_right_choice_yellow - 0.055) / 0.30) * 0.44
        + upper_right_choice_component * 0.56
    )

    # The birthday form contains two tall, low-saturation selectors and far
    # fewer key tiles than the full IME. This signal is deliberately geometric
    # so it works for every supported UI language.
    form_cream = _fraction(cream, (0.17, 0.14, 0.66, 0.66))
    form_edges = cv2.Canny(_crop(gray, (0.17, 0.14, 0.66, 0.66)), 55, 145)
    form_edge_ratio = float(np.count_nonzero(form_edges)) / max(1, form_edges.size)
    birthday_teal = _fraction(teal, (0.24, 0.25, 0.58, 0.38))
    birthday_confirm_teal = _fraction(teal, (0.62, 0.32, 0.18, 0.28))
    birthday_avatar_skin = _fraction(skin, (0.08, 0.17, 0.34, 0.58))
    birthday_score = (
        _clamp01((form_cream - 0.28) / 0.48) * 0.55
        + _clamp01((form_edge_ratio - 0.025) / 0.09) * 0.25
        + (1 - keyboard_score) * 0.20
    )

    # The style page presents two large teal circular options around the middle.
    style_mask = _crop(teal.astype(np.uint8) * 255, (0.18, 0.22, 0.64, 0.56))
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(style_mask, 8)
    style_components = 0
    for index in range(1, count):
        _x, _y, component_width, component_height, area = (int(value) for value in stats[index])
        area_ratio = area / max(1, style_mask.size)
        aspect = component_width / max(1, component_height)
        if 0.012 <= area_ratio <= 0.24 and 0.55 <= aspect <= 1.75:
            style_components += 1
    style_score = _clamp01(style_components / 2) * 0.72 + _clamp01(
        (_fraction(teal, (0.18, 0.22, 0.64, 0.56)) - 0.045) / 0.30
    ) * 0.28

    signals = {
        "dark": dark_ratio,
        "luminance": luminance_mean,
        "variation": luminance_std,
        "loadingCorner": loading_corner_color,
        "map": map_score,
        "mapHits": map_hits / 4,
        "home": home_score,
        "homeTopNeutral": home_top_neutral,
        "homeGameColor": home_game_color,
        "homeIconNeutral": home_icon_neutral,
        "homeGameEdges": home_game_edge_ratio,
        "accountPicker": account_score,
        "accountTopNeutral": account_top_neutral,
        "accountCoverColor": account_cover_color,
        "accountPanelNeutral": account_panel_neutral,
        "accountPanelColor": account_panel_color,
        "accountCenterEdges": account_center_edge_ratio,
        "keyboard": keyboard_score,
        "keyboardTiles": keyboard_tiles / 60,
        "keyboardRows": keyboard_rows / 5,
        "appearance": editor_score,
        "choice": choice_score,
        "choiceButtons": choice_buttons / 3,
        "dialogue": dialogue_score,
        "yellowChoice": yellow_choice_score,
        "yellowChoiceArea": upper_right_choice_yellow,
        "yellowChoiceComponent": upper_right_choice_component,
        "birthday": birthday_score,
        "birthdayTeal": birthday_teal,
        "birthdayConfirm": birthday_confirm_teal,
        "birthdayAvatarSkin": birthday_avatar_skin,
        "formCream": form_cream,
        "formEdges": form_edge_ratio,
        "style": style_score,
    }

    # Ordered high-specificity detectors prevent the pale patterned background
    # used throughout setup from being mistaken for a dialogue bubble.
    if map_hits >= 3 and map_score >= 0.57:
        return ScreenResult("mapSelection", _clamp01(0.55 + map_score * 0.45), signals)
    if (
        account_score >= 0.72
        and account_top_neutral >= 0.90
        and account_cover_color >= 0.12
        and account_panel_neutral >= 0.90
        and account_panel_color <= 0.06
        and account_center_edge_ratio >= 0.025
    ):
        return ScreenResult(
            "accountPicker",
            _clamp01(0.48 + account_score * 0.52),
            signals,
        )
    # Resolve the high-specificity system HOME layout before any cream-panel
    # form or dialogue rule. Every individual gate is kept so a bright Animal
    # Crossing setup page cannot pass merely because its aggregate score is
    # high.
    if (
        home_score >= 0.72
        and home_top_neutral >= 0.88
        and home_game_color >= 0.20
        and home_icon_neutral >= 0.78
        and home_game_edge_ratio >= 0.10
        and luminance_mean >= 0.62
    ):
        return ScreenResult("homeMenu", _clamp01(0.48 + home_score * 0.52), signals)
    # Birthday is a structured form that also contains a wide teal confirmation
    # button. Resolve it before the generic choice-dialog detector so A/B dialog
    # acceleration can never bypass the guarded month/day entry routine.
    if (
        birthday_score >= 0.68
        and form_edge_ratio >= 0.035
        and birthday_teal >= 0.018
        and birthday_confirm_teal >= 0.20
        and birthday_avatar_skin < 0.055
    ):
        return ScreenResult("birthdayPicker", _clamp01(0.46 + birthday_score * 0.54), signals)
    if choice_score >= 0.72 and center_teal >= 0.055 and choice_buttons >= 1:
        return ScreenResult("choiceDialog", _clamp01(0.48 + choice_score * 0.52), signals)
    if keyboard_tiles >= 20 and keyboard_rows >= 3 and keyboard_score >= 0.32:
        return ScreenResult("nameKeyboard", _clamp01(0.56 + keyboard_score * 0.44), signals)
    if (
        dialogue_score >= 0.55
        # Region/hemisphere questions use a noticeably narrower pale-yellow
        # bubble than the earlier setup prompts.  Keep the lower dialogue
        # panel and minimum yellow area as context, but accept that compact
        # horizontal geometry.  Round character heads still score zero in
        # _horizontal_bubble_score because their aspect ratio is below 1.55.
        and yellow_choice_score >= 0.18
        and upper_right_choice_yellow >= 0.075
        and upper_right_choice_component >= 0.22
    ):
        return ScreenResult(
            "choiceDialog",
            _clamp01(0.50 + yellow_choice_score * 0.50),
            signals,
        )
    if editor_score >= 0.48:
        return ScreenResult("appearanceEditor", _clamp01(0.52 + editor_score * 0.48), signals)
    if style_score >= 0.58 and style_components >= 2:
        return ScreenResult("styleChoice", _clamp01(0.5 + style_score * 0.5), signals)
    if dialogue_score >= 0.55:
        return ScreenResult("dialogue", _clamp01(0.48 + dialogue_score * 0.52), signals)
    # A bright, structured screen that is neither a form nor a map is commonly
    # an intro/title screen with an A prompt. Keep this threshold conservative;
    # dim transitions and flat loading frames remain non-interactive.
    startup_score = _clamp01((luminance_std - 0.11) / 0.20) * 0.55 + _clamp01(
        (luminance_mean - 0.22) / 0.48
    ) * 0.45
    signals["startup"] = startup_score
    if startup_score >= 0.70:
        return ScreenResult("startupPrompt", _clamp01(0.42 + startup_score * 0.48), signals)
    return ScreenResult("unknown", _clamp01(0.52 - startup_score * 0.24), signals)
