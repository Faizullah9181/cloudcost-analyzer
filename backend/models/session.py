"""Session database models."""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, JSON, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator

try:
    from backend.database import Base
except ImportError:
    from database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type that uses CHAR(32) on SQLite and UUID on PostgreSQL."""

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(String(32))


class Session(Base):
    """Cloud Analytics session model."""

    __tablename__ = "sessions"

    # Primary key
    id = Column(GUID, primary_key=True, default=lambda: str(uuid4()))

    # Metadata
    name = Column(String(255), nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Cloud configuration
    cloud_providers = Column(
        JSON, default=lambda: {"aws": True}, nullable=False
    )  # {"aws": True, "azure": True, "gcp": False, "digitalocean": False}
    credentials = Column(
        JSON, default=lambda: {}, nullable=False
    )  # Encrypted credentials per provider

    # LLM configuration
    llm_provider = Column(String(50), default="bedrock", nullable=False)
    llm_model = Column(String(255), default="", nullable=False)

    # Session state
    is_active = Column(Boolean, default=True, nullable=False)
    message_count = Column(Integer, default=0, nullable=False)
    context_tokens = Column(Integer, default=0, nullable=False)

    # Conversation & results
    messages = Column(
        JSON, default=lambda: [], nullable=False
    )  # [{"role": "user"/"assistant", "content": "...", "timestamp": "..."}]
    analysis_results = Column(
        JSON, default=lambda: {}, nullable=False
    )  # Latest analysis cache

    # Metadata
    tags = Column(
        JSON, default=lambda: [], nullable=False
    )  # ["production", "cost-optimization"]
    custom_metadata = Column(
        "metadata", JSON, default=lambda: {}, nullable=False
    )  # Custom metadata

    def add_message(self, role: str, content: str):
        """Add message to session."""
        self.messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.message_count += 1

    def get_last_analysis(self) -> dict:
        """Get last analysis result."""
        return self.analysis_results

    def update_analysis(self, analysis: dict):
        """Update analysis result."""
        self.analysis_results = analysis
        self.updated_at = datetime.now(timezone.utc)


class SessionMessage(Base):
    """Detailed message history (optional, for better query performance)."""

    __tablename__ = "session_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String(36), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(String, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    tokens_used = Column(Integer, default=0, nullable=False)


class CloudCredential(Base):
    """Encrypted cloud provider credentials."""

    __tablename__ = "cloud_credentials"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String(36), nullable=False)
    provider = Column(
        String(50), nullable=False
    )  # "aws", "azure", "gcp", "digitalocean"
    credential_type = Column(
        String(50), nullable=False
    )  # "api_key", "service_account", "oauth_token"
    encrypted_value = Column(String, nullable=False)  # Encrypted credential
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_used = Column(DateTime, nullable=True)
