from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np
import pytest

from analyzer import (
    Component,
    _choose_structure,
    _detect_mouth_positions,
    _detect_mouths,
    _score_beach_shape,
    _score_peninsula,
    _suppress_selection_cursor,
    analyze_map,
)


def candidate_map(
    *,
    double_south: bool = False,
    fragmented_rock: bool = False,
    single_large_rock: bool = False,
    fixed_rock_decorations: bool = False,
    airport_x: int = 261,
    airport_y: int = 314,
    plaza_x: int = 250,
    plaza_y: int = 160,
    fox_x: int = 105,
    peninsula_height: int = 24,
    peninsula_x: int = 10,
) -> np.ndarray:
    image = np.full((344, 480, 3), (196, 208, 148), dtype=np.uint8)
    sand = (160, 220, 236)
    grass = (72, 146, 78)
    river = (205, 215, 151)
    rock = (108, 105, 112)

    cv2.rectangle(image, (25, 12), (455, 330), sand, -1)
    cv2.rectangle(image, (45, 30), (435, 292), grass, -1)
    cv2.rectangle(
        image,
        (peninsula_x, 50),
        (70, 50 + peninsula_height - 1),
        grass,
        -1,
    )  # west peninsula

    # One compact river tree.  It has a south mouth plus either an east mouth
    # (acceptable) or a second south mouth (hard rejection).
    cv2.line(image, (176, 58), (176, 334), river, 13)
    if double_south:
        cv2.line(image, (176, 165), (346, 245), river, 13)
        cv2.line(image, (346, 245), (346, 344), river, 13)
    else:
        cv2.line(image, (176, 165), (470, 165), river, 13)

    cv2.rectangle(image, (12, 145), (37, 205), rock, -1)
    if not single_large_rock:
        cv2.rectangle(image, (443, 210), (469, 275), rock, -1)
    cv2.rectangle(image, (55, 2), (115, 18), rock, -1)  # decorative north rocks
    if fragmented_rock:
        cv2.circle(image, (18, 242), 5, rock, -1)
        cv2.circle(image, (18, 260), 4, rock, -1)
    if fixed_rock_decorations:
        # Generated on every map and therefore irrelevant to optional rocks.
        cv2.rectangle(image, (12, 20), (30, 38), rock, -1)
        cv2.rectangle(image, (450, 20), (469, 38), rock, -1)
        cv2.rectangle(image, (443, 140), (451, 152), rock, -1)
        cv2.rectangle(image, (443, 178), (451, 190), rock, -1)
        cv2.rectangle(image, (8, 300), (60, 306), (82, 142, 204), -1)  # yellow pier

    # The only two semantic icons used by the scorer.
    # North coast is rocky except for the small fox beach near the west edge.
    cv2.rectangle(image, (45, 12), (435, 29), rock, -1)
    cv2.rectangle(image, (fox_x - 16, 8), (fox_x + 16, 26), sand, -1)

    cv2.rectangle(
        image,
        (plaza_x - 26, plaza_y - 22),
        (plaza_x + 26, plaza_y + 22),
        (65, 210, 229),
        -1,
    )
    cv2.circle(image, (plaza_x, plaza_y), 14, (60, 135, 60), -1)
    cv2.ellipse(image, (plaza_x, plaza_y), (7, 11), 25, 0, 360, (235, 241, 231), -1)
    cv2.rectangle(
        image,
        (airport_x - 27, airport_y - 20),
        (airport_x + 27, airport_y + 20),
        (96, 94, 105),
        -1,
    )
    return image


def factor(result: dict, key: str) -> dict:
    return next(item for item in result["factors"] if item["key"] == key)


