"""Precise PDF page hints must be verified, unique and never guessed."""

from types import SimpleNamespace

from app.domain.comparison import Evidence, build_fields, field_status
from app.infrastructure.agents import comparison as evidence_extractor
from app.infrastructure.repo import comparison as repository


def test_training_and_pretraining_are_core_comparison_conditions():
    paper = Evidence("ImageNet-1K pretraining", "Training: ImageNet-1K pretraining", 1)
    same = Evidence("ImageNet-1K pretraining", "Training: ImageNet-1K pretraining", 2)
    different = Evidence(
        "ImageNet-22K pretraining",
        "Training: ImageNet-22K pretraining",
        3,
    )
    less_detailed = Evidence(
        "ImageNet-22K pre-trained models",
        "ImageNet-22K pre-trained models",
        4,
    )
    detailed = Evidence(
        "ImageNet-22K pretraining followed by ImageNet-1K fine-tuning",
        "Training: ImageNet-22K pretraining followed by ImageNet-1K fine-tuning",
        5,
    )
    assert build_fields({"training": paper}, {"training": same})[4].status == "aligned"
    assert build_fields({"training": paper}, {"training": different})[4].status == "mismatch"
    assert build_fields({"training": less_detailed}, {"training": detailed})[4].status == "unknown"
    assert build_fields({"training": paper}, {})[4].status == "unknown"
    assert len(build_fields({}, {})) == 10


def test_pdf_page_hint_requires_a_unique_literal_page_match(monkeypatch):
    pages = [
        "An introduction without the measurement.",
        "Table 3  ResNet-50\n top-1 error 22.85%\nvalidation split",
        "Other experiment: 24.10%",
    ]
    monkeypatch.setattr(
        repository, "PdfReader",
        lambda _: SimpleNamespace(
            pages=[SimpleNamespace(extract_text=lambda text=text: text) for text in pages],
        ),
    )
    assert repository._verified_pdf_page(
        "paper.pdf", "ResNet-50\n top-1 error 22.85%",
    ) == 2
    assert repository._verified_pdf_page("paper.md", "ResNet-50") is None
    assert repository._verified_pdf_page("paper.pdf", "unreported fact") is None
    pages[0] = "ResNet-50\n top-1 error 22.85%"
    assert repository._verified_pdf_page(
        "paper.pdf", "ResNet-50\n top-1 error 22.85%",
    ) is None


def test_pdf_read_failure_does_not_invent_page(monkeypatch):
    def unreadable(_):
        raise OSError("unavailable")

    monkeypatch.setattr(repository, "PdfReader", unreadable)
    assert repository._verified_pdf_page("paper.pdf", "ResNet-50") is None


def test_pdf_line_wrap_hyphenation_and_ligatures_are_normalized_for_evidence(monkeypatch):
    paper = Evidence("validation", "valida- tion set", 1)
    run = Evidence("validation", "validation set", 2)
    assert field_status(paper, run, "split") == "aligned"

    pages = ["Classi\ufb01cation accuracy on the valida- tion set."]

    class PdfPage:
        def extract_text(self):
            return pages[0]

    monkeypatch.setattr(
        repository, "PdfReader", lambda _: SimpleNamespace(pages=[PdfPage()]),
    )
    assert repository._verified_pdf_page(
        "paper.pdf", "Classification accuracy on the validation set.",
    ) == 1


