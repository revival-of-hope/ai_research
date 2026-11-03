"""UC08 field semantics and evidence recovery, replayed on realistic source shapes."""

import pytest

from app.domain.comparison import Evidence, build_fields, field_status
from app.infrastructure.agents.comparison import _fill_explicit_conditions

ROWS = (
    "Second, compared to its plain counterpart, the 34-layer\n"
    "model top-1 err. top-5 err.\n"
    "VGG-16 [40] 28.07 9.33\n"
    "ResNet-50 22.85 6.71\n"
    "ResNet-101 21.75 6.05\n"
    "Table 3. Error rates (%, 10-crop testing) on ImageNet validation.\n"
)
CIFAR = (
    "4.2. CIFAR-10 and Analysis\n"
    "We present experiments trained on the training set and evaluated on the test set.\n"
)
HEADER_ONLY = (
    "method image\n"
    "size #param. FLOPs throughput\n"
    "ImageNet\n"
    "top-1 acc.\n"
    "ImageNet-1K trained models\n"
    "Swin-T 2242 29M 4.5G 755.2 81.3\n"
)
JUNK_SIZES = (
    "Table 6. MobileNetV2 bottleneck residual block.\n"
    "Input Operator t c n s\n"
    "142 × 96 bottleneck 6 160 3 2\n"
    "112 × 112 bottleneck 6 96 1 2\n"
    "Network Top 1 Params MAdds CPU\n"
    "MobileNetV2 72.0 3.4M 300M 75ms\n"
)
RUN_SUMMARY = (
    "# Synthetic run summary\n"
    "TEST FIXTURE ONLY. No training or model evaluation was performed.\n"
    "Dataset: ImageNet\n"
    "Model: MobileNetV2 (1.4)\n"
    "Metric: top-1 accuracy\n"
    "Unit: percent\n"
    "Value: 74.7% (invented for the fixture)\n"
    "Random seed: not reported\n"
)


def chunk(chunk_id, ordinal, content):
    return {"id": chunk_id, "ordinal": ordinal, "content": content}


def statuses(paper_fields, run_fields):
    return {field.key: field.status for field in build_fields(paper_fields, run_fields)}


