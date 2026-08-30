from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Literal

import cv2
import numpy as np


CoastSide = Literal["south", "east", "west"]
ANALYZER_VERSION = "2026.08.30-r19"
AIRPORT_PLAZA_MAX_CENTER_OFFSET = 0.05
AIRPORT_PLAZA_MAX_ALIGNMENT_DELTA = 0.02
AIRPORT_PLAZA_MAX_COHERENT_CENTER_OFFSET = 0.08
AIRPORT_PLAZA_MAX_COHERENT_ALIGNMENT_DELTA = 0.01


@dataclass
class Component:
    area: int
    x: int
    y: int
    width: int
    height: int
    center_x: float
    center_y: float
    solidity: float

    @property
    def max_x(self) -> int:
        return self.x + self.width - 1

    @property
    def max_y(self) -> int:
        return self.y + self.height - 1


@dataclass
class Factor:
    key: str
    label: str
    score: float
    passed: bool
    hard: bool
    summary: str


def analysis_input_sha256(image: np.ndarray) -> str:
    """Identify the exact decoded pixels supplied to the analyzer."""
    if image is None or image.size == 0:
        raise ValueError("empty image")
    return hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _ratio_score(value: float, low: float, high: float) -> float:
    return _clamp01((value - low) / max(0.0001, high - low))


def _components(mask: np.ndarray) -> list[Component]:
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    result: list[Component] = []
    for index in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[index])
        result.append(
            Component(
                area=area,
                x=x,
                y=y,
                width=width,
                height=height,
                center_x=float(centroids[index][0]),
                center_y=float(centroids[index][1]),
                solidity=area / max(1, width * height),
            )
        )
    return sorted(result, key=lambda component: component.area, reverse=True)


def _close(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    size = radius * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _dilate(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    size = radius * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    return cv2.dilate(mask, kernel)


def _mask_bounds(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    height, width = mask.shape
    if len(xs) == 0:
        return 0, 0, width - 1, height - 1
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _largest_map_crop(image: np.ndarray) -> np.ndarray:
    """Trim obvious UI margins while keeping ocean around the island."""
    height, width = image.shape[:2]
    if width < 64 or height < 48:
        return image
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    colored = (
        (saturation > 42)
        & (value > 55)
        & (
            ((hue >= 32) & (hue <= 110))
            | ((hue >= 8) & (hue <= 31) & (value > 105))
        )
    ).astype(np.uint8) * 255
    colored = _close(colored, 4)
    candidates = [component for component in _components(colored) if component.area >= width * height * 0.08]
    if not candidates:
        return image
    component = candidates[0]
    padding_x = round(component.width * 0.07)
    padding_y = round(component.height * 0.07)
    x0 = max(0, component.x - padding_x)
    y0 = max(0, component.y - padding_y)
    x1 = min(width, component.max_x + padding_x + 1)
    y1 = min(height, component.max_y + padding_y + 1)
    if x1 - x0 < width * 0.58 or y1 - y0 < height * 0.58:
        return image
    return image[y0:y1, x0:x1]


def _suppress_selection_cursor(image: np.ndarray) -> np.ndarray:
    """Remove the white hand cursor when it overlaps a map's lower-right ocean."""
    height, width = image.shape[:2]
    if width < 120 or height < 90:
        return image
    x0 = round(width * 0.62)
    y0 = round(height * 0.58)
    roi = image[y0:, x0:]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    _hue, saturation, value = cv2.split(hsv)
    bright_neutral = ((saturation < 30) & (value > 190)).astype(np.uint8) * 255
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(bright_neutral, 8)
    roi_height, roi_width = bright_neutral.shape
    cursor_label: int | None = None
    cursor_area = 0
    for index in range(1, count):
        x, y, component_width, component_height, area = (int(item) for item in stats[index])
        touches_corner = x + component_width >= roi_width - 2 and y + component_height >= roi_height - 2
        compact = component_width <= roi_width * 0.55 and component_height <= roi_height * 0.58
        plausible_area = roi_width * roi_height * 0.025 <= area <= roi_width * roi_height * 0.16
        if touches_corner and compact and plausible_area and area > cursor_area:
            cursor_label = index
            cursor_area = area
    if cursor_label is None:
        return image

    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y0:, x0:][labels == cursor_label] = 255
    # Include the dark outline and shadow surrounding the bright hand pixels.
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)))
    return cv2.inpaint(image, mask, 7, cv2.INPAINT_TELEA)