ROCK_FIXTURES = Path(__file__).parent / "fixtures" / "coastal-rocks"
COMPLEMENTARY_REEF_FIXTURE = ROCK_FIXTURES / "complementary-large-reef.png"
SINGLE_LARGE_REEF_FIXTURE = ROCK_FIXTURES / "supported-single-large.png"
AIRPORT_PLAZA_FIXTURES = Path(__file__).parent / "fixtures" / "airport-plaza"
COHERENT_OFFSET_PERFECT_FIXTURE = AIRPORT_PLAZA_FIXTURES / "coherent-offset-perfect.png"
TOO_CLOSE_AIRPORT_PLAZA_FIXTURE = AIRPORT_PLAZA_FIXTURES / "unsupported-too-close-17.4.png"
RIGHT_OFFSET_EXIT_ALIGNED_FIXTURE = (
    AIRPORT_PLAZA_FIXTURES / "right-offset-exit-aligned-too-close.png"
)
PENINSULA_FIXTURES = Path(__file__).parent / "fixtures" / "peninsula"


def _fixture(name: str) -> np.ndarray:
    image = cv2.imread(str(ROCK_FIXTURES / name))
    assert image is not None
    return image


def _large_rock_count(image: np.ndarray) -> int:
    summary = factor(analyze_map(image), "coastalRocks")["summary"]
    match = re.match(r"(\d+) 块完整大礁石", summary)
    assert match is not None
    return int(match.group(1))


def _fragment_count(image: np.ndarray) -> int:
    summary = factor(analyze_map(image), "coastalRocks")["summary"]
    if "无碎礁" in summary:
        return 0
    match = re.search(r"(\d+) 处碎礁", summary)
    assert match is not None
    return int(match.group(1))


def test_candidate_matching_the_requested_shape_passes_hard_conditions() -> None:
    result = analyze_map(candidate_map())

    assert result["hardPass"] is True
    assert result["score"] >= 0.76
    assert len(result["factors"]) == 6
    assert all(item["key"] != "riverSimplicity" for item in result["factors"])
    assert factor(result, "coastalRocks")["passed"] is True
    assert factor(result, "coastalRocks")["summary"] == "2 块完整大礁石（左右各 1） · 无碎礁"
    assert factor(result, "riverMouths")["passed"] is True
    assert factor(result, "riverMouths")["summary"] == "南 + 东入海（非双南）"


def test_peninsula_prioritizes_extension_but_requires_the_supported_span() -> None:
    extended = factor(
        analyze_map(candidate_map(peninsula_height=24, peninsula_x=10)),
        "peninsula",
    )
    shallow = factor(
        analyze_map(candidate_map(peninsula_height=24, peninsula_x=30)),
        "peninsula",
    )
    too_thin = factor(
        analyze_map(candidate_map(peninsula_height=18, peninsula_x=10)),
        "peninsula",
    )

    assert extended["passed"] is True
    assert "块状浮岛合格" in extended["summary"]
    assert shallow["passed"] is False
    assert too_thin["passed"] is False
    assert "指定浮岛" in shallow["summary"]
    assert extended["score"] > shallow["score"]


def test_peninsula_uses_the_mainland_median_when_coast_variation_biases_outer_quantiles() -> None:
    grass = np.zeros((144, 192), dtype=np.uint8)
    grass[8:119, 44:146] = 255

    # Ordinary rounded-coast variation occupies enough rows to drag the old
    # outer-biased percentile to x=39, but it is too shallow to be a peninsula.
    grass[40:75, 39:44] = 255
    # A real sustained west peninsula remains deep and wide relative to the
    # mainland median.  This mirrors audit 1787734230627-964fb133/card 3.
    grass[20:31, 31:44] = 255

    result, side = _score_peninsula(grass)

    assert result.passed is True
    assert result.score >= 0.60
    assert side == "west"
    assert "左岸块状浮岛合格" in result.summary


