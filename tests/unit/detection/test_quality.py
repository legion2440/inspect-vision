from __future__ import annotations

from backend.detection.dto import BoundingBox, InspectionDefect
from backend.detection.quality import calculate_quality_score


def _defect(
    defect_type: str,
    confidence: float,
    box: tuple[float, float, float, float],
) -> InspectionDefect:
    return InspectionDefect(defect_type, confidence, BoundingBox(*box))


def test_clean_image_scores_100() -> None:
    assert calculate_quality_score((), image_width=100, image_height=100) == 100


def test_mild_defect_uses_quality_v1_formula() -> None:
    mild = _defect("crazing", 0.8, (0.0, 0.0, 10.0, 10.0))

    score = calculate_quality_score(
        (mild,),
        image_width=100,
        image_height=100,
        class_weights={"crazing": 1.25},
    )

    assert score == 89


def test_multiple_defects_compound_penalty() -> None:
    first = _defect("inclusion", 0.8, (0.0, 0.0, 20.0, 20.0))
    second = _defect("scratches", 0.7, (50.0, 50.0, 20.0, 20.0))

    weights = {"inclusion": 1.1, "scratches": 0.85}
    combined = calculate_quality_score(
        (first, second), image_width=100, image_height=100, class_weights=weights
    )
    individual = calculate_quality_score(
        (first,), image_width=100, image_height=100, class_weights=weights
    )

    assert combined < individual < 100


def test_severe_defects_clamp_score_to_zero() -> None:
    severe = tuple(
        _defect("crazing", 1.0, (0.0, 0.0, 100.0, 100.0))
        for _ in range(2)
    )

    assert calculate_quality_score(
        severe,
        image_width=100,
        image_height=100,
        class_weights={"crazing": 1.25},
    ) == 0


def test_unconfigured_class_uses_explicit_neutral_weight() -> None:
    crack = _defect("crack", 0.8, (0.0, 0.0, 10.0, 10.0))

    assert calculate_quality_score(
        (crack,), image_width=100, image_height=100, default_weight=1.0
    ) == 91