def test_candidate_rank_includes_training_and_validation_context():
    decoys = [
        SimpleNamespace(
            id=index + 1,
            ordinal=index,
            content="Dataset reference data split model metric result experiment.",
        )
        for index in range(12)
    ]
    relevant = [
        SimpleNamespace(
            id=100,
            ordinal=12,
            content="ConvNeXt-T Table 1 top-1 accuracy, ImageNet-1K result.",
        ),
        SimpleNamespace(
            id=101,
            ordinal=13,
            content=(
                "ConvNeXt-T pre-training on ImageNet-22K then fine-tuning on ImageNet-1K."
            ),
        ),
        SimpleNamespace(
            id=102,
            ordinal=14,
            content="ConvNeXt-T ImageNet-1K top-1 accuracy on the validation set.",
        ),
    ]

    class Results:
        def all(self):
            return decoys + relevant

    class Session:
        def exec(self, _statement):
            return Results()

    candidate = repository.SqlComparisonRepository(Session())._candidate(
        SimpleNamespace(id=1, filename="paper.pdf"),
        "top-1 accuracy (ConvNeXt-T, Table 1, ImageNet-1K, 224x224; check 22K pretraining)",
    )

    selected = {chunk["id"] for chunk in candidate["chunks"]}
    assert {100, 101, 102} <= selected


def test_explicit_pretraining_heading_and_split_fill_around_the_cited_row():
    row = "ConvNeXt-T 2242 29M 4.5G 774.7 82.1"
    fields = {"value": Evidence("82.1", row, 17)}
    chunks = [
        {
            "id": 16, "ordinal": 16,
            "content": (
                "Table 1. Classification accuracy on ImageNet-1K. We report top-1 "
                "accuracy on the valida-\ntion set."
            ),
        },
        {"id": 17, "ordinal": 17, "content": "IN-1K top-1 acc.\n" + row},
        {"id": 18, "ordinal": 18, "content": "ImageNet-22K pre-trained models"},
    ]

    evidence_extractor._fill_explicit_conditions(
        fields,
        chunks,
        "top-1 accuracy (ConvNeXt-T, Table 1, ImageNet-22K pre-trained row, "
        "evaluated on ImageNet-1K at 224x224)",
    )

    assert fields["split"].value == "validation"
    assert fields["training"] == Evidence(
        "ImageNet-22K pre-trained models", "ImageNet-22K pre-trained models", 18,
    )
    # The column header of the cited row wins over the wider abbreviation.
    assert fields["metric"].value == "top-1 acc"


def test_dataset_is_never_inferred_from_nearby_prose():
    """A cited row is not permission to read every other section of the paper."""
    metric = "top-1 error (ResNet-50, Table 3, 10-crop ImageNet validation)"
    coco = {
        "id": 10, "ordinal": 10,
        "content": "We also evaluate our detector on COCO, evaluated on COCO test-dev.",
    }
    row = {
        "id": 11, "ordinal": 11,
        "content": "model top-1 err. top-5 err.\nResNet-50 22.85 6.71\n",
    }

    fields = {"value": Evidence("22.85", "ResNet-50 22.85 6.71", 11)}
    evidence_extractor._fill_explicit_conditions(fields, [coco, row], metric)
    assert "dataset" not in fields

    caption = {
        "id": 12, "ordinal": 12,
        "content": "Table 3. Error rates (%) on ImageNet validation.",
    }
    fields = {"value": Evidence("22.85", "ResNet-50 22.85 6.71", 11)}
    evidence_extractor._fill_explicit_conditions(fields, [coco, row, caption], metric)
    assert fields["dataset"] == Evidence(
        "ImageNet", "Table 3. Error rates (%) on ImageNet", 12,
    )


def test_run_summary_dataset_comes_from_its_own_label_line():
    chunks = [{"id": 20, "ordinal": 0, "content": "Dataset: COCO\nModel: ResNet-50\n"}]
    fields = {}
    evidence_extractor._fill_explicit_conditions(fields, chunks, "top-1 error", side="run")
    assert fields["dataset"] == Evidence("COCO", "Dataset: COCO", 20)


def test_in1k_top1_accuracy_abbreviation_is_comparable():
    paper = Evidence("IN-1K top-1 acc.", "IN-1K top-1 acc.", 1)
    run = Evidence("top-1 accuracy", "top-1 accuracy", 2)
    assert field_status(paper, run, "metric") == "aligned"