def test_peninsula_prefers_a_valid_run_over_a_deeper_but_too_thin_spike() -> None:
    grass = np.zeros((144, 192), dtype=np.uint8)
    grass[8:119, 44:146] = 255
    grass[20:25, 20:44] = 255  # deeper, but only 3.5% of the coast height
    grass[50:61, 31:44] = 255  # less deep, but has the larger supported exterior area

    result, side = _score_peninsula(grass)

    assert result.passed is True
    assert side == "west"
    assert "外伸 6.8%" in result.summary
    assert "结构高度 7.6%" in result.summary
    assert "外形面积" in result.summary


def test_peninsula_requires_ten_rows_in_the_fixed_grid() -> None:
    grass = np.zeros((144, 192), dtype=np.uint8)
    grass[8:119, 44:146] = 255
    grass[20:29, 31:44] = 255  # 9 / 144 rows = 6.25%, shown as 6.2%.

    too_thin, side = _score_peninsula(grass)

    assert too_thin.passed is False
    assert side == "west"
    assert "结构高度 6.2%" in too_thin.summary
    assert "外伸结构过薄" in too_thin.summary

    thick_enough_grass = np.zeros_like(grass)
    thick_enough_grass[8:119, 44:146] = 255
    thick_enough_grass[20:30, 31:44] = 255  # 10 / 144 rows = 6.94%.
    thick_enough, _ = _score_peninsula(thick_enough_grass)

    assert thick_enough.passed is True
    assert "结构高度 6.9%" in thick_enough.summary


def test_peninsula_rejects_a_tapered_bar_at_the_nine_row_boundary() -> None:
    grass = np.zeros((144, 192), dtype=np.uint8)
    grass[8:119, 44:146] = 255
    for y, depth in zip(range(20, 29), [10, 11, 12, 13, 13, 13, 12, 11, 10]):
        grass[y, 44 - depth : 44] = 255

    result, side = _score_peninsula(grass)

    assert result.passed is False
    assert side == "west"
    assert "结构高度 6.2%" in result.summary
    assert "外伸结构过薄" in result.summary


def test_peninsula_rejects_a_block_within_the_side_river_shoulder_zone() -> None:
    grass = np.zeros((144, 192), dtype=np.uint8)
    grass[8:119, 44:146] = 255
    grass[71:82, 146:160] = 255
    water = np.zeros_like(grass)
    water[55:61, 136:160] = 255

    result, side = _score_peninsula(grass, water)

    assert result.passed is False
    assert side == "east"
    assert "紧邻横向河口" in result.summary

    farther_grass = np.zeros_like(grass)
    farther_grass[8:119, 44:146] = 255
    farther_grass[88:108, 146:160] = 255
    farther_result, farther_side = _score_peninsula(farther_grass, water)

    assert farther_result.passed is True
    assert farther_side == "east"


@pytest.mark.parametrize(
    ("name", "side"),
    [
        ("supported-east-wide.png", "右岸"),
        ("supported-west-wide.png", "左岸"),
        # Exact audit 1788420150791-7677df7c/card 4. The former row-run
        # detector selected its smaller river shoulder instead of this larger
        # green exterior component.
        ("supported-west-exterior-area.png", "左岸"),
        # Legacy filename from the superseded 8% maximum-height rule. This is
        # a user-confirmed block silhouette and must remain accepted.
        ("unsupported-west-too-tall-2.png", "左岸"),
    ],
)
def test_user_supplied_block_peninsula_families_pass(name: str, side: str) -> None:
    image = cv2.imread(str(PENINSULA_FIXTURES / name))
    assert image is not None

    result = factor(analyze_map(image), "peninsula")

    assert result["passed"] is True
    assert result["label"] == "指定浮岛结构"
    assert f"{side}块状浮岛合格" in result["summary"]


@pytest.mark.parametrize(
    "name",
    [
        "unsupported-east-shallow.png",
        "unsupported-west-shallow.png",
        "unsupported-west-too-tall.png",
    ],
)
def test_other_peninsula_silhouettes_are_rejected(name: str) -> None:
    image = cv2.imread(str(PENINSULA_FIXTURES / name))
    assert image is not None

    result = factor(analyze_map(image), "peninsula")

    assert result["passed"] is False
    assert "指定浮岛" in result["summary"]