def _segment(image: np.ndarray) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    blue, green, red = cv2.split(image)

    channel = np.maximum.reduce([red, green, blue])
    minimum = np.minimum.reduce([red, green, blue])
    color_saturation = (channel.astype(np.int16) - minimum.astype(np.int16)) / np.maximum(channel, 1)
    luminance = (red.astype(np.float32) + green + blue) / 3

    # Coastal rocks are a neutral, mid-dark grey.  The old water predicate also
    # matched that palette (especially after HDMI colour conversion), leaving
    # only thin anti-aliased remnants for the rock scorer.  Reserve the neutral
    # pixels before assigning water/land so the scorer sees the complete object.
    rock = (
        (luminance >= 55)
        & (luminance <= 160)
        & (color_saturation <= 0.30)
    )
    water = (
        (green > red.astype(np.int16) + 13)
        & (blue > red.astype(np.int16) + 9)
        & (green > 82)
        & (blue > 78)
        & (np.abs(green.astype(np.int16) - blue.astype(np.int16)) < 82)
        & ~rock
    )
    grass = (
        (green > red.astype(np.int16) + 17)
        & (green > blue.astype(np.int16) + 12)
        & (green > 58)
        & ~water
        & ~rock
    )
    sand = (
        (red > 130)
        & (green > 115)
        & (red > blue.astype(np.int16) + 24)
        & (green > blue.astype(np.int16) + 17)
        & (np.abs(red.astype(np.int16) - green.astype(np.int16)) < 78)
        & ~rock
    )

    # River and ocean use almost the same palette on some capture cards.  Separate
    # them by island topology: water enclosed by both the horizontal and vertical
    # land envelope is inland water; the rest is ocean.  This remains stable when
    # hue, saturation, or HDMI color range changes.
    height, width = water.shape
    land_seed = _close((grass | sand).astype(np.uint8) * 255) > 0
    row_envelope = np.zeros_like(water)
    column_envelope = np.zeros_like(water)
    max_horizontal_gap = round(width * 0.16)
    max_vertical_gap = round(height * 0.19)
    for y in range(height):
        xs = np.flatnonzero(land_seed[y])
        for gap_index in np.flatnonzero(np.diff(xs) > 1):
            left = int(xs[gap_index])
            right = int(xs[gap_index + 1])
            if right - left <= max_horizontal_gap:
                row_envelope[y, left : right + 1] = True
    for x in range(width):
        ys = np.flatnonzero(land_seed[:, x])
        for gap_index in np.flatnonzero(np.diff(ys) > 1):
            top = int(ys[gap_index])
            bottom = int(ys[gap_index + 1])
            if bottom - top <= max_vertical_gap:
                column_envelope[top : bottom + 1, x] = True
    # A vertical river is enclosed left/right; a horizontal river is enclosed
    # above/below.  Limiting each bridged gap avoids treating the broad ocean
    # outside the coastline as an inland channel.
    inland_envelope = row_envelope | column_envelope
    river = water & inland_envelope
    ocean = water & ~river

    structure = (
        ~water
        & ~grass
        & ~sand
        & (luminance >= 25)
        & (luminance <= 246)
    )

    return {
        "water": water.astype(np.uint8) * 255,
        "grass": grass.astype(np.uint8) * 255,
        "sand": sand.astype(np.uint8) * 255,
        "ocean": ocean.astype(np.uint8) * 255,
        "river": river.astype(np.uint8) * 255,
        "rock": rock.astype(np.uint8) * 255,
        "structure": structure.astype(np.uint8) * 255,
    }


