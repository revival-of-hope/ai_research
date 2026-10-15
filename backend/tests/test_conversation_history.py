from sqlmodel import Session, SQLModel, create_engine

from app.core.crypto import encrypt_secret
from app.domain.research import ResearchCommand
from app.infrastructure.repo.research import SqlResearchRepository
from app.models.accounts import ApiProvider, User
from app.models.conversations import Conversation, Message


def test_recent_history_returns_last_six_messages_in_chat_order():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="history@example.com", password_hash="hash")
        session.add(user)
        session.flush()
        provider = ApiProvider(
            user_id=user.id,
            name="Custom",
            base_url="https://example.com/v1",
            model="actual-model",
            api_key_encrypted=encrypt_secret("unused"),
        )
        conversation = Conversation(user_id=user.id, title="History")
        session.add_all([conversation, provider])
        session.flush()
        for index in range(8):
            session.add(
                Message(
                    conversation_id=conversation.id,
                    role="user" if index % 2 == 0 else "assistant",
                    content=f"message-{index}",
                )
            )
        session.commit()
        prepared = SqlResearchRepository(session).start(
            user.id,
            ResearchCommand(
                "Follow-up question", provider_id=provider.id, conversation_id=conversation.id
            ),
        )
        assert [message.content for message in prepared.history] == [
            f"message-{i}" for i in range(2, 8)
        ]
    engine.dispose()