def test_audit_1788101808190_rounded_corner_nub_is_rejected() -> None:
    image = cv2.imread(str(PENINSULA_FIXTURES / "unsupported-west-rounded-corner-nub.png"))
    assert image is not None

    result = factor(analyze_map(image), "peninsula")

    assert result["passed"] is False
    assert "未匹配指定浮岛" in result["summary"]


def test_beach_shape_ignores_unrelated_structure_below_the_coast() -> None:
    sand = np.zeros((144, 192), dtype=np.uint8)
    for x in range(16, 176):
        shoreline_y = 108 + round(4 * np.sin(x / 19))
        sand[62 : shoreline_y + 1, x] = 255
    unrelated_background = np.zeros_like(sand)
    unrelated_background[126:, :] = 255

    clean = _score_beach_shape(sand, np.zeros_like(sand))
    contaminated = _score_beach_shape(sand, unrelated_background)

    assert contaminated.score == clean.score
    assert contaminated.passed == clean.passed
    assert contaminated.summary == clean.summary


def test_double_south_mouth_is_a_hard_rejection() -> None:
    result = analyze_map(candidate_map(double_south=True))

    assert result["hardPass"] is False
    assert factor(result, "riverMouths")["passed"] is False
    assert "双南" in factor(result, "riverMouths")["summary"]


def test_fragmented_coastal_rocks_are_a_hard_rejection() -> None:
    result = analyze_map(candidate_map(fragmented_rock=True))

    assert result["hardPass"] is False
    assert factor(result, "coastalRocks")["passed"] is False
    assert "碎礁" in factor(result, "coastalRocks")["summary"]


def test_one_complete_large_reef_is_preferred_but_fragments_still_reject() -> None:
    single = factor(analyze_map(candidate_map(single_large_rock=True)), "coastalRocks")
    pair = factor(analyze_map(candidate_map()), "coastalRocks")
    fragmented = factor(
        analyze_map(candidate_map(single_large_rock=True, fragmented_rock=True)),
        "coastalRocks",
    )

    assert single["passed"] is True
    assert single["score"] == pytest.approx(1.0)
    assert single["score"] > pair["score"]
    assert single["summary"].startswith("1 块完整大礁石（单块优先） · 无碎礁")
    assert pair["passed"] is True
    assert fragmented["passed"] is False
    assert "碎礁" in fragmented["summary"]


def test_supplied_single_large_reef_map_is_accepted_and_preferred() -> None:
    image = cv2.imread(str(SINGLE_LARGE_REEF_FIXTURE))
    assert image is not None

    rocks = factor(analyze_map(image), "coastalRocks")

    assert rocks["passed"] is True
    assert rocks["score"] == pytest.approx(1.0)
    assert rocks["summary"].startswith("1 块完整大礁石（单块优先） · 无碎礁")


def test_fixed_north_and_river_mouth_rocks_do_not_count_as_fragments() -> None:
    plain = analyze_map(candidate_map())
    decorated = analyze_map(candidate_map(fixed_rock_decorations=True))

    plain_rocks = factor(plain, "coastalRocks")
    decorated_rocks = factor(decorated, "coastalRocks")
    assert decorated_rocks["passed"] is True
    assert decorated_rocks["score"] == plain_rocks["score"]
    assert "无碎礁" in decorated_rocks["summary"]
    assert "北岸固定礁" in decorated_rocks["summary"]
    assert "河口护岸礁" in decorated_rocks["summary"]


def test_real_audit_crops_separate_tall_and_compact_large_reefs_from_small_reefs() -> None:
    # The historical filename predates confirmation that the compact, two-lobed
    # east formation is also a complete large reef.
    assert _large_rock_count(_fixture("true-large-left.jpg")) == 2
    assert _large_rock_count(_fixture("true-large-both-with-fragment.jpg")) == 2
    assert _large_rock_count(_fixture("true-large-both.jpg")) == 2
    assert _large_rock_count(_fixture("small-reefs-only.jpg")) == 0


