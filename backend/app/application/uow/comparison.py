"""Explicit transaction boundary for evidence comparison."""

from types import TracebackType
from typing import Protocol, Self

from app.application.repo.comparison import ComparisonRepository


class ComparisonUnitOfWork(Protocol):
    comparisons: ComparisonRepository

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
