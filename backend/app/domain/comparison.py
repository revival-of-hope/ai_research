"""Domain rules for paper/result comparison and researcher review."""

import re
import unicodedata
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

FieldKey = Literal[
    "dataset", "version", "split", "model", "training", "preprocessing",
    "seed", "metric", "unit", "value",
]
FieldStatus = Literal["aligned", "mismatch", "unknown"]
ReviewStatus = Literal["pending", "confirmed", "unresolved"]

FIELD_LABELS: dict[str, str] = {
    "dataset": "数据集",
    "version": "数据集版本",
    "split": "数据划分",
    "model": "模型或方法",
    "training": "训练与预训练条件",
    "preprocessing": "预处理",
    "seed": "随机种子",
    "metric": "指标名称",
    "unit": "指标单位或定义",
    "value": "指标数值",
}


class ComparisonNotFound(Exception):
    pass


class ComparisonConflict(Exception):
    pass


class ComparisonTimeout(Exception):
    pass


class EvidenceExtractionError(Exception):
    """A safe, user-facing failure of the external evidence extraction."""


@dataclass
class Evidence:
    value: str | None = None
    excerpt: str | None = None
    chunk_id: int | None = None


@dataclass
class ComparedField:
    key: str
    label: str
    paper: Evidence
    run: Evidence
    status: FieldStatus
    review_status: ReviewStatus = "pending"
    note: str = ""


def normalize_source_text(value: str | None) -> str:
    """Normalize PDF ligatures and line-wrap hyphenation for literal evidence checks."""
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
    return " ".join(text.split())


def _normalized(value: str | None) -> str:
    return normalize_source_text(value)


_SPLIT_CANONICAL: tuple[tuple[str, str], ...] = (
    ("test-dev", "test-dev"),
    ("validation", "validation"),
    ("val", "validation"),
    ("testing", "test"),
    ("test", "test"),
    ("training", "training"),
    ("train", "training"),
)
_SPLIT_ALTERNATION = "|".join(pattern for pattern, _ in _SPLIT_CANONICAL)
_CROP_ALTERNATION = r"(?:\d+|single|multi|center|centre|ten)\s*[- ]?\s*(?:crops?|patch(?:es)?)"


def _normalized_split(value: str | None) -> str:
    """Reduce a split description such as '50k validation images' to its partition."""
    text = _normalized(value)
    for pattern, canonical in _SPLIT_CANONICAL:
        if re.search(rf"\b{re.escape(pattern)}\b", text):
            return canonical
    return text


def _normalized_dataset(value: str | None) -> str:
    """Separate an evaluation dataset name from the split words that follow it."""
    text = _normalized(value)
    text = re.sub(r"^(?:the|a|an)\s+", "", text)
    text = re.sub(
        rf"\s*\(?(?:{_SPLIT_ALTERNATION})\b(?:\s+(?:set|split|partition|images|subset))?\)?\s*$",
        "",
        text,
    )
    text = re.sub(r"\s+(?:dataset|set|images|split)$", "", text)
    return text.strip(" ,;:()")


def _resolution(value: str) -> str | None:
    """Normalize '224 x 224', '224× 224' and the flattened '2242' form to one token."""
    text = _normalized(value).strip()
    match = re.search(r"\b(\d{2,4})\s*[x×*]\s*(\d{2,4})\b", text)
    if match:
        return f"{int(match.group(1))}x{int(match.group(2))}"
    match = re.fullmatch(r"(\d{2,4})\s?2", text)
    if match and 96 <= int(match.group(1)) <= 1024:
        return f"{int(match.group(1))}x{int(match.group(1))}"
    return None


def _crop_mode(text: str) -> str | None:
    match = re.search(rf"\b({_CROP_ALTERNATION})\b", text)
    if not match:
        return None
    token = re.sub(r"\s*[- ]\s*", "-", match.group(1))
    number = re.match(r"(\d+|ten)-(?:crops?|patch(?:es)?)", token)
    if number:
        count = "10" if number.group(1) == "ten" else number.group(1)
        return f"{count}-crop"
    name = token.split("-")[0]
    return "center-crop" if name.startswith("cent") else f"{name}-crop"


def _preprocessing_signature(value: str | None) -> tuple[str | None, str | None]:
    text = _normalized(value)
    return _crop_mode(text), _resolution(text)


