"""UC08 application use cases: candidate extraction, review and confirmation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.application.uow.comparison import ComparisonUnitOfWork
from app.domain.comparison import (
    FIELD_LABELS,
    ComparisonConflict,
    ComparisonTimeout,
    Evidence,
    EvidenceExtractionError,
    build_fields,
    confirm_fields,
    field_dicts,
    normalize_source_text,
    read_fields,
    reconcile_fields,
    update_field,
)
from app.domain.research import ProviderConfig

Extractor = Callable[[ProviderConfig, dict, str], Awaitable[dict[str, Evidence]]]
COMPARISON_EXTRACTION_TIMEOUT_SECONDS = 120


async def _extract_pair(
    extractor: Extractor, provider: ProviderConfig,
    paper: dict, run: dict, metric: str,
) -> tuple[dict[str, Evidence], dict[str, Evidence]]:
    async def extract_side(label: str, source: dict) -> dict[str, Evidence]:
        try:
            return await extractor(provider, source, metric)
        except Exception as error:
            # Preserve cancellation; distinguish a failed paper from a failed run.
            if isinstance(error, EvidenceExtractionError):
                raise EvidenceExtractionError(f"{label}读取失败：{error}") from None
            raise

    tasks = (
        asyncio.create_task(extract_side("论文", paper)),
        asyncio.create_task(extract_side("运行摘要", run)),
    )
    try:
        paper_fields, run_fields = await asyncio.gather(*tasks)
        return paper_fields, run_fields
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


def _verified_fields(source: dict, values: dict[str, Evidence]) -> dict[str, Evidence]:
    chunks = {chunk["id"]: chunk["content"] for chunk in source["chunks"]}
    return {
        key: evidence
        for key, evidence in values.items()
        if key in FIELD_LABELS
        and evidence.chunk_id in chunks
        and evidence.value
        and evidence.excerpt
        and normalize_source_text(evidence.excerpt)
        in normalize_source_text(chunks[evidence.chunk_id])
    }


class ComparisonService:
    def __init__(
        self, uow_factory: Callable[[], ComparisonUnitOfWork], extractor: Extractor,
    ):
        self._uow = uow_factory
        self._extractor = extractor

    def list(self, user_id: int) -> list[dict]:
        with self._uow() as uow:
            return uow.comparisons.list(user_id)

    def get(self, user_id: int, comparison_id: int) -> dict:
        with self._uow() as uow:
            return uow.comparisons.get(user_id, comparison_id)

    def evidence(self, user_id: int, comparison_id: int, side: str, key: str) -> dict:
        with self._uow() as uow:
            return uow.comparisons.evidence(user_id, comparison_id, side, key)

    def source_chunks(
        self, user_id: int, comparison_id: int, side: str, query: str | None,
    ) -> list[dict]:
        with self._uow() as uow:
            return uow.comparisons.source_chunks(user_id, comparison_id, side, query)

    async def create(
        self, user_id: int, paper_id: int, run_id: int, provider_id: int, metric: str,
    ) -> dict:
        metric = metric.strip()
        if not metric or len(metric) > 120:
            raise ValueError("目标指标应包含 1 至 120 个字符")
        with self._uow() as uow:
            provider, paper, run = uow.comparisons.prepare(
                user_id, paper_id, run_id, provider_id, metric,
            )
        try:
            async with asyncio.timeout(COMPARISON_EXTRACTION_TIMEOUT_SECONDS):
                paper_fields, run_fields = await _extract_pair(
                    self._extractor, provider, paper, run, metric,
                )
        except TimeoutError:
            raise ComparisonTimeout(
                "整理两份资料已超过 120 秒，请缩小资料范围后重试。"
            ) from None
        fields = field_dicts(build_fields(
            _verified_fields(paper, paper_fields), _verified_fields(run, run_fields),
        ))
        with self._uow() as uow:
            # Ownership and ready state may have changed during an upstream request.
            uow.comparisons.prepare(user_id, paper_id, run_id, provider_id, metric)
            record = uow.comparisons.create(user_id, paper, run, provider_id, metric, fields)
            uow.commit()
            return record

    def update(
        self, user_id: int, comparison_id: int, updates: list[dict], confirm: bool,
    ) -> dict:
        if not updates and not confirm:
            raise ValueError("没有提交复核操作")
        keys = [item["key"] for item in updates]
        if len(keys) != len(set(keys)):
            raise ValueError("同一项内容不能重复提交")
        with self._uow() as uow:
            record = uow.comparisons.get_for_update(user_id, comparison_id)
            if record["status"] == "confirmed":
                raise ComparisonConflict("已确认的核验记录不可再修改")
            fields = read_fields(record["fields"])
            by_key = {item.key: index for index, item in enumerate(fields)}
            for item in updates:
                if item["key"] not in by_key:
                    raise ValueError("要修改的内容不存在")
                index = by_key[item["key"]]
                current = fields[index]

                def reviewed_evidence(
                    side: str, source: dict | None, previous: Evidence,
                ) -> Evidence | None:
                    if source is None:
                        return None
                    excerpt = source.get("excerpt")
                    chunk_id = source.get("chunk_id")
                    if (excerpt is None) != (chunk_id is None):
                        raise ValueError("原文摘录和文本片段必须同时提供")
                    if excerpt is None:
                        return Evidence(value=None, excerpt=None, chunk_id=None)
                    excerpt = excerpt.strip()
                    if not excerpt:
                        raise ValueError("原文摘录不能为空")
                    if excerpt != previous.excerpt or chunk_id != previous.chunk_id:
                        uow.comparisons.validate_source_reference(
                            user_id, comparison_id, side, chunk_id, excerpt,
                        )
                    return Evidence(value=None, excerpt=excerpt, chunk_id=chunk_id)

                fields[index] = update_field(
                    fields[index], item["paper_value"], item["run_value"],
                    item["review_status"], item.get("note", ""),
                    paper_evidence=reviewed_evidence(
                        "paper", item.get("paper_source"), current.paper,
                    ),
                    run_evidence=reviewed_evidence(
                        "run", item.get("run_source"), current.run,
                    ),
                )
            if confirm:
                confirm_fields(fields)
            # A reviewed value must obey the same metric/value dependency as extraction.
            fields = reconcile_fields(fields)
            record = uow.comparisons.update(
                user_id, comparison_id, field_dicts(fields),
                "confirmed" if confirm else "pending",
            )
            uow.commit()
            return record