def test_condition_fields_come_from_the_cited_table_not_another_section():
    chunks = [chunk(1, 0, CIFAR), chunk(2, 1, ROWS)]
    paper = {
        "model": Evidence("ResNet-50", "ResNet-50 22.85 6.71", 2),
        "value": Evidence("22.85", "ResNet-50 22.85 6.71", 2),
        "dataset": Evidence("the test set", "evaluated on the test set", 1),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 error (ResNet-50, Table 3, 10-crop 10-crop)")
    assert paper["dataset"] == Evidence(
        "ImageNet", "Table 3. Error rates (%, 10-crop testing) on ImageNet", 2,
    )
    assert paper["preprocessing"].value == "10-crop testing"
    assert paper["metric"].value == "top-1 err"
    assert paper["split"].value == "validation"


def test_recovered_metric_and_unit_align_with_the_run_summary():
    chunks = [chunk(2, 1, ROWS)]
    paper = {
        "model": Evidence("ResNet-50", "ResNet-50 22.85 6.71", 2),
        "value": Evidence("22.85", "ResNet-50 22.85 6.71", 2),
    }
    run = {
        "dataset": Evidence("ImageNet", "Dataset: ImageNet", 3),
        "split": Evidence("validation", "Evaluation split: validation", 3),
        "model": Evidence("ResNet-50", "Model: ResNet-50", 3),
        "preprocessing": Evidence(
            "10-crop testing", "Evaluation preprocessing: 10-crop testing", 3,
        ),
        "metric": Evidence("top-1 error", "Metric: top-1 error", 3),
        "unit": Evidence("percent", "Unit: percent", 3),
        "value": Evidence("22.85%", "Value: 22.85%", 3),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 error (ResNet-50, Table 3)")
    assert statuses(paper, run) == {
        "dataset": "aligned", "version": "unknown", "split": "aligned",
        "model": "aligned", "training": "unknown", "preprocessing": "aligned",
        "seed": "unknown", "metric": "aligned", "unit": "aligned", "value": "aligned",
    }


def test_header_label_is_recovered_without_misreading_another_metric_column():
    chunks = [chunk(5, 0, HEADER_ONLY)]
    paper = {
        "model": Evidence("Swin-T", "Swin-T 2242 29M 4.5G 755.2 81.3", 5),
        "value": Evidence("81.3", "Swin-T 2242 29M 4.5G 755.2 81.3", 5),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 accuracy (Swin-T, Table 1)")
    assert paper["metric"].value == "top-1 acc"
    assert paper["preprocessing"].value == "2242"
    assert "dataset" not in paper


def test_metric_is_not_filled_when_the_request_names_another_cut_off():
    chunks = [chunk(5, 0, HEADER_ONLY)]
    paper = {
        "model": Evidence("Swin-T", "Swin-T 2242 29M 4.5G 755.2 81.3", 5),
        "value": Evidence("81.3", "Swin-T 2242 29M 4.5G 755.2 81.3", 5),
    }
    _fill_explicit_conditions(paper, chunks, "top-5 accuracy (Swin-T, Table 1)")
    assert "metric" not in paper


def test_unrelated_table_cell_is_not_accepted_as_an_input_resolution():
    chunks = [chunk(6, 0, JUNK_SIZES)]
    paper = {
        "model": Evidence("MobileNetV2", "MobileNetV2 72.0 3.4M 300M 75ms", 6),
        "value": Evidence("72.0", "MobileNetV2 72.0 3.4M 300M 75ms", 6),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 accuracy (MobileNetV2, Table 4)")
    assert "preprocessing" not in paper
    assert paper["metric"].value == "Top 1"


def test_bare_top_one_label_needs_the_source_definition_before_it_counts():
    paper = {
        "model": Evidence("MobileNetV2", "MobileNetV2 Top 1 72.0 71.8", 7),
        "value": Evidence("72.0", "MobileNetV2 Top 1 72.0 71.8", 7),
        "metric": Evidence("Top 1", "MobileNetV2 Top 1 72.0 71.8", 7),
    }
    run = {
        "metric": Evidence("top-1 accuracy", "Metric: top-1 accuracy", 8),
        "value": Evidence("72.0%", "Value: 72.0%", 8),
    }
    assert statuses(paper, run)["metric"] == "unknown"
    paper["unit"] = Evidence("%", "Accuracy, Top 1, %", 7)
    resolved = statuses(paper, run)
    assert resolved["metric"] == "aligned"
    assert resolved["value"] == "aligned"


def test_different_metric_keeps_the_number_unknown_instead_of_a_gap():
    paper = {
        "model": Evidence("MobileNetV2", "MobileNetV2 72.0", 1),
        "metric": Evidence("top-1 accuracy", "Metric top-1 accuracy", 1),
        "value": Evidence("72.0", "MobileNetV2 72.0", 1),
    }
    run = {
        "model": Evidence("MobileNetV2", "Model: MobileNetV2", 2),
        "metric": Evidence("top-5 accuracy", "Metric: top-5 accuracy", 2),
        "value": Evidence("91.0%", "Value: 91.0%", 2),
    }
    resolved = statuses(paper, run)
    assert resolved["metric"] == "mismatch"
    assert resolved["value"] == "unknown"


@pytest.mark.parametrize(
    ("paper_value", "run_value", "expected"),
    [
        pytest.param("top-1 err.", "top-1 error", "aligned", id="abbreviated-error"),
        pytest.param("Top-1 Acc.", "top-1 accuracy", "aligned", id="abbreviated-accuracy"),
        pytest.param("ImageNet top-1 acc.", "top-1 accuracy", "aligned", id="dataset-prefix"),
        pytest.param("IN-1K top-1 acc.", "top-1 accuracy", "aligned", id="short-dataset-prefix"),
        pytest.param("top-1 error", "top-1 accuracy", "mismatch", id="error-is-not-accuracy"),
        pytest.param("top-1 accuracy", "top-5 accuracy", "mismatch", id="different-cut-off"),
    ],
)
def test_metric_spellings_are_normalized_without_merging_definitions(
    paper_value, run_value, expected,
):
    paper = Evidence(paper_value, f"paper {paper_value}", 1)
    run = Evidence(run_value, f"run {run_value}", 2)
    assert field_status(paper, run, "metric") == expected


@pytest.mark.parametrize(
    ("key", "paper_value", "run_value", "expected"),
    [
        pytest.param("unit", "%, 10-crop testing", "percent", "aligned", id="unit-with-convention"),
        pytest.param("unit", "percent", "percentage", "aligned", id="percentage-word"),
        pytest.param("unit", "top-1 accuracy on a single crop", "percent", "unknown", id="no-unit"),
        pytest.param(
            "dataset", "ImageNet validation", "ImageNet", "aligned", id="dataset-with-split",
        ),
        pytest.param("dataset", "the test set", "ImageNet", "unknown", id="generic-dataset"),
        pytest.param("split", "50k validation images", "validation", "aligned", id="split-phrase"),
        pytest.param("preprocessing", "2242", "224 x 224", "aligned", id="flattened-size"),
        pytest.param("preprocessing", "224× 224", "224 x 224", "aligned", id="unicode-size"),
        pytest.param(
            "preprocessing", "single crop", "single-crop, 224 x 224", "unknown",
            id="partial-coverage-is-not-aligned",
        ),
        pytest.param(
            "preprocessing", "single-crop, 224 x 224", "single-crop", "unknown",
            id="missing-resolution-is-not-aligned",
        ),
        pytest.param(
            "preprocessing", "single-crop, 224 x 224", "single-crop, 224 x 224", "aligned",
            id="same-attributes",
        ),
        pytest.param("preprocessing", "10-crop", "center crop", "mismatch", id="crop-conflict"),
        pytest.param("preprocessing", "224 x 224", "384 x 384", "mismatch", id="size-conflict"),
    ],
)
def test_field_values_carry_their_declared_meaning(key, paper_value, run_value, expected):
    paper = Evidence(paper_value, f"paper says {paper_value}", 1)
    run = Evidence(run_value, f"run says {run_value}", 2)
    assert field_status(paper, run, key) == expected


def test_run_summary_labels_fill_fields_the_model_left_out():
    chunks = [chunk(9, 0, RUN_SUMMARY)]
    run = {"dataset": Evidence("ImageNet", "Dataset: ImageNet", 9)}
    _fill_explicit_conditions(run, chunks, "top-1 accuracy (MobileNetV2, Table 4)", side="run")
    assert run["model"] == Evidence("MobileNetV2 (1.4)", "Model: MobileNetV2 (1.4)", 9)
    assert run["metric"].value == "top-1 accuracy"
    assert run["unit"].value == "percent"
    assert run["value"].value == "74.7%"
    assert "seed" not in run


def test_run_summary_labels_never_overwrite_reported_candidates():
    chunks = [chunk(9, 0, RUN_SUMMARY)]
    run = {"value": Evidence("74.7%", "Value: 74.7% (invented for the fixture)", 9)}
    _fill_explicit_conditions(run, chunks, "top-1 accuracy", side="run")
    assert run["value"].value == "74.7%"
    assert run["value"].excerpt == "Value: 74.7% (invented for the fixture)"


def test_paper_recovery_does_not_run_without_a_cited_row():
    chunks = [chunk(2, 1, ROWS)]
    paper = {"dataset": Evidence("ImageNet", "on ImageNet validation", 2)}
    _fill_explicit_conditions(paper, chunks, "top-1 error (ResNet-50, Table 3)")
    # Nothing beyond the reported candidate is added, and no caption is consulted.
    assert paper["dataset"].value == "ImageNet"
    assert set(paper) == {"dataset"}


def test_a_phrase_that_is_not_a_dataset_name_is_dropped():
    chunks = [chunk(1, 0, CIFAR)]
    paper = {"dataset": Evidence("the test set", "evaluated on the test set", 1)}
    _fill_explicit_conditions(paper, chunks, "top-1 error (ResNet-50, Table 3)")
    assert "dataset" not in paper


def _responses_stub(monkeypatch, payloads, answer):
    import asyncio
    import json

    import httpx

    from app.domain.research import ProviderConfig
    from app.infrastructure.agents import comparison

    requests = []
    original_client = httpx.AsyncClient

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json={
            "id": "resp_uc08", "object": "response", "created_at": 1,
            "model": "deepseek-flash", "status": "completed",
            "output": [{
                "id": "msg_uc08", "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": json.dumps(answer), "annotations": []}],
            }],
            "usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
        })

    class MockClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(comparison.httpx, "AsyncClient", MockClient)
    provider = ProviderConfig(
        1, "Test", "https://api.deepseek.com", "deepseek-flash", "placeholder-key", "deepseek",
    )
    return asyncio, comparison, provider, requests


def test_run_summary_prompt_reports_what_is_reported(monkeypatch):
    asyncio, comparison, provider, requests = _responses_stub(
        monkeypatch, None,
        {"fields": [{
            "key": "dataset", "value": "ImageNet", "excerpt": "Dataset: ImageNet", "chunk_id": 9,
        }]},
    )
    result = asyncio.run(comparison.extract_evidence(
        provider,
        {
            "id": 2, "filename": "run.md", "side": "run",
            "chunks": [chunk(9, 0, RUN_SUMMARY)],
        },
        "top-1 accuracy (target model MobileNetV2, Table 4)",
    ))
    assert "evaluation summary written by" in requests[0]["input"][0]["content"]
    assert result["dataset"] == Evidence("ImageNet", "Dataset: ImageNet", 9)
    # The model returned only one field; the explicit label lines describe the rest.
    assert result["model"].value == "MobileNetV2 (1.4)"
    assert result["value"].value == "74.7%"


def test_paper_prompt_keeps_the_target_row_constraints(monkeypatch):
    asyncio, comparison, provider, requests = _responses_stub(
        monkeypatch, None,
        {"fields": [{
            "key": "value", "value": "22.85",
            "excerpt": "ResNet-50 22.85 6.71", "chunk_id": 2,
        }]},
    )
    result = asyncio.run(comparison.extract_evidence(
        provider,
        {
            "id": 1, "filename": "paper.pdf", "side": "paper",
            "chunks": [chunk(1, 0, CIFAR), chunk(2, 1, ROWS)],
        },
        "top-1 error (target model ResNet-50; Table 3, 10-crop ImageNet validation)",
    ))
    instructions = requests[0]["input"][0]["content"]
    assert "research paper" in instructions
    assert "ImageNet-22K" in instructions
    assert "evaluation summary written by" not in instructions
    assert result["dataset"].value == "ImageNet"
    assert result["preprocessing"].value == "10-crop testing"
    assert result["metric"].value == "top-1 err"


def test_an_empty_field_list_is_retried_once(monkeypatch):
    import asyncio
    import json

    import httpx

    from app.domain.research import ProviderConfig
    from app.infrastructure.agents import comparison

    original_client = httpx.AsyncClient
    requests = []
    answers = [
        {"fields": []},
        {"fields": [{
            "key": "value", "value": "22.85",
            "excerpt": "ResNet-50 22.85 6.71", "chunk_id": 2,
        }]},
    ]

    def respond(request):
        requests.append(json.loads(request.content))
        text = json.dumps(answers[min(len(requests) - 1, 1)])
        return httpx.Response(200, json={
            "id": "resp_uc08", "object": "response", "created_at": 1,
            "model": "deepseek-flash", "status": "completed",
            "output": [{
                "id": "msg_uc08", "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }],
            "usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
        })

    class MockClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(comparison.httpx, "AsyncClient", MockClient)
    result = asyncio.run(comparison.extract_evidence(
        ProviderConfig(
            1, "Test", "https://api.deepseek.com", "deepseek-flash", "placeholder-key", "deepseek",
        ),
        {"id": 1, "filename": "paper.pdf", "side": "paper", "chunks": [chunk(2, 1, ROWS)]},
        "top-1 error (target model ResNet-50; Table 3)",
    ))
    assert len(requests) == 2
    assert result["value"].value == "22.85"


def test_a_rejected_citation_is_not_retried(monkeypatch):
    asyncio, comparison, provider, requests = _responses_stub(
        monkeypatch, None,
        {"fields": [{
            "key": "value", "value": "22.85",
            "excerpt": "an excerpt that is not in the source", "chunk_id": 2,
        }]},
    )
    result = asyncio.run(comparison.extract_evidence(
        provider,
        {"id": 1, "filename": "paper.pdf", "side": "paper", "chunks": [chunk(2, 1, ROWS)]},
        "top-1 error (target model ResNet-50; Table 3)",
    ))
    assert len(requests) == 1
    assert "value" not in result


def test_caption_is_never_taken_from_a_relevance_neighbour():
    """The candidate list is ranked by relevance, so list order is not document order."""
    cifar_caption = "Table 9. Error rates (%) on CIFAR-10 test set. Regularization study."
    candidates = [
        # Relevance order: the CIFAR chunk sits right after the ResNet row.
        chunk(40, 3, cifar_caption),
        chunk(41, 17, "model top-1 err. top-5 err.\nResNet-50 22.85 6.71\nResNet-101 21.75 6.05\n"),
    ]
    paper = {
        "model": Evidence("ResNet-50", "ResNet-50 22.85 6.71", 41),
        "value": Evidence("22.85", "ResNet-50 22.85 6.71", 41),
    }
    _fill_explicit_conditions(paper, candidates, "top-1 error (ResNet-50, Table 3)")
    assert "dataset" not in paper
    assert "split" not in paper
    assert paper["metric"].value == "top-1 err"


def test_caption_from_a_document_adjacent_chunk_is_used():
    candidates = [
        chunk(41, 17, "model top-1 err. top-5 err.\nResNet-50 22.85 6.71\n"),
        chunk(40, 16, "text before the table\nTable 3. Error rates (%) on ImageNet validation."),
        chunk(42, 25, "unrelated later section on CIFAR-10"),
    ]
    paper = {
        "model": Evidence("ResNet-50", "ResNet-50 22.85 6.71", 41),
        "value": Evidence("22.85", "ResNet-50 22.85 6.71", 41),
    }
    _fill_explicit_conditions(paper, candidates, "top-1 error (ResNet-50, Table 3)")
    assert paper["dataset"] == Evidence(
        "ImageNet", "Table 3. Error rates (%) on ImageNet", 40,
    )
    assert paper["split"].value == "validation"


def test_reviewing_a_value_respects_the_metric_verdict():
    from app.domain.comparison import read_fields, reconcile_fields, update_field

    paper = {
        "model": Evidence("Swin-T", "Swin-T 2242 ...", 1),
        "metric": Evidence("top-1 accuracy", "top-1 accuracy", 1),
        "value": Evidence("81.3", "Swin-T 2242 81.3", 1),
    }
    run = {
        "model": Evidence("Swin-T", "Model: Swin-T", 2),
        "metric": Evidence("top-5 accuracy", "Metric: top-5 accuracy", 2),
        "value": Evidence("81.3%", "Value: 81.3%", 2),
    }
    fields = build_fields(paper, run)
    assert {f.key: f.status for f in fields}["value"] == "unknown"

    by_key = {f.key: i for i, f in enumerate(fields)}
    index = by_key["value"]
    fields[index] = update_field(
        fields[index], "81.3", "81.3%", "confirmed", "核对过原文数值",
    )
    # A single-field review must not resurrect a value behind a different metric.
    assert read_fields([as_dict(fields[index])])[0].status == "aligned"
    reconciled = {f.key: f.status for f in reconcile_fields(fields)}
    assert reconciled["metric"] == "mismatch"
    assert reconciled["value"] == "unknown"


def as_dict(field):
    from dataclasses import asdict

    return asdict(field)


@pytest.mark.parametrize(
    ("paper", "run", "expected"),
    [
        pytest.param(
            {"value": Evidence("81.3", "paper 81.3", 1)},
            {"value": Evidence("81.3%", "run 81.3%", 2)},
            "unknown", id="both-metrics-missing",
        ),
        pytest.param(
            {"metric": Evidence("top-1 accuracy", "top-1 accuracy", 1),
             "value": Evidence("81.3", "paper 81.3", 1)},
            {"value": Evidence("81.3%", "run 81.3%", 2)},
            "unknown", id="one-metric-missing",
        ),
        pytest.param(
            {"metric": Evidence("top-1 accuracy", "top-1 accuracy", 1),
             "value": Evidence("81.3", "paper 81.3", 1)},
            {"metric": Evidence("top-1 acc.", "top-1 acc.", 2),
             "value": Evidence("81.3%", "run 81.3%", 2)},
            "aligned", id="same-metric",
        ),
        pytest.param(
            {"metric": Evidence("top-1 accuracy", "top-1 accuracy", 1),
             "value": Evidence("81.3", "paper 81.3", 1)},
            {"metric": Evidence("top-5 accuracy", "top-5 accuracy", 2),
             "value": Evidence("81.3%", "run 81.3%", 2)},
            "unknown", id="different-metric",
        ),
    ],
)
def test_numbers_are_only_comparable_behind_the_same_metric(paper, run, expected):
    assert {field.key: field.status for field in build_fields(paper, run)}["value"] == expected


def test_review_cannot_compare_numbers_when_the_metric_is_missing():
    from app.domain.comparison import reconcile_fields, update_field

    paper = {"value": Evidence("81.3", "paper 81.3", 1)}
    run = {"value": Evidence("81.3%", "run 81.3%", 2)}
    fields = build_fields(paper, run)
    index = next(i for i, field in enumerate(fields) if field.key == "value")
    fields[index] = update_field(fields[index], "81.3", "81.3%", "confirmed", "已核对")
    reconciled = {field.key: field.status for field in reconcile_fields(fields)}
    assert reconciled["value"] == "unknown"


ROW_ONLY = "Top-1\nMobileNetV2 72.0 71.8\n"
OTHER_SECTION = (
    "3.4 Comparison with other methods\n"
    "We also evaluate MobileNetV2 on the test set with 10-crop testing.\n"
)


def test_a_repeated_model_in_another_section_does_not_supply_the_protocol():
    """The same model may be reported again elsewhere under a different protocol."""
    chunks = [
        chunk(3, 3, OTHER_SECTION),
        chunk(11, 11, ROW_ONLY),
    ]
    paper = {
        "model": Evidence("MobileNetV2", "MobileNetV2 72.0 71.8", 11),
        "value": Evidence("72.0", "MobileNetV2 72.0 71.8", 11),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 accuracy (MobileNetV2, Table 4)")
    # The cited row names neither a crop protocol nor a split, and the section that
    # does is not part of this experiment: both stay unknown.
    assert "preprocessing" not in paper
    assert "split" not in paper


def test_a_repeated_model_in_another_section_does_not_supply_the_unit():
    """Another section quoting the same number as a percentage is not this unit."""
    chunks = [
        chunk(2, 2, "3.5 Comparison with other methods\nMobileNetV2 reaches 72.0% on ImageNet.\n"),
        chunk(11, 11, ROW_ONLY),
    ]
    paper = {
        "model": Evidence("MobileNetV2", "MobileNetV2 72.0 71.8", 11),
        "value": Evidence("72.0", "MobileNetV2 72.0 71.8", 11),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 accuracy (MobileNetV2, Table 4)")
    assert "unit" not in paper


def test_the_protocol_beside_the_cited_row_is_still_used():
    chunks = [
        chunk(10, 10, "All MobileNetV2 results use 10-crop testing on the validation set."),
        chunk(11, 11, ROW_ONLY),
    ]
    paper = {
        "model": Evidence("MobileNetV2", "MobileNetV2 72.0 71.8", 11),
        "value": Evidence("72.0", "MobileNetV2 72.0 71.8", 11),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 accuracy (MobileNetV2, Table 4)")
    assert paper["preprocessing"].value == "10-crop testing"
    assert paper["split"].value == "validation"


def test_the_same_window_is_shared_by_every_recovery_path():
    """A distant chunk naming the model is outside the window for unit as well."""
    chunks = [
        chunk(2, 2, "Top1 Acc (%)\nMobileNetV2\n"),
        chunk(5, 5, OTHER_SECTION),
        chunk(11, 11, ROW_ONLY),
        chunk(30, 30, "MobileNetV2 71.8 70.1 69.4\n"),
    ]
    paper = {
        "model": Evidence("MobileNetV2", "MobileNetV2 72.0 71.8", 11),
        "value": Evidence("72.0", "MobileNetV2 72.0 71.8", 11),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 accuracy (MobileNetV2, Table 4)")
    assert set(paper) == {"model", "value"}


def test_a_model_citation_in_another_section_does_not_widen_the_window():
    """The window is the cited result row, not every chunk the model was cited from."""
    chunks = [
        chunk(3, 3, OTHER_SECTION),
        chunk(11, 11, ROW_ONLY),
    ]
    paper = {
        # The model name was "found" in the unrelated section.
        "model": Evidence("MobileNetV2", "We also evaluate MobileNetV2", 3),
        "value": Evidence("72.0", "MobileNetV2 72.0 71.8", 11),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 accuracy (MobileNetV2, Table 4)")
    assert "preprocessing" not in paper
    assert "split" not in paper


def test_without_a_cited_result_row_nothing_is_recovered():
    chunks = [
        chunk(3, 3, OTHER_SECTION),
        chunk(11, 11, ROW_ONLY),
    ]
    paper = {"model": Evidence("MobileNetV2", "We also evaluate MobileNetV2", 3)}
    _fill_explicit_conditions(paper, chunks, "top-1 accuracy (MobileNetV2, Table 4)")
    assert set(paper) == {"model"}


RESNET_ROW = "model top-1 err. top-5 err.\nResNet-50 22.85 6.71\n"


def test_a_caption_from_another_table_is_rejected_for_a_named_table():
    """Requesting Table 3 must not borrow Table 9's dataset, split or unit."""
    chunks = [
        chunk(16, 16, "3.2. CIFAR-10\nTable 9. Error rates (%) on CIFAR-10 test set.\n"),
        chunk(17, 17, RESNET_ROW),
    ]
    paper = {
        "model": Evidence("ResNet-50", "ResNet-50 22.85 6.71", 17),
        "value": Evidence("22.85", "ResNet-50 22.85 6.71", 17),
        "metric": Evidence("top-1 err.", "model top-1 err. top-5 err.", 17),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 error (ResNet-50, Table 3)")
    assert "dataset" not in paper
    assert "split" not in paper
    assert "unit" not in paper


def test_the_caption_of_the_named_table_is_used():
    chunks = [
        chunk(16, 16, "3.1. ImageNet\nTable 3. Error rates (%) on ImageNet validation.\n"),
        chunk(17, 17, RESNET_ROW),
    ]
    paper = {
        "model": Evidence("ResNet-50", "ResNet-50 22.85 6.71", 17),
        "value": Evidence("22.85", "ResNet-50 22.85 6.71", 17),
        "metric": Evidence("top-1 err.", "model top-1 err. top-5 err.", 17),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 error (ResNet-50, Table 3)")
    assert paper["dataset"].value == "ImageNet"
    assert paper["split"].value == "validation"
    assert paper["unit"].value == "%"


def test_two_named_tables_both_adjacent_stay_unknown():
    """If the request cannot be narrowed to one table, no caption is used."""
    chunks = [
        chunk(16, 16, "Table 3. Error rates (%) on ImageNet validation.\n"),
        chunk(17, 17, RESNET_ROW),
        chunk(18, 18, "Table 4. Error rates (%) on CIFAR-10 test set.\n"),
    ]
    paper = {
        "model": Evidence("ResNet-50", "ResNet-50 22.85 6.71", 17),
        "value": Evidence("22.85", "ResNet-50 22.85 6.71", 17),
        "metric": Evidence("top-1 err.", "model top-1 err. top-5 err.", 17),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 error (ResNet-50, Tables 3 and 4)")
    assert "dataset" not in paper
    assert "split" not in paper
    assert "unit" not in paper


def test_a_caption_above_the_row_decides_the_table_and_is_not_skipped():
    """A caption printed above the row fixes membership; a matching neighbour may not replace it."""
    chunks = [
        chunk(16, 16, "3.1. ImageNet\nTable 3. Error rates (%) on ImageNet validation.\n"),
        chunk(
            17, 17,
            "Table 9. Error rates (%) on CIFAR-10 test set.\n" + RESNET_ROW,
        ),
    ]
    paper = {
        "model": Evidence("ResNet-50", "ResNet-50 22.85 6.71", 17),
        "value": Evidence("22.85", "ResNet-50 22.85 6.71", 17),
        "metric": Evidence("top-1 err.", "model top-1 err. top-5 err.", 17),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 error (ResNet-50, Table 3)")
    # The row sits under Table 9, so Table 3 in the previous chunk is not its table.
    assert "dataset" not in paper
    assert "split" not in paper
    assert "unit" not in paper


def test_the_named_table_caption_after_a_cross_chunk_row_is_still_used():
    """Positive control: the caption of Table 3 in the next chunk describes this row."""
    chunks = [
        chunk(17, 17, RESNET_ROW),
        chunk(18, 18, "Table 3. Error rates (%) on ImageNet validation.\n"),
    ]
    paper = {
        "model": Evidence("ResNet-50", "ResNet-50 22.85 6.71", 17),
        "value": Evidence("22.85", "ResNet-50 22.85 6.71", 17),
        "metric": Evidence("top-1 err.", "model top-1 err. top-5 err.", 17),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 error (ResNet-50, Table 3)")
    assert paper["dataset"].value == "ImageNet"
    assert paper["split"].value == "validation"
    assert paper["unit"].value == "%"


def test_a_cross_reference_above_the_row_does_not_fix_the_table():
    """`as shown in Table 9.` is prose, not the caption of the row's table."""
    chunks = [
        chunk(16, 16, "3.1. ImageNet\nTable 3. Error rates (%) on ImageNet validation.\n"),
        chunk(
            17, 17,
            "These results are shown in Table 9.\n" + RESNET_ROW,
        ),
    ]
    paper = {
        "model": Evidence("ResNet-50", "ResNet-50 22.85 6.71", 17),
        "value": Evidence("22.85", "ResNet-50 22.85 6.71", 17),
        "metric": Evidence("top-1 err.", "model top-1 err. top-5 err.", 17),
    }
    _fill_explicit_conditions(paper, chunks, "top-1 error (ResNet-50, Table 3)")
    assert paper["dataset"].value == "ImageNet"
    assert paper["split"].value == "validation"


@pytest.mark.parametrize(
    ("paper", "run", "expected"),
    [
        pytest.param(
            "ImageNet-1K trained models", "ImageNet-1K only (no ImageNet-22K pretraining)",
            "aligned", id="both-1k-from-scratch",
        ),
        pytest.param(
            "ImageNet-1K trained models",
            "ImageNet-22K pretraining followed by ImageNet-1K fine-tuning",
            "mismatch", id="22k-pretraining-versus-1k-training",
        ),
        pytest.param(
            "ImageNet-22K pre-trained models", "ImageNet-1K only (no ImageNet-22K pretraining)",
            "mismatch", id="pretraining-only-on-one-side",
        ),
        pytest.param("ImageNet-1K trained models", None, "unknown", id="one-side-silent"),
    ],
)
def test_training_conditions_compare_pretraining_not_wording(paper, run, expected):
    evidence_paper = {"training": Evidence(paper, paper, 1)}
    evidence_run = {"training": Evidence(run, run, 2)} if run else {}
    assert {field.key: field.status for field in build_fields(evidence_paper, evidence_run)}[
        "training"
    ] == expected


def test_a_negated_pretraining_mention_is_not_pretraining():
    from app.domain.comparison import _pretraining_datasets

    assert _pretraining_datasets("ImageNet-1K only (no ImageNet-22K pretraining)") == set()
    assert _pretraining_datasets(
        "ImageNet-22K pretraining followed by ImageNet-1K fine-tuning",
    ) == {"imagenet-22k"}
    # `pre-trained models` must not be read as a dataset named "models".
    assert _pretraining_datasets("ImageNet-22K pre-trained models") == {"imagenet-22k"}