def _preprocessing_status(left: str, right: str) -> FieldStatus:
    """Compare evaluation protocol attributes instead of raw wording.

    Both sides must describe the same set of attributes; a missing crop mode or
    input size on one side leaves the condition unconfirmed.
    """
    left_signature = _preprocessing_signature(left)
    right_signature = _preprocessing_signature(right)
    left_crop, left_resolution = left_signature
    right_crop, right_resolution = right_signature
    if left_crop and right_crop and left_crop != right_crop:
        return "mismatch"
    if left_resolution and right_resolution and left_resolution != right_resolution:
        return "mismatch"
    if any(left_signature) or any(right_signature):
        return "aligned" if left_signature == right_signature else "unknown"
    return "aligned" if _normalized(left) == _normalized(right) else "mismatch"


def _unit_token(value: str | None) -> str | None:
    """Return the measurement unit itself, ignoring evaluation conventions."""
    text = _normalized(value)
    if "%" in text or re.search(r"\bpercent(?:age)?s?\b", text):
        return "percent"
    return None


def _appears_in_excerpt(value: str, excerpt: str) -> bool:
    normalized = _normalized(value)
    source = _normalized(excerpt)
    if normalized == "%":
        return "%" in source
    return re.search(
        rf"(?<![\w.+-]){re.escape(normalized)}(?![\w+-]|\.\d)", source,
    ) is not None


def _normalized_metric(value: str | None) -> str:
    """Normalize metric spellings that name the same measured quantity."""
    text = _normalized(value)
    text = re.sub(r"\bacc\b\.?|\bacc\.", "accuracy", text)
    text = re.sub(r"\berr\b\.?|\berr\.", "error", text)
    text = re.sub(r"\btop[- ]?(\d)\b", r"top-\1", text)
    text = re.sub(r"^(?:(?:in-1k|in1k|imagenet(?:-?1k|-?22k)?)\s+)+", "", text)
    text = re.sub(r"\s*/\s*", "/", text)
    return text.strip(" .,;:")


def _metric_top_n(text: str) -> int | None:
    match = re.search(r"\btop-(\d)\b", text)
    return int(match.group(1)) if match else None


def _metric_kind(text: str) -> str | None:
    if "accuracy" in text:
        return "accuracy"
    if "error" in text:
        return "error"
    return None


def _metric_term(value: str | None, context: str | None = None) -> str:
    """Resolve a bare 'Top 1' header label only when the source defines it."""
    text = _normalized_metric(value)
    if re.fullmatch(r"top-\d", text) and context:
        kind = _metric_kind(_normalized(context))
        if kind:
            text = f"{text} {kind}"
    return text


def _metric_status(paper: str, run: str) -> FieldStatus:
    if paper == run:
        return "aligned"
    paper_top, run_top = _metric_top_n(paper), _metric_top_n(run)
    if paper_top is not None and run_top is not None and paper_top != run_top:
        return "mismatch"
    if (paper_top is None) != (run_top is None):
        # One side names a top-N cut-off and the other does not: not comparable.
        return "unknown"
    if not _metric_kind(paper) or not _metric_kind(run):
        return "unknown"
    return "mismatch"


def _comparison_value(key: str | None, value: str | None) -> str:
    if key == "unit":
        return _unit_token(value) or _normalized(value)
    if key == "value":
        return _normalized_value(value)
    if key == "metric":
        return _normalized_metric(value)
    if key == "dataset":
        return _normalized_dataset(value)
    if key == "split":
        return _normalized_split(value)
    return _normalized(value)


def _normalized_value(value: str | None) -> str:
    normalized = _normalized(value)
    # A trailing note such as "81.3% (invented value)" does not change the number.
    normalized = re.sub(r"\s*\([^()]*\)\s*$", "", normalized).strip()
    match = re.fullmatch(
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)\s*(?:%|percent(?:age)?)?",
        normalized,
    )
    if match:
        try:
            number = Decimal(match.group(1))
        except InvalidOperation:
            return normalized
        if number.is_finite():
            return format(number.normalize(), "f")
    return normalized


_TRAINING_TOKEN = r"[a-z][a-z0-9]*(?:[-/][a-z0-9]+)*"