def _peninsula_grass_mask(image: np.ndarray) -> np.ndarray:
    """Keep only saturated land greens for the side-peninsula profile.

    The general grass mask is intentionally permissive because it also feeds
    river topology and confidence scoring.  That permissive mask admits the
    pale cyan ocean on real capture-card frames, however, so its outer edge is
    not a reliable peninsula measurement.  The peninsula detector needs the
    darker island greens only.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    grass = (
        (hue >= 45)
        & (hue <= 71)
        & (saturation >= 64)
        & (value >= 50)
        & (value <= 220)
    ).astype(np.uint8) * 255
    return _close(grass)


def _score_peninsula(
    grass: np.ndarray,
    water: np.ndarray | None = None,
) -> tuple[Factor, Literal["west", "east"] | None]:
    height, width = grass.shape
    start_y = max(0, round(height * 0.05))
    end_y = min(height - 1, round(height * 0.82))
    minimum_row_pixels = max(4, round(width * 0.04))
    left_edges = np.full(height, np.nan, dtype=np.float32)
    right_edges = np.full(height, np.nan, dtype=np.float32)
    for y in range(start_y, end_y + 1):
        xs = np.flatnonzero(grass[y])
        if len(xs) >= minimum_row_pixels:
            left_edges[y] = float(xs.min())
            right_edges[y] = float(xs.max())
    valid = ~np.isnan(left_edges)
    if cv2.countNonZero(valid.astype(np.uint8)) < max(8, round(height * 0.20)):
        return (
            Factor("peninsula", "指定浮岛结构", 0, False, True, "未可靠识别指定浮岛结构"),
            None,
        )

    # Measure protrusion from the typical mainland coastline. The mild inward
    # 60/40 bias resists a real peninsula pulling its own baseline towards the
    # sea, while the thickness, continuity, and river-shoulder gates below
    # continue to reject ordinary coast variation and thin spikes.
    west_baseline = float(np.percentile(left_edges[valid], 60))
    east_baseline = float(np.percentile(right_edges[valid], 40))
    west_depth = np.where(valid, np.maximum(0, west_baseline - left_edges), 0)
    east_depth = np.where(valid, np.maximum(0, right_edges - east_baseline), 0)
    minimum_depth = width * 0.026
    minimum_run = max(3, round(height * 0.025))

    # User-confirmed silhouettes may occur on either coast and at different
    # vertical positions. Their stable feature is a sustained, block-shaped
    # extension; a thin horizontal bar is not accepted even when it reaches
    # farther into the sea.
    supported_min_depth_ratio = 0.052
    supported_min_span_ratio = 0.065
    supported_max_span_ratio = 0.160
    supported_min_profile_fill = 0.80
    supported_max_end_imbalance = 0.40
    side_mouth_clearance_ratio = 0.12
    side_mouths: dict[Literal["west", "east"], list[float]] = {
        "west": [],
        "east": [],
    }
    if water is not None:
        for mouth_side, position, _confidence in _detect_mouth_positions(water):
            if mouth_side in side_mouths:
                side_mouths[mouth_side].append(position)

    def candidate_score(
        run_length: int,
        sustained_depth: float,
        profile_fill: float,
        end_imbalance: float,
    ) -> float:
        span_ratio = run_length / height
        depth_ratio = sustained_depth / width
        extension_score = _ratio_score(depth_ratio, 0.045, 0.060)
        span_score = _ratio_score(span_ratio, 0.040, supported_min_span_ratio)
        fill_score = _ratio_score(profile_fill, 0.76, 0.92)
        balance_score = 1 - _clamp01(end_imbalance / supported_max_end_imbalance)
        shape_score = fill_score * 0.75 + balance_score * 0.25
        return extension_score * 0.60 + span_score * 0.20 + shape_score * 0.20

    def candidate_family(
        side_key: Literal["west", "east"],
        begin: int,
        finish: int,
        run_length: int,
        sustained_depth: float,
        profile_fill: float,
        end_imbalance: float,
    ) -> tuple[Literal["block"] | None, bool]:
        span_ratio = run_length / height
        depth_ratio = sustained_depth / width
        begin_ratio = begin / height
        finish_ratio = finish / height
        near_side_mouth = any(
            begin_ratio - side_mouth_clearance_ratio
            <= position
            <= finish_ratio + side_mouth_clearance_ratio
            for position in side_mouths[side_key]
        )
        block = (
            supported_min_span_ratio <= span_ratio <= supported_max_span_ratio
            and depth_ratio >= supported_min_depth_ratio
            and profile_fill >= supported_min_profile_fill
            and end_imbalance <= supported_max_end_imbalance
            and not near_side_mouth
        )
        return ("block" if block else None), near_side_mouth

    def strongest_run(
        values: np.ndarray,
        side_key: Literal["west", "east"],
    ) -> tuple[
        int,
        float,
        float,
        float,
        float,
        float,
        Literal["block"] | None,
        bool,
    ]:
        candidates: list[
            tuple[
                Literal["block"] | None,
                float,
                float,
                int,
                float,
                float,
                float,
                float,
                bool,
            ]
        ] = []
        begin: int | None = None
        for y in range(start_y, end_y + 1):
            enabled = bool(valid[y] and values[y] >= minimum_depth)
            if enabled and begin is None:
                begin = y
            if begin is not None and (not enabled or y == end_y):
                finish = y if enabled and y == end_y else y - 1
                run = values[begin : finish + 1]
                if len(run) >= minimum_run:
                    sustained_depth = float(np.percentile(run, 25))
                    area = float(run.sum())
                    peak_depth = float(run.max())
                    profile_fill = area / max(1.0, peak_depth * len(run))
                    end_imbalance = abs(float(run[0]) - float(run[-1])) / max(
                        1.0,
                        peak_depth,
                    )
                    score = candidate_score(
                        len(run),
                        sustained_depth,
                        profile_fill,
                        end_imbalance,
                    )
                    family, near_side_mouth = candidate_family(
                        side_key,
                        begin,
                        finish,
                        len(run),
                        sustained_depth,
                        profile_fill,
                        end_imbalance,
                    )
                    candidates.append(
                        (
                            family,
                            score,
                            area,
                            len(run),
                            sustained_depth,
                            profile_fill,
                            end_imbalance,
                            ((begin + finish) / 2) / height,
                            near_side_mouth,
                        )
                    )
                begin = None
        if not candidates:
            return 0, 0.0, 0.0, 1.0, 0.0, 0.0, None, False
        (
            family,
            score,
            _area,
            run_length,
            sustained_depth,
            profile_fill,
            end_imbalance,
            center_ratio,
            near_side_mouth,
        ) = max(
            candidates,
            key=lambda candidate: (
                candidate[0] is not None,
                candidate[1],
                candidate[2],
            ),
        )
        return (
            run_length,
            sustained_depth,
            profile_fill,
            end_imbalance,
            center_ratio,
            score,
            family,
            near_side_mouth,
        )

    (
        west_run,
        west_depth_sustained,
        west_profile_fill,
        west_end_imbalance,
        west_center_ratio,
        west_score,
        west_family,
        west_near_side_mouth,
    ) = strongest_run(west_depth, "west")
    (
        east_run,
        east_depth_sustained,
        east_profile_fill,
        east_end_imbalance,
        east_center_ratio,
        east_score,
        east_family,
        east_near_side_mouth,
    ) = strongest_run(east_depth, "east")
    side_key: Literal["west", "east"] = (
        "west"
        if (west_family is not None, west_score) >= (east_family is not None, east_score)
        else "east"
    )
    run = west_run if side_key == "west" else east_run
    sustained_depth = west_depth_sustained if side_key == "west" else east_depth_sustained
    profile_fill = west_profile_fill if side_key == "west" else east_profile_fill
    end_imbalance = west_end_imbalance if side_key == "west" else east_end_imbalance
    center_ratio = west_center_ratio if side_key == "west" else east_center_ratio
    near_side_mouth = (
        west_near_side_mouth if side_key == "west" else east_near_side_mouth
    )
    if run == 0:
        return (
            Factor("peninsula", "指定浮岛结构", 0, False, True, "未可靠识别指定浮岛结构"),
            None,
        )

    span_ratio = run / height
    depth_ratio = sustained_depth / width
    score = west_score if side_key == "west" else east_score
    family = west_family if side_key == "west" else east_family
    side = "左岸" if side_key == "west" else "右岸"
    # Passing here means matching the user-confirmed block silhouette, not
    # simply finding any thin side-coast protrusion.
    passed = family is not None
    depth_percent = depth_ratio * 100
    span_percent = span_ratio * 100
    center_percent = center_ratio * 100
    if passed:
        summary = (
            f"{side}块状浮岛合格（外伸 {depth_percent:.1f}%"
            f" · 结构高度 {span_percent:.1f}% · 位置 {center_percent:.1f}%"
            f" · 轮廓完整 {profile_fill * 100:.0f}%）"
        )
    else:
        unmet: list[str] = []
        if depth_ratio < supported_min_depth_ratio:
            unmet.append("外伸需 ≥5.2%")
        if span_ratio < supported_min_span_ratio:
            unmet.append("外伸结构过薄（需 ≥6.5%）")
        if span_ratio > supported_max_span_ratio:
            unmet.append("外伸结构过高")
        if profile_fill < supported_min_profile_fill:
            unmet.append("外伸轮廓不完整")
        if end_imbalance > supported_max_end_imbalance:
            unmet.append("外伸轮廓不对称")
        if near_side_mouth:
            unmet.append("紧邻横向河口，属于河口岸肩")
        requirement = f" · 未通过：{'、'.join(unmet)}" if unmet else ""
        summary = (
            f"未匹配指定浮岛（外伸 {depth_percent:.1f}%"
            f" · 结构高度 {span_percent:.1f}% · 位置 {center_percent:.1f}%"
            f" · 轮廓完整 {profile_fill * 100:.0f}%{requirement}）"
        )
    return Factor("peninsula", "指定浮岛结构", score, passed, True, summary), side_key


def _score_fox_beach(
    sand: np.ndarray, peninsula_side: Literal["west", "east"] | None
) -> Factor:
    """Require the small north beach to sit near an outer side of the island."""
    height, width = sand.shape
    pixel_count = width * height
    candidates = [
        component
        for component in _components(sand)
        if 0.00065 <= component.area / pixel_count <= 0.018
        and component.y <= height * 0.10
        and component.height <= height * 0.10
        and component.width <= width * 0.14
    ]
    if not candidates:
        return Factor("foxBeach", "狐狸海滩位置", 0, False, True, "未可靠识别北侧狐狸海滩")

    beach = max(candidates, key=lambda component: component.area * component.solidity)
    center_x = beach.center_x / width
    edge_distance = min(center_x, 1 - center_x)
    beach_side: Literal["west", "east"] = "west" if center_x < 0.5 else "east"
    side_name = "左侧" if beach_side == "west" else "右侧"
    same_side = peninsula_side is not None and beach_side == peninsula_side

    # Audited accepted maps reach roughly 31% from the closest outer edge.
    # Give that whole band full edge credit, then fade across the next ~8%.
    edge_score = 1 - _ratio_score(edge_distance, 0.31, 0.39)
    score = _clamp01(edge_score * 0.82 + (0.18 if same_side else 0))
    passed = edge_distance <= 0.38
    if not passed:
        summary = f"狐狸海滩位于上方中段（距最近侧边 {edge_distance * 100:.1f}%）"
    elif same_side:
        summary = f"狐狸海滩靠{side_name}（距侧边 {edge_distance * 100:.1f}%）· 与浮岛同侧，满分"
    else:
        summary = f"狐狸海滩靠{side_name}（距侧边 {edge_distance * 100:.1f}%）"
    return Factor("foxBeach", "狐狸海滩位置", score, passed, True, summary)


def _score_beach_shape(sand: np.ndarray, structures: np.ndarray) -> Factor:
    """Measure large scallops in the outer south-beach silhouette."""
    height, width = sand.shape
    # Only structures touching the beach can bridge the airport/pier cut-outs.
    # The permissive structure mask intentionally includes unmatched UI pixels;
    # using all of it lets the pale card/background become a perfectly flat
    # artificial shoreline after tiny HDMI brightness changes.
    coast_adjacent_structures = cv2.bitwise_and(structures, _dilate(sand, 3))
    coast_surface = cv2.bitwise_or(sand, coast_adjacent_structures)
    minimum_sand_pixels = max(3, round(height * 0.065))
    shoreline = np.full(width, np.nan, dtype=np.float32)
    for x in range(width):
        sand_ys = np.flatnonzero(sand[:, x])
        surface_ys = np.flatnonzero(coast_surface[:, x])
        if len(sand_ys) >= minimum_sand_pixels and len(surface_ys):
            shoreline[x] = float(surface_ys.max())
    valid = np.flatnonzero(~np.isnan(shoreline))
    if len(valid) < width * 0.42:
        return Factor("beachShape", "沙滩圆润度", 0, False, True, "沙岸轮廓识别不足")

    start = int(np.percentile(valid, 5))
    end = int(np.percentile(valid, 95))
    indexes = np.arange(start, end + 1)
    values = np.interp(indexes, valid, shoreline[valid]).astype(np.float32)
    small_kernel = max(5, (round(width * 0.035) // 2) * 2 + 1)
    broad_kernel = max(17, (round(width * 0.19) // 2) * 2 + 1)
    smooth = cv2.GaussianBlur(values.reshape(1, -1), (small_kernel, 1), 0).ravel()
    baseline = cv2.GaussianBlur(smooth.reshape(1, -1), (broad_kernel, 1), 0).ravel()
    residual = smooth - baseline
    amplitude = float(np.percentile(residual, 95) - np.percentile(residual, 5)) / height
    curvature = float(np.mean(np.abs(np.diff(smooth, n=2)))) / height if len(smooth) >= 3 else 1

    sampled = residual[:: max(2, round(width * 0.018))]
    derivative = np.diff(sampled)
    derivative[np.abs(derivative) < height * 0.003] = 0
    nonzero_signs = np.sign(derivative[derivative != 0])
    turns = int(np.count_nonzero(np.diff(nonzero_signs))) if len(nonzero_signs) > 1 else 0
    amplitude_score = 1 - _ratio_score(amplitude, 0.018, 0.075)
    curvature_score = 1 - _ratio_score(curvature, 0.0012, 0.009)
    turn_score = 1 - _ratio_score(turns, 3, 9)
    score = amplitude_score * 0.52 + curvature_score * 0.30 + turn_score * 0.18
    passed = score >= 0.68
    summary = f"岸线起伏 {round(amplitude * 100)}% · {turns} 次明显转向"
    return Factor("beachShape", "沙滩圆润度", score, passed, True, summary)


def _merged_component(group: list[Component]) -> Component:
    area = sum(component.area for component in group)
    x = min(component.x for component in group)
    y = min(component.y for component in group)
    max_x = max(component.max_x for component in group)
    max_y = max(component.max_y for component in group)
    width = max_x - x + 1
    height = max_y - y + 1
    return Component(
        area=area,
        x=x,
        y=y,
        width=width,
        height=height,
        center_x=sum(component.center_x * component.area for component in group) / area,
        center_y=sum(component.center_y * component.area for component in group) / area,
        solidity=area / max(1, width * height),
    )


def _component_axis_gaps(first: Component, second: Component) -> tuple[int, int]:
    """Return the empty horizontal/vertical pixels between two bounding boxes."""
    horizontal = max(first.x - second.max_x - 1, second.x - first.max_x - 1, 0)
    vertical = max(first.y - second.max_y - 1, second.y - first.max_y - 1, 0)
    return horizontal, vertical


def _split_large_formation(
    primary: Component,
    components: list[Component],
    side: str,
    coast_x: int,
    width: int,
    height: int,
) -> tuple[list[Component], list[Component]]:
    """Separate close satellite pieces of one reef from detached fragments.

    Capture-card colour conversion can break a complete coastal formation into
    several neutral-grey connected components.  Those pieces stay aligned on
    the same coast and form a short gap-connected chain.  A genuinely detached
    small reef has a wider break from the accepted large formation.
    """
    formation = [primary]
    remaining = [component for component in components if component is not primary]
    maximum_horizontal_gap = max(2, round(width * 0.02))
    maximum_vertical_gap = max(3, round(height * 0.12))
    coast_tolerance = max(1, round(width * 0.005))

    def is_landward_satellite(component: Component) -> bool:
        if side == "west":
            return component.x >= coast_x - coast_tolerance
        return component.max_x <= coast_x + coast_tolerance

    while True:
        joined = [
            component
            for component in remaining
            if is_landward_satellite(component)
            and any(
                horizontal_gap <= maximum_horizontal_gap
                and vertical_gap <= maximum_vertical_gap
                for member in formation
                for horizontal_gap, vertical_gap in [_component_axis_gaps(member, component)]
            )
        ]
        if not joined:
            break
        formation.extend(joined)
        remaining = [component for component in remaining if component not in joined]

    return formation, remaining


def _score_rocks(
    rock: np.ndarray,
    sand_bounds: tuple[int, int, int, int],
    water: np.ndarray,
) -> Factor:
    """Count only optional side formations, excluding fixed map decorations."""
    height, width = rock.shape
    pixel_count = width * height
    min_x, min_y, max_x, max_y = sand_bounds
    side_distance = width * 0.075
    mouth_positions = _detect_mouth_positions(water)
    side_mouths = {
        side: position
        for side, position, _confidence in mouth_positions
        if side in {"west", "east"}
    }
    south_mouths = [
        position
        for side, position, _confidence in mouth_positions
        if side == "south"
    ]
    ignored_north = 0
    ignored_mouth = 0
    ignored_pier = 0
    side_components: dict[str, list[Component]] = {"west": [], "east": []}

    def is_tall_large(component: Component) -> bool:
        return (
            component.area / pixel_count >= 0.0030
            and component.height / height >= 0.10
            and component.width / width >= 0.035
            and component.solidity >= 0.45
        )

    def is_compact_large(component: Component) -> bool:
        aspect_ratio = component.width / max(1, component.height)
        return (
            component.area / pixel_count >= 0.00245
            and component.height / height >= 0.06
            and component.width / width >= 0.045
            and 0.75 <= aspect_ratio <= 1.45
            and 0.50 <= component.solidity <= 0.78
        )

    def is_complementary_large(component: Component) -> bool:
        """Accept the coherent remainder when the opposite reef owns the budget.

        The game distributes a limited amount of optional side-rock material
        between both coasts.  When one side receives a very large formation,
        the other valid formation can be a smaller, vertical oval.  This branch
        deliberately describes that sprite instead of lowering the ordinary
        large-component thresholds, which would promote detached fragments.
        """
        aspect_ratio = component.width / max(1, component.height)
        return (
            component.area / pixel_count >= 0.0012
            and component.height / height >= 0.06
            and component.width / width >= 0.025
            and 0.42 <= aspect_ratio <= 0.80
            and component.solidity >= 0.55
        )

    def is_large(component: Component) -> bool:
        return is_tall_large(component) or is_compact_large(component)

    def is_fragment(component: Component) -> bool:
        return component.area / pixel_count >= 0.00035 and (
            component.height / height >= 0.025 or component.width / width >= 0.015
        )

    for component in _components(_close(rock, 2)):
        if abs(component.center_x - min_x) <= side_distance:
            side = "west"
        elif abs(component.center_x - max_x) <= side_distance:
            side = "east"
        else:
            continue
        if component.area < 2 or (component.width < 2 and component.height < 2):
            continue
        large_component = is_large(component)
        # The north-west and north-east rocks are present on every generated map.
        # Keep the zone tight: a genuine side reef can sit in the upper quarter.
        if component.center_y < min_y + height * 0.11 and not is_tall_large(component):
            ignored_north += 1
            continue
        if (
            component.center_y >= max_y - height * 0.14
            and component.width / width >= 0.018
            and component.height / height <= 0.035
        ):
            ignored_pier += 1
            continue
        if component.center_y > max_y - height * 0.04:
            continue
        # Every river mouth has two small fixed shore rocks.  They are decoration,
        # not optional fragmented coastal rocks.
        mouth_position = side_mouths.get(side)
        if (
            not large_component
            and mouth_position is not None
            and abs(component.center_y / height - mouth_position) <= 0.10
        ):
            ignored_mouth += 1
            continue
        if not large_component and south_mouths and component.center_y >= max_y - height * 0.12:
            if any(abs(component.center_x / width - position) <= 0.08 for position in south_mouths):
                ignored_mouth += 1
                continue
        side_components[side].append(component)

    primary_by_side: dict[str, Component | None] = {}
    for side, components in side_components.items():
        large_candidates = [component for component in components if is_large(component)]
        primary_by_side[side] = (
            max(large_candidates, key=lambda component: component.area)
            if large_candidates
            else None
        )

    complementary_distribution: str | None = None
    normal_large_sides = [side for side, primary in primary_by_side.items() if primary is not None]
    if len(normal_large_sides) == 1:
        dominant_side = normal_large_sides[0]
        remainder_side = "east" if dominant_side == "west" else "west"
        dominant = primary_by_side[dominant_side]
        remainder_candidates = [
            component
            for component in side_components[remainder_side]
            if is_complementary_large(component)
        ]
        if dominant is not None and remainder_candidates:
            remainder = max(remainder_candidates, key=lambda component: component.area)
            combined_area_ratio = (dominant.area + remainder.area) / pixel_count
            if combined_area_ratio >= 0.0060:
                primary_by_side[remainder_side] = remainder
                complementary_distribution = "左大右小" if dominant_side == "west" else "右大左小"

    large: list[Component] = []
    fragments: list[Component] = []
    large_sides: set[str] = set()
    for side, components in side_components.items():
        if not components:
            continue
        primary = primary_by_side[side]
        if primary is not None:
            large.append(primary)
            large_sides.add(side)
            coast_x = min_x if side == "west" else max_x
            _formation, components = _split_large_formation(
                primary,
                components,
                side,
                coast_x,
                width,
                height,
            )
        fragments.extend(
            component
            for component in components
            if component is not primary and is_fragment(component)
        )

    solidity = float(np.mean([component.solidity for component in large])) if large else 0
    count_score = 1 if len(large) == 2 and len(large_sides) == 2 else 0.38 if len(large) == 1 else 0.08
    fragment_score = 1 if not fragments else 0.35 if len(fragments) == 1 else 0
    score = count_score * 0.72 + fragment_score * 0.20 + _ratio_score(solidity, 0.18, 0.48) * 0.08
    passed = len(large) == 2 and len(large_sides) == 2 and not fragments and solidity >= 0.45
    large_text = (
        (
            f"2 块完整大礁石（{complementary_distribution}，总量合格）"
            if complementary_distribution
            else "2 块完整大礁石（左右各 1）"
        )
        if len(large) == 2 and len(large_sides) == 2
        else f"{len(large)} 块完整大礁石"
    )
    west_fragments = sum(component.center_x < width / 2 for component in fragments)
    east_fragments = len(fragments) - west_fragments
    fragment_text = (
        "无碎礁"
        if not fragments
        else f"{len(fragments)} 处碎礁（左 {west_fragments} · 右 {east_fragments}）"
    )
    ignored: list[str] = []
    if ignored_north:
        ignored.append(f"北岸固定礁 {ignored_north}")
    if ignored_mouth:
        ignored.append(f"河口护岸礁 {ignored_mouth}")
    if ignored_pier:
        ignored.append(f"码头形状 {ignored_pier}")
    ignored_text = f" · 已忽略{'、'.join(ignored)}" if ignored else ""
    return Factor(
        "coastalRocks",
        "完整大礁石",
        score,
        passed,
        True,
        f"{large_text} · {fragment_text}{ignored_text}",
    )


def _structure_candidates(structure: np.ndarray) -> list[Component]:
    height, width = structure.shape
    pixel_count = width * height
    return [
        component
        for component in _components(_dilate(structure))
        if 0.0008 <= component.area / pixel_count <= 0.08
    ]


def _choose_structure(
    candidates: list[Component], width: int, height: int, kind: Literal["plaza", "airport"]
) -> tuple[Component | None, float]:
    winner: Component | None = None
    winner_score = 0.0
    for component in candidates:
        x = component.center_x / width
        y = component.center_y / height
        area_ratio = component.area / (width * height)
        square = min(component.width, component.height) / max(component.width, component.height)
        centered = _clamp01(1 - abs(x - 0.5) / 0.38)
        score = 0.0
        if kind == "plaza" and 0.18 <= x <= 0.82 and 0.28 <= y <= 0.76:
            vertical = _clamp01(1 - abs(y - 0.57) / 0.31)
            area = min(_ratio_score(area_ratio, 0.001, 0.009), _clamp01((0.065 - area_ratio) / 0.03))
            score = centered * 0.28 + vertical * 0.20 + area * 0.30 + square * 0.22
        # The airport icon is a compact building above the south beach.  Thin
        # anti-aliased coastline bands touch the bottom edge and used to win
        # solely because the airport score rewarded southern components.
        if (
            kind == "airport"
            and 0.12 <= x <= 0.88
            and 0.72 <= y <= 0.94
            and square >= 0.28
        ):
            south = _ratio_score(y, 0.72, 0.90)
            area = min(_ratio_score(area_ratio, 0.0008, 0.007), _clamp01((0.075 - area_ratio) / 0.035))
            score = centered * 0.30 + south * 0.28 + area * 0.28 + square * 0.14
        if score > winner_score:
            winner = component
            winner_score = score
    return winner, _clamp01(winner_score)


def _score_airport_plaza(structure: np.ndarray) -> tuple[Factor, float]:
    height, width = structure.shape
    candidates = _structure_candidates(structure)
    plaza, plaza_confidence = _choose_structure(candidates, width, height, "plaza")
    airport, airport_confidence = _choose_structure(candidates, width, height, "airport")
    if plaza is None or airport is None or plaza is airport:
        return Factor("airportPlaza", "机场与广场", 0, False, True, "机场或广场定位置信度不足"), 0
    airport_x, airport_y = airport.center_x / width, airport.center_y / height
    plaza_x, plaza_y = plaza.center_x / width, plaza.center_y / height
    # The map icon's airport exit is slightly left of the airport body's center.
    # Compare the exit—not the body centroid—to the plaza center.
    airport_exit_x = airport_x - 0.015
    alignment_delta = abs(airport_exit_x - plaza_x)
    distance = float(np.hypot(airport_exit_x - plaza_x, airport_y - plaza_y))
    airport_center_offset = abs(airport_exit_x - 0.5)
    plaza_center_offset = abs(plaza_x - 0.5)
    centered_score = (
        _clamp01(1 - airport_center_offset / 0.10)
        + _clamp01(1 - plaza_center_offset / 0.10)
    ) / 2
    alignment_score = _clamp01(1 - alignment_delta / 0.04)
    if distance < 0.16:
        distance_score = _ratio_score(distance, 0.10, 0.16)
    elif distance > 0.30:
        distance_score = _clamp01(1 - (distance - 0.30) / 0.10)
    else:
        distance_score = 1
    score = centered_score * 0.32 + alignment_score * 0.43 + distance_score * 0.25
    airport_centered = airport_center_offset <= AIRPORT_PLAZA_MAX_CENTER_OFFSET
    plaza_centered = plaza_center_offset <= AIRPORT_PLAZA_MAX_CENTER_OFFSET
    aligned = alignment_delta <= AIRPORT_PLAZA_MAX_ALIGNMENT_DELTA
    # A coherent pair can be slightly off the geometric map center without
    # being a bad layout. Preserve the strict individual 5% gate normally,
    # but admit a bounded shared-axis case only when both structures remain
    # within 8% and their mutual horizontal error is at most 1%. This accepts
    # the supplied 6.6% / 7.1% / 0.5% layout while keeping visibly mismatched
    # pairs such as 6.7% / 9.5% / 2.9% rejected.
    coherently_offset = (
        airport_center_offset <= AIRPORT_PLAZA_MAX_COHERENT_CENTER_OFFSET
        and plaza_center_offset <= AIRPORT_PLAZA_MAX_COHERENT_CENTER_OFFSET
        and alignment_delta <= AIRPORT_PLAZA_MAX_COHERENT_ALIGNMENT_DELTA
    )
    center_gate = (airport_centered and plaza_centered) or coherently_offset
    distance_ok = 0.14 <= distance <= 0.34
    vertically_ordered = airport_y > plaza_y
    passed = center_gate and aligned and distance_ok and vertically_ordered
    distance_label = "过近" if distance < 0.14 else "过远" if distance > 0.34 else "适中"
    violations: list[str] = []
    if not airport_centered and not coherently_offset:
        violations.append(f"机场偏离中线（上限 {AIRPORT_PLAZA_MAX_CENTER_OFFSET * 100:.1f}%）")
    if not plaza_centered and not coherently_offset:
        violations.append(f"广场偏离中线（上限 {AIRPORT_PLAZA_MAX_CENTER_OFFSET * 100:.1f}%）")
    if not aligned:
        violations.append(f"出口与广场错位（上限 {AIRPORT_PLAZA_MAX_ALIGNMENT_DELTA * 100:.1f}%）")
    if not distance_ok:
        violations.append(f"间距{distance_label}")
    if not vertically_ordered:
        violations.append("机场未位于广场南侧")
    violation_label = f" · 未通过：{'、'.join(violations)}" if violations else ""
    coherent_label = " · 共同偏移但轴线一致" if coherently_offset and not (airport_centered and plaza_centered) else ""
    summary = (
        f"机场出口距中线 {airport_center_offset * 100:.1f}% · "
        f"广场距中线 {plaza_center_offset * 100:.1f}% · "
        f"出口横向错位 {alignment_delta * 100:.1f}% · "
        f"间距 {distance * 100:.1f}%（{distance_label}）{coherent_label}{violation_label}"
    )
    return Factor("airportPlaza", "机场与广场", score, passed, True, summary), min(
        plaza_confidence, airport_confidence
    )


def _profile_runs(
    profile: np.ndarray,
    start: int,
    end: int,
    threshold: float,
    minimum_length: int,
) -> list[tuple[int, int, float]]:
    runs: list[tuple[int, int, float]] = []
    begin: int | None = None
    for index in range(start, end + 1):
        active = float(profile[index]) >= threshold
        if active and begin is None:
            begin = index
        if begin is not None and (not active or index == end):
            finish = index if active and index == end else index - 1
            if finish - begin + 1 >= minimum_length:
                values = profile[begin : finish + 1]
                confidence = float(values.mean()) * 0.75 + float(values.max()) * 0.25
                runs.append((begin, finish, confidence))
            begin = None
    return runs


def _detect_mouth_positions(
    water: np.ndarray,
) -> list[tuple[CoastSide, float, float]]:
    """Return the two strongest beach crossings with normalized coast positions."""
    height, width = water.shape
    binary = water > 0
    profiles: list[tuple[CoastSide, np.ndarray, int, int, int]] = [
        (
            "west",
            binary[:, round(width * 0.177) : round(width * 0.292)].mean(axis=1),
            round(height * 0.17),
            round(height * 0.83),
            max(4, round(height * 0.035)),
        ),
        (
            "east",
            binary[:, round(width * 0.708) : round(width * 0.833)].mean(axis=1),
            round(height * 0.17),
            round(height * 0.83),
            max(4, round(height * 0.035)),
        ),
        (
            "south",
            binary[round(height * 0.57) : round(height * 0.972), :].mean(axis=0),
            round(width * 0.25),
            round(width * 0.75),
            max(4, round(width * 0.025)),
        ),
    ]
    candidates: list[tuple[CoastSide, float, float]] = []
    for side, profile, start, end, minimum_length in profiles:
        candidates.extend(
            (
                side,
                (begin + finish) / 2 / (width if side == "south" else height),
                confidence,
            )
            for begin, finish, confidence in _profile_runs(
                profile,
                start,
                end,
                0.55,
                minimum_length,
            )
        )
    # ACNH generates exactly two river mouths.  Ranking coherent beach-crossing
    # corridors enforces that invariant and prevents inland waterfalls, ponds,
    # and anti-aliased river edges from being counted as extra mouths.
    selected = sorted(candidates, key=lambda item: item[2], reverse=True)[:2]
    order = {"south": 0, "east": 1, "west": 1}
    return sorted(selected, key=lambda item: order[item[0]])


def _detect_mouths(water: np.ndarray) -> list[CoastSide]:
    """Find only water corridors that cross the outer west/east/south beach."""
    return [side for side, _position, _confidence in _detect_mouth_positions(water)]


def _analyze_river(
    river: np.ndarray, water: np.ndarray
) -> tuple[Factor, float]:
    height, width = river.shape
    pixel_count = width * height
    closed = _close(river, 3)
    meaningful = np.zeros_like(closed)
    component_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(closed, 8)
    eligible_components: list[tuple[int, int]] = []
    for index in range(1, component_count):
        component_width = int(stats[index, cv2.CC_STAT_WIDTH])
        component_height = int(stats[index, cv2.CC_STAT_HEIGHT])
        component_area = int(stats[index, cv2.CC_STAT_AREA])
        long_enough = component_width / width >= 0.12 or component_height / height >= 0.12
        if component_area / pixel_count >= 0.004 and long_enough:
            eligible_components.append((index, component_area))
    if eligible_components:
        main_index = max(eligible_components, key=lambda item: item[1])[0]
        meaningful[labels == main_index] = 255

    mouths = _detect_mouths(water)
    south_count = mouths.count("south")
    mouth_pass = len(mouths) == 2 and south_count < 2
    if len(mouths) == 2:
        mouth_score = 1 if south_count < 2 else 0.08
    elif len(mouths) == 1:
        mouth_score = 0.38
    elif len(mouths) == 3 and south_count < 2:
        mouth_score = 0.52
    else:
        mouth_score = 0.05
    labels = {"south": "南", "east": "东", "west": "西"}
    mouth_names = [labels[side] for side in mouths]
    mouth_summary = (
        "未可靠识别入海口"
        if not mouths
        else f"{' + '.join(mouth_names)}入海（{'双南' if south_count == 2 else '非双南'}）"
    )
    mouth_factor = Factor("riverMouths", "入海口方向", mouth_score, mouth_pass, True, mouth_summary)

    river_confidence = _ratio_score(cv2.countNonZero(meaningful) / pixel_count, 0.008, 0.035)
    return mouth_factor, river_confidence


def _debug_overlay(
    image: np.ndarray,
    masks: dict[str, np.ndarray],
    factors: list[Factor],
) -> np.ndarray:
    overlay = image.copy()
    colors = {
        "river": (255, 80, 40),
        "rock": (210, 40, 220),
        "grass": (40, 210, 50),
        "sand": (20, 220, 240),
    }
    for name, color in colors.items():
        mask = masks[name] > 0
        overlay[mask] = (overlay[mask] * 0.55 + np.asarray(color) * 0.45).astype(np.uint8)
    for index, factor in enumerate(factors):
        color = (45, 180, 45) if factor.passed else (45, 45, 220)
        cv2.putText(
            overlay,
            f"{factor.label}: {round(factor.score * 100)}",
            (5, 16 + index * 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.34,
            color,
            1,
            cv2.LINE_AA,
        )
    return overlay


def analyze_map(image: np.ndarray, include_debug: bool = False) -> dict[str, Any]:
    if image is None or image.size == 0:
        raise ValueError("empty image")
    cropped = _largest_map_crop(_suppress_selection_cursor(image))
    normalized = cv2.resize(cropped, (192, 144), interpolation=cv2.INTER_AREA)
    masks = _segment(normalized)
    rock_normalized = cv2.resize(cropped, (384, 288), interpolation=cv2.INTER_AREA)
    rock_masks = _segment(rock_normalized)
    land = cv2.bitwise_or(masks["grass"], masks["sand"])
    bounds = _mask_bounds(land)
    sand_bounds = _mask_bounds(masks["sand"])

    rock_sand_bounds = _mask_bounds(rock_masks["sand"])
    rock_factor = _score_rocks(rock_masks["rock"], rock_sand_bounds, rock_masks["water"])
    airport_factor, structure_confidence = _score_airport_plaza(masks["structure"])
    peninsula_factor, peninsula_side = _score_peninsula(
        _peninsula_grass_mask(normalized),
        masks["water"],
    )
    fox_beach_factor = _score_fox_beach(masks["sand"], peninsula_side)
    beach_factor = _score_beach_shape(masks["sand"], masks["structure"])
    mouth_factor, river_confidence = _analyze_river(masks["river"], masks["water"])
    factors = [
        rock_factor,
        airport_factor,
        peninsula_factor,
        fox_beach_factor,
        beach_factor,
        mouth_factor,
    ]
    weights = [0.23, 0.23, 0.16, 0.13, 0.13, 0.12]
    raw_score = sum(factor.score * weight for factor, weight in zip(factors, weights))
    hard_pass = all(factor.passed for factor in factors if factor.hard)

    pixel_count = normalized.shape[0] * normalized.shape[1]
    map_color_confidence = (
        _ratio_score(cv2.countNonZero(masks["grass"]) / pixel_count, 0.16, 0.42)
        + _ratio_score(cv2.countNonZero(masks["sand"]) / pixel_count, 0.015, 0.08)
        + _ratio_score(cv2.countNonZero(masks["water"]) / pixel_count, 0.09, 0.28)
    ) / 3
    confidence = _clamp01(map_color_confidence * 0.55 + structure_confidence * 0.25 + river_confidence * 0.20)
    if confidence < 0.42:
        score = raw_score * confidence
    elif hard_pass:
        score = raw_score
    else:
        score = min(raw_score, 0.69)

    result: dict[str, Any] = {
        "analysisRevision": ANALYZER_VERSION,
        "score": _clamp01(score),
        "hardPass": hard_pass and confidence >= 0.42,
        "analysisConfidence": confidence,
        "factors": [asdict(factor) for factor in factors],
    }
    if include_debug:
        masks["rock"] = cv2.resize(
            rock_masks["rock"],
            (normalized.shape[1], normalized.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        )
        result["debugImage"] = _debug_overlay(normalized, masks, factors)
        result["masks"] = masks
    return result
