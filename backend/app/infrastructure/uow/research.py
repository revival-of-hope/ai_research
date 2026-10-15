from types import TracebackType
from typing import Self

from sqlmodel import Session

from app.infrastructure.repo.research import SqlResearchRepository


class SqlResearchUnitOfWork:
    """An explicit transaction; close only sessions this UoW owns."""

    def __init__(self, session: Session, *, owns_session: bool = False):
        self.session = session
        self.owns_session = owns_session
        self.research = SqlResearchRepository(session)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.rollback()
        finally:
            if self.owns_session:
                self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