def _pretraining_datasets(value: str | None) -> set[str]:
    """Datasets named as pretraining sources, ignoring a negated mention."""
    text = _normalized(value)
    patterns = (
        rf"\b(?P<dataset>{_TRAINING_TOKEN})\s+pre[- ]?train(?:ed|ing)?\b",
        rf"\bpre[- ]?train(?:ed|ing)?\s+(?:on\s+)?(?P<dataset>{_TRAINING_TOKEN})\b",
    )
    found = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            # `no ImageNet-22K pretraining` states the absence of that condition.
            prefix = text[max(0, match.start() - 32): match.start()]
            if _NEGATED_PRETRAINING.search(prefix):
                continue
            if match.group("dataset") in _PRETRAIN_STOPWORDS:
                continue
            found.add(match.group("dataset"))
    return found


_NEGATED_PRETRAINING = re.compile(
    r"\b(?:no|without|not)\s+(?:[a-z0-9-]+\s+){0,2}$", re.IGNORECASE,
)
# Words that the pattern above can capture around `pre-trained <x>` without naming a dataset.
_PRETRAIN_STOPWORDS = frozenset({
    "model", "models", "network", "networks", "weights", "checkpoint", "checkpoints",
    "followed", "then", "and", "or", "on", "by", "with", "for", "from", "using",
    "the", "a", "an", "is", "are", "was", "were", "image", "images", "dataset",
    "data", "training", "fine", "tuning", "initialization", "scratch", "pre",
})

# `ImageNet-1K trained models` / `ImageNet-1K only` / `trained on ImageNet-1K`.
_TRAINED_DATASET = (
    re.compile(rf"\b(?P<dataset>{_TRAINING_TOKEN})\s+trained\b"),
    re.compile(rf"\b(?P<dataset>{_TRAINING_TOKEN})\s+only\b"),
    re.compile(rf"\btrained\s+on\s+(?P<dataset>{_TRAINING_TOKEN})\b"),
)


def _trained_dataset(value: str | None) -> str | None:
    """The dataset a side says the model was trained on, when it says so plainly."""
    text = _normalized(value)
    for pattern in _TRAINED_DATASET:
        match = pattern.search(text)
        if match:
            return match.group("dataset")
    return None


def _training_status(paper_value: str | None, run_value: str | None) -> FieldStatus:
    paper = _normalized(paper_value)
    run = _normalized(run_value)
    paper_pretraining = _pretraining_datasets(paper)
    run_pretraining = _pretraining_datasets(run)
    paper_trained = _trained_dataset(paper)
    run_trained = _trained_dataset(run)
    no_pretraining = re.compile(
        r"\b(?:no|without|not)\s+(?:any\s+)?[a-z0-9-]*\s*pre[- ]?train", re.IGNORECASE,
    )

    if paper_pretraining and run_pretraining and paper_pretraining.isdisjoint(run_pretraining):
        return "mismatch"
    if paper_pretraining and no_pretraining.search(run):
        return "mismatch"
    if run_pretraining and no_pretraining.search(paper):
        return "mismatch"
    # One side states plain training on a dataset while the other reports pretraining:
    # that is the ImageNet-1K-from-scratch versus ImageNet-22K comparison.
    if run_pretraining and paper_trained and not paper_pretraining:
        return "mismatch"
    if paper_pretraining and run_trained and not run_pretraining:
        return "mismatch"
    if (
        paper_trained
        and run_trained
        and paper_trained == run_trained
        and not paper_pretraining
        and not run_pretraining
    ):
        return "aligned"
    return "unknown"


def field_status(paper: Evidence, run: Evidence, key: str | None = None) -> FieldStatus:
    """An explicit value and exact source excerpt are required on both sides."""
    for side in (paper, run):
        if (
            not side.value
            or not side.excerpt
            or side.chunk_id is None
            or not _appears_in_excerpt(side.value, side.excerpt)
        ):
            return "unknown"
    paper_value = _comparison_value(key, paper.value)
    run_value = _comparison_value(key, run.value)
    if key == "unit":
        paper_unit, run_unit = _unit_token(paper.value), _unit_token(run.value)
        if paper_unit and run_unit:
            return "aligned" if paper_unit == run_unit else "mismatch"
        if paper_unit or run_unit:
            # One side states a measurement unit and the other only a convention
            # or a metric name; that is not evidence of a conflicting unit.
            return "unknown"
        return "aligned" if _normalized(paper.value) == _normalized(run.value) else "mismatch"
    if key == "dataset" and (not paper_value or not run_value):
        return "unknown"
    if key == "preprocessing":
        return _preprocessing_status(paper.value, run.value)
    if paper_value == run_value:
        return "aligned"
    if key == "training":
        return _training_status(paper.value, run.value)
    return "mismatch"


