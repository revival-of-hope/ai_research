from sqlmodel import Session

from app.infrastructure.repo.accounts import SqlAccountRepo
from app.infrastructure.repo.documents import SqlDocumentRepo


class SqlWorkspaceUow:
    """Borrow a request session; every uncommitted exit rolls back."""

    def __init__(self, session: Session):
        self.session = session
        self.accounts = SqlAccountRepo(session)
        self.documents = SqlDocumentRepo(session)
        self._committed = False

    def __enter__(self):
        self._committed = False
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None or not self._committed:
            self.rollback()

    def commit(self):
        self.session.commit()
        self._committed = True

    def rollback(self):
        self.session.rollback()