def test_large_reef_budget_can_leave_one_small_but_complete_opposite_reef() -> None:
    image = cv2.imread(str(COMPLEMENTARY_REEF_FIXTURE))
    assert image is not None

    rocks = factor(analyze_map(image), "coastalRocks")

    assert rocks["passed"] is True
    assert rocks["score"] < factor(analyze_map(cv2.imread(str(SINGLE_LARGE_REEF_FIXTURE))), "coastalRocks")["score"]
    assert rocks["summary"].startswith("2 块完整大礁石（左大右小，总量合格） · 无碎礁")
    # Two small ovals alone still do not satisfy the shared material budget.
    assert _large_rock_count(_fixture("small-reefs-only.jpg")) == 0


def test_complete_reef_satellites_are_not_reported_as_detached_fragments() -> None:
    complete = factor(analyze_map(_fixture("true-large-both.jpg")), "coastalRocks")
    detached = factor(
        analyze_map(_fixture("true-large-both-with-fragment.jpg")),
        "coastalRocks",
    )

    assert complete["passed"] is True
    assert _fragment_count(_fixture("true-large-both.jpg")) == 0
    assert detached["passed"] is False
    assert _fragment_count(_fixture("true-large-both-with-fragment.jpg")) == 1


def test_real_large_reef_classification_survives_capture_disturbances() -> None:
    fixtures = {
        "true-large-left.jpg": 2,
        "true-large-both.jpg": 2,
        "small-reefs-only.jpg": 0,
    }
    for name, expected in fixtures.items():
        image = _fixture(name)
        height, width = image.shape[:2]
        encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]
        variants = [
            image,
            cv2.convertScaleAbs(image, alpha=1, beta=8),
            cv2.convertScaleAbs(image, alpha=1, beta=-8),
            cv2.imdecode(encoded, cv2.IMREAD_COLOR),
            cv2.resize(
                cv2.resize(
                    image,
                    (round(width * 0.96), round(height * 0.96)),
                    interpolation=cv2.INTER_AREA,
                ),
                (width, height),
                interpolation=cv2.INTER_LINEAR,
            ),
        ]
        assert [_large_rock_count(variant) for variant in variants] == [expected] * len(variants)


def test_complementary_reef_budget_survives_capture_disturbances() -> None:
    image = cv2.imread(str(COMPLEMENTARY_REEF_FIXTURE))
    assert image is not None
    height, width = image.shape[:2]
    encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]
    variants = [
        image,
        cv2.convertScaleAbs(image, alpha=1, beta=8),
        cv2.convertScaleAbs(image, alpha=1, beta=-8),
        cv2.imdecode(encoded, cv2.IMREAD_COLOR),
        cv2.resize(
            cv2.resize(
                image,
                (round(width * 0.96), round(height * 0.96)),
                interpolation=cv2.INTER_AREA,
            ),
            (width, height),
            interpolation=cv2.INTER_LINEAR,
        ),
    ]

    assert [_large_rock_count(variant) for variant in variants] == [2] * len(variants)
    assert [_fragment_count(variant) for variant in variants] == [0] * len(variants)


def test_mouth_detector_ignores_internal_water_and_keeps_only_two_ocean_crossings() -> None:
    water = np.zeros((144, 192), dtype=np.uint8)
    cv2.rectangle(water, (69, 82), (78, 143), 255, -1)  # south mouth
    cv2.rectangle(water, (130, 52), (191, 61), 255, -1)  # east mouth
    cv2.circle(water, (48, 62), 13, 255, -1)  # internal pond near the west
    cv2.line(water, (50, 75), (115, 100), 255, 7)  # internal branch

    assert _detect_mouths(water) == ["south", "east"]
    positions = _detect_mouth_positions(water)
    assert positions[0][0] == "south"
    assert np.isclose(positions[0][1], 73.5 / 192)
    assert positions[1][0] == "east"
    assert np.isclose(positions[1][1], 56.5 / 144)