def _side_metric_context(fields: dict[str, Evidence]) -> str:
    """Excerpts of one side that may define an ambiguous metric column label."""
    return " ".join(
        evidence.excerpt or ""
        for key in ("metric", "unit", "value", "model")
        if (evidence := fields.get(key))
    )


def _metric_field_status(paper: dict[str, Evidence], run: dict[str, Evidence]) -> FieldStatus:
    """Metric status, resolving a bare 'Top 1' header against its own side's definition."""
    if field_status(
        paper.get("metric", Evidence()), run.get("metric", Evidence()), "metric",
    ) == "unknown":
        return "unknown"
    return _metric_status(
        _metric_term(paper.get("metric", Evidence()).value, _side_metric_context(paper)),
        _metric_term(run.get("metric", Evidence()).value, _side_metric_context(run)),
    )


def reconcile_fields(fields: list[ComparedField]) -> list[ComparedField]:
    """Recompute the fields that depend on another field's verdict.

    Numbers are only comparable behind the same measured quantity: unless the metric
    itself is confirmed aligned, the value stays unknown. Both the extraction and the
    review path go through here, so a saved edit cannot bypass the rule.
    """
    paper = {field.key: field.paper for field in fields}
    run = {field.key: field.run for field in fields}
    metric_status = _metric_field_status(paper, run)
    for field in fields:
        if field.key == "metric":
            field.status = metric_status
        elif field.key == "value":
            field.status = (
                field_status(field.paper, field.run, "value")
                if metric_status == "aligned"
                else "unknown"
            )
    return fields


def build_fields(paper: dict[str, Evidence], run: dict[str, Evidence]) -> list[ComparedField]:
    return reconcile_fields([
        ComparedField(
            key=key, label=label,
            paper=paper.get(key, Evidence()),
            run=run.get(key, Evidence()),
            status=field_status(paper.get(key, Evidence()), run.get(key, Evidence()), key),
        )
        for key, label in FIELD_LABELS.items()
    ])


def update_field(
    item: ComparedField, paper_value: str | None, run_value: str | None,
    review_status: ReviewStatus, note: str, *,
    paper_evidence: Evidence | None = None,
    run_evidence: Evidence | None = None,
) -> ComparedField:
    if review_status not in {"confirmed", "unresolved"}:
        raise ValueError("请选择确认或标记未解决")
    if len(note) > 1000:
        raise ValueError("复核备注不能超过 1000 字")
    paper = Evidence(paper_value.strip() or None if paper_value is not None else None,
                     paper_evidence.excerpt if paper_evidence is not None else item.paper.excerpt,
                     paper_evidence.chunk_id if paper_evidence is not None else item.paper.chunk_id)
    run = Evidence(run_value.strip() or None if run_value is not None else None,
                   run_evidence.excerpt if run_evidence is not None else item.run.excerpt,
                   run_evidence.chunk_id if run_evidence is not None else item.run.chunk_id)
    return ComparedField(
        key=item.key, label=item.label, paper=paper, run=run,
        status=field_status(paper, run, item.key), review_status=review_status, note=note,
    )


def read_fields(rows: list[dict]) -> list[ComparedField]:
    return [
        ComparedField(
            key=row["key"], label=row["label"],
            paper=Evidence(**row["paper"]), run=Evidence(**row["run"]),
            status=row["status"], review_status=row["review_status"], note=row["note"],
        )
        for row in rows
    ]


def field_dicts(fields: list[ComparedField]) -> list[dict]:
    return [asdict(item) for item in fields]


def confirm_fields(fields: list[ComparedField]) -> None:
    if any(item.review_status == "pending" for item in fields):
        raise ComparisonConflict("还有内容尚未检查，请逐项确认或标记为未解决后再保存")
