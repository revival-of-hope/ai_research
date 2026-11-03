"""Controlled UC08 fixture matrix validates domain statuses, not model extraction."""

from pathlib import Path

import pytest

from app.domain.comparison import Evidence, build_fields, field_status

FIXTURES = Path(__file__).parent / "fixtures" / "uc08"
LABELS = {
    "dataset": "Dataset",
    "version": "Version",
    "split": "Split",
    "model": "Model",
    "preprocessing": "Preprocessing",
    "seed": "Seed",
    "metric": "Metric",
    "unit": "Unit",
    "value": "Value",
}
PAPER = {
    "dataset": "ImageNet",
    "version": "ILSVRC-2012",
    "split": "validation",
    "model": "1 CNN",
    "preprocessing": "ten-patch evaluation",
    "metric": "top-1 error",
    "unit": "percent",
    "value": "40.7%",
}

# All unspecified fields match the controlled paper; paper seed remains unknown.
CASES = [
    ("01-split-conflict.md", {"split": "mismatch"}),
    ("02-version-conflict.md", {"version": "mismatch"}),
    ("03-model-conflict.md", {"model": "mismatch"}),
    ("04-preprocessing-conflict.md", {"preprocessing": "mismatch"}),
    # A different measured quantity makes the two numbers incomparable: the value
    # stays unknown instead of being reported as a like-for-like difference.
    ("06-metric-conflict.md", {"metric": "mismatch", "value": "unknown"}),
    ("07-value-conflict.md", {"value": "mismatch"}),
    (
        "08-missing-conditions.md",
        {"version": "unknown", "split": "unknown", "preprocessing": "unknown"},
    ),
    ("09-run-only-seed.md", {}),
]


def _evidence(fields: dict[str, str], block_id: int) -> dict[str, Evidence]:
    return {
        key: Evidence(value, f"{LABELS[key]}: {value}", block_id)
        for key, value in fields.items()
    }


def _fixture_values(filename: str) -> dict[str, str]:
    # Fixture-only label parsing; production extraction always goes through the AI adapter.
    lines = (FIXTURES / filename).read_text(encoding="utf-8").splitlines()
    result = {}
    for key, label in LABELS.items():
        prefix = f"{label}: "
        matches = [line for line in lines if line.startswith(prefix)]
        assert len(matches) <= 1, (filename, label)
        if matches:
            result[key] = matches[0][len(prefix):]
    return result


@pytest.mark.parametrize(("filename", "overrides"), CASES)
def test_controlled_run_cases_match_annotated_comparison_statuses(filename, overrides):
    source = (FIXTURES / filename).read_text(encoding="utf-8")
    assert "No training was executed" in source

    paper = _evidence(PAPER, 1)
    run_values = _fixture_values(filename)
    run = _evidence(run_values, 2)
    expected = {
        key: "unknown" if key == "seed" else "aligned"
        for key in LABELS
    }
    expected["training"] = "unknown"
    expected.update(overrides)

    fields = build_fields(paper, run)
    assert {field.key: field.status for field in fields} == expected
    assert all(field.review_status == "pending" for field in fields)
    for key, evidence in run.items():
        assert evidence.value in source, (filename, key)


def test_multirow_fixture_requires_correct_row_binding_before_confirming():
    source = (FIXTURES / "10-multi-row-distractor.md").read_text(encoding="utf-8")
    assert "| 5 CNN ensemble | 38.1% |" in source
    assert "| 1 CNN | 40.7% |" in source
    assert "Comparison intent: compare the 1 CNN row." in source
    # A matching number alone cannot establish a matching model or experiment.
    fields = build_fields(
        _evidence(PAPER, 1),
        {"value": Evidence("40.7%", "1 CNN | 40.7%", 2)},
    )
    by_key = {field.key: field.status for field in fields}
    # The run side reports no metric at all, so even the identical number is not
    # comparable: a value only counts behind the same measured quantity.
    assert by_key["value"] == "unknown"
    assert by_key["model"] == "unknown"
    assert by_key["split"] == "unknown"


@pytest.mark.parametrize(
    ("key", "value", "excerpt"),
    [
        ("value", "40.7", "top-1 error 140.7%"),
        ("value", "40.7", "top-1 error 40.70%"),
        ("value", "40.7", "top-1 error -40.7%"),
        ("model", "1 CNN", "Model: 11 CNN"),
        ("seed", "123", "seed: 1234"),
    ],
)
def test_partial_source_token_does_not_support_a_field(key, value, excerpt):
    paper = Evidence(value, excerpt, 1)
    run = Evidence(value, f"reported {value}", 2)
    assert field_status(paper, run, key) == "unknown"