def test_mouth_detector_preserves_double_south_layout() -> None:
    water = np.zeros((144, 192), dtype=np.uint8)
    cv2.rectangle(water, (58, 82), (66, 143), 255, -1)
    cv2.rectangle(water, (122, 82), (130, 143), 255, -1)

    assert _detect_mouths(water) == ["south", "south"]


def test_airport_alignment_is_a_hard_condition() -> None:
    aligned = analyze_map(candidate_map(airport_x=258))
    offset = analyze_map(candidate_map(airport_x=370))

    assert factor(aligned, "airportPlaza")["score"] > factor(offset, "airportPlaza")["score"]
    assert aligned["hardPass"] is True
    assert offset["hardPass"] is False
    assert factor(offset, "airportPlaza")["passed"] is False


def test_airport_and_plaza_allow_a_bounded_coherent_shared_offset() -> None:
    centered = factor(analyze_map(candidate_map(airport_x=258, plaza_x=250)), "airportPlaza")
    coherent = factor(
        analyze_map(candidate_map(airport_x=282, plaza_x=274)),
        "airportPlaza",
    )
    shifted_too_far = factor(
        analyze_map(candidate_map(airport_x=293, plaza_x=285)),
        "airportPlaza",
    )

    assert centered["passed"] is True
    assert coherent["passed"] is True
    assert "共同偏移但轴线一致" in coherent["summary"]
    assert shifted_too_far["passed"] is False
    assert "机场偏离中线" in shifted_too_far["summary"]
    assert "广场偏离中线" in shifted_too_far["summary"]


def test_supplied_reference_map_passes_the_coherent_airport_plaza_rule() -> None:
    image = cv2.imread(str(COHERENT_OFFSET_PERFECT_FIXTURE))
    assert image is not None

    result = analyze_map(image)
    airport_plaza = factor(result, "airportPlaza")

    assert airport_plaza["passed"] is True
    assert "机场本体右偏 2.0%" in airport_plaza["summary"]
    assert "机场出口距中线 7.4%" in airport_plaza["summary"]
    assert "广场距中线 7.1%" in airport_plaza["summary"]
    assert "出口横向错位 0.3%" in airport_plaza["summary"]
    assert "共同偏移但轴线一致" in airport_plaza["summary"]
    # The same map also carries the user-confirmed west exterior-area shape.
    # It used to be reduced to a short row run; the connected-area model must
    # now keep and accept the complete silhouette.
    assert factor(result, "peninsula")["passed"] is True
    assert "外形面积 0.51%" in factor(result, "peninsula")["summary"]
    assert result["hardPass"] is True
    assert result["score"] >= 0.83


def test_airport_plaza_mutual_horizontal_offset_is_limited_to_two_percent() -> None:
    within_limit = factor(analyze_map(candidate_map(airport_x=270)), "airportPlaza")
    excessive = factor(analyze_map(candidate_map(airport_x=271)), "airportPlaza")

    assert within_limit["passed"] is True
    assert excessive["passed"] is False
    assert "出口与广场错位（上限 2.0%）" in excessive["summary"]


def test_airport_distance_requires_20_percent_separation_and_has_no_too_far_rejection() -> None:
    too_close = analyze_map(candidate_map(airport_x=258, plaza_y=246))
    long_enough = analyze_map(candidate_map(airport_x=258, plaza_y=244))
    farther = analyze_map(candidate_map(airport_x=258, plaza_y=120))

    assert factor(too_close, "airportPlaza")["passed"] is False
    assert "间距 19.7%（过近）" in factor(too_close, "airportPlaza")["summary"]
    assert "间距过近（需 ≥20.0%）" in factor(too_close, "airportPlaza")["summary"]
    assert factor(long_enough, "airportPlaza")["passed"] is True
    assert "间距 20.3%（合格）" in factor(long_enough, "airportPlaza")["summary"]
    assert factor(farther, "airportPlaza")["passed"] is True


