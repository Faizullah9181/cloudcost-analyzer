"""SQLAlchemy ORM models for sessions, message history and user profiles."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def new_id() -> str:
    """Generate a UUID4 primary key."""
    return str(uuid4())


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class ChatSession(Base):
    """A persistent analysis session (CLI or web)."""

    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=new_id)
    name = Column(String(255), nullable=False)
    user_id = Column(String(255), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Cloud configuration: {"aws": True, "azure": False, ...}
    cloud_providers = Column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    # Non-secret connection context per provider: {"aws": {"account_id": "...", "region": "..."}}
    connection_context = Column(MutableDict.as_mutable(JSON), default=dict, nullable=False)

    # LLM configuration
    llm_provider = Column(String(50), default="bedrock", nullable=False)
    llm_model = Column(String(255), default="", nullable=False)

    # State
    is_active = Column(Boolean, default=True, nullable=False)
    message_count = Column(Integer, default=0, nullable=False)
    context_tokens = Column(Integer, default=0, nullable=False)
    compression_count = Column(Integer, default=0, nullable=False)

    # Latest structured analysis (cache for the UI)
    analysis_results = Column(MutableDict.as_mutable(JSON), default=dict, nullable=False)

    tags = Column(MutableList.as_mutable(JSON), default=list, nullable=False)
    custom_metadata = Column("metadata", MutableDict.as_mutable(JSON), default=dict, nullable=False)

    messages = relationship(
        "SessionMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionMessage.seq",
        lazy="selectin",
    )

    # ----- helpers -------------------------------------------------------

    def enabled_providers(self) -> list[str]:
        """Cloud providers enabled for this session, in a stable order."""
        providers = self.cloud_providers or {}
        return [name for name, enabled in providers.items() if enabled]

    def add_message(
        self,
        role: str,
        content: str,
        *,
        tokens_used: int = 0,
        provider: str | None = None,
        tags: list[str] | None = None,
        analysis: dict[str, Any] | None = None,
        is_summary: bool = False,
    ) -> "SessionMessage":
        """Append a message row and bump the counters (caller commits)."""
        self.message_count = (self.message_count or 0) + 1
        self.context_tokens = (self.context_tokens or 0) + int(tokens_used or 0)
        message = SessionMessage(
            session_id=self.id,
            seq=self.message_count,
            role=role,
            content=content,
            tokens_used=int(tokens_used or 0),
            provider=provider,
            tags=list(tags or []),
            analysis=analysis,
            is_summary=is_summary,
        )
        self.messages.append(message)
        self.updated_at = utcnow()
        return message

    def update_analysis(self, analysis: dict[str, Any]) -> None:
        """Replace the cached analysis result."""
        self.analysis_results = dict(analysis or {})
        self.updated_at = utcnow()

    def get_last_analysis(self) -> dict[str, Any]:
        """Return the cached analysis result."""
        return dict(self.analysis_results or {})

    def to_dict(self) -> dict[str, Any]:
        """Summary representation used by the API and CLI."""
        return {
            "id": self.id,
            "name": self.name,
            "user_id": self.user_id,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
            "cloud_providers": dict(self.cloud_providers or {}),
            "connection_context": dict(self.connection_context or {}),
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model or "",
            "is_active": bool(self.is_active),
            "message_count": int(self.message_count or 0),
            "context_tokens": int(self.context_tokens or 0),
            "compression_count": int(self.compression_count or 0),
            "tags": list(self.tags or []),
        }

    def to_export(self) -> dict[str, Any]:
        """Full representation including message history."""
        data = self.to_dict()
        data["messages"] = [message.to_dict() for message in self.messages]
        data["analysis_results"] = dict(self.analysis_results or {})
        data["metadata"] = dict(self.custom_metadata or {})
        return data

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<ChatSession id={self.id} name={self.name!r} messages={self.message_count}>"


class SessionMessage(Base):
    """One conversation turn. This table is the source of truth for history."""

    __tablename__ = "session_messages"

    id = Column(String(36), primary_key=True, default=new_id)
    session_id = Column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq = Column(Integer, nullable=False, default=0)
    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    provider = Column(String(50), nullable=True)
    tags = Column(MutableList.as_mutable(JSON), default=list, nullable=False)
    analysis = Column(JSON, nullable=True)
    is_summary = Column(Boolean, default=False, nullable=False)

    session = relationship("ChatSession", back_populates="messages")

    def to_dict(self) -> dict[str, Any]:
        """Serialisable representation."""
        return {
            "id": self.id,
            "seq": self.seq,
            "role": self.role,
            "content": self.content,
            "timestamp": _iso(self.created_at),
            "tokens_used": int(self.tokens_used or 0),
            "provider": self.provider,
            "tags": list(self.tags or []),
            "analysis": self.analysis,
            "is_summary": bool(self.is_summary),
        }


class UserProfile(Base):
    """Cross-session user model persisted for the deep-memory layer."""

    __tablename__ = "user_profiles"

    user_id = Column(String(255), primary_key=True)
    data = Column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