def test_audit_1788155968623_airport_plaza_distance_17_4_is_rejected() -> None:
    image = cv2.imread(str(TOO_CLOSE_AIRPORT_PLAZA_FIXTURE))
    assert image is not None

    result = factor(analyze_map(image), "airportPlaza")

    assert result["passed"] is False
    assert "间距 17.5%（过近）" in result["summary"]
    assert "间距过近（需 ≥20.0%）" in result["summary"]


def test_audit_1788394985095_right_shift_aligns_the_airport_exit_with_plaza() -> None:
    image = cv2.imread(str(RIGHT_OFFSET_EXIT_ALIGNED_FIXTURE))
    assert image is not None

    result = factor(analyze_map(image), "airportPlaza")

    assert "机场本体右偏 2.3%" in result["summary"]
    assert "出口横向错位 0.0%" in result["summary"]
    assert "出口与广场错位" not in result["summary"]
    assert "机场偏离中线" not in result["summary"]
    assert "广场偏离中线" not in result["summary"]
    assert result["passed"] is True
    assert "间距 23.3%（合格）" in result["summary"]


def test_airport_exit_alignment_accounts_for_its_left_offset() -> None:
    body_centered = analyze_map(candidate_map(airport_x=250))
    exit_centered = analyze_map(candidate_map(airport_x=261))

    assert factor(exit_centered, "airportPlaza")["score"] > factor(body_centered, "airportPlaza")["score"]
    assert "机场本体右偏 2.5%" in factor(exit_centered, "airportPlaza")["summary"]
    assert "出口横向错位 0.2%" in factor(exit_centered, "airportPlaza")["summary"]


def test_airport_selector_rejects_flat_bottom_edge_artifacts() -> None:
    actual_airport = Component(64, 114, 115, 16, 7, 122.4375, 118.0625, 0.57)
    bottom_edge = Component(86, 68, 139, 30, 3, 82.5, 140.0, 0.96)

    selected, confidence = _choose_structure(
        [actual_airport, bottom_edge],
        width=192,
        height=144,
        kind="airport",
    )

    assert selected is actual_airport
    assert confidence > 0.45


def test_fox_beach_must_hug_an_outer_edge_and_gets_same_side_bonus() -> None:
    beside_west_peninsula = analyze_map(candidate_map(fox_x=105))
    audited_outer_limit = analyze_map(candidate_map(fox_x=145))
    opposite_side = analyze_map(candidate_map(fox_x=375))
    too_central = analyze_map(candidate_map(fox_x=240))

    west = factor(beside_west_peninsula, "foxBeach")
    east = factor(opposite_side, "foxBeach")
    central = factor(too_central, "foxBeach")
    assert west["passed"] is True
    assert "与浮岛同侧，满分" in west["summary"]
    assert west["score"] == 1
    assert factor(audited_outer_limit, "foxBeach")["passed"] is True
    assert factor(audited_outer_limit, "foxBeach")["score"] == 1
    assert east["passed"] is True
    assert west["score"] > east["score"]
    assert central["passed"] is False
    assert "上方中段" in central["summary"]


def test_selection_hand_cursor_is_removed_without_touching_the_map_center() -> None:
    image = candidate_map()
    original_center = image[150, 220].copy()
    cv2.circle(image, (466, 330), 34, (40, 40, 40), -1)
    cv2.circle(image, (466, 330), 27, (242, 242, 242), -1)

    cleaned = _suppress_selection_cursor(image)

    assert np.array_equal(cleaned[150, 220], original_center)
    assert not np.array_equal(cleaned[330, 466], np.array([242, 242, 242], dtype=np.uint8))
