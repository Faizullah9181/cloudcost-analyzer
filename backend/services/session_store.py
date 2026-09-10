"""Repository for sessions, message history and user profiles."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from backend.config import settings
from backend.database import SessionLocal
from backend.models import ChatSession, SessionMessage, UserProfile, utcnow


class SessionNotFound(LookupError):
    """Raised when a session id does not exist."""


def _providers_map(providers: Iterable[str] | dict[str, bool] | None) -> dict[str, bool]:
    if providers is None:
        return {"aws": True}
    if isinstance(providers, dict):
        result = {str(k).lower(): bool(v) for k, v in providers.items()}
    else:
        result = {str(p).lower(): True for p in providers}
    return result or {"aws": True}


class SessionStore:
    """Thin data-access layer over SQLAlchemy.

    Pass an existing DB session (e.g. the FastAPI dependency) or let the store
    open its own, in which case ``close()`` releases it.
    """

    def __init__(self, db: DBSession | None = None):
        self.db: DBSession = db or SessionLocal()
        self._owns_db = db is None

    # ----- lifecycle -------------------------------------------------------------

    def commit(self) -> None:
        """Commit pending changes."""
        self.db.commit()

    def rollback(self) -> None:
        """Roll back pending changes."""
        self.db.rollback()

    def close(self) -> None:
        """Close the DB session if this store opened it."""
        if self._owns_db:
            self.db.close()

    def __enter__(self) -> "SessionStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self.rollback()
        self.close()

    # ----- sessions -----------------------------------------------------------------

    def create_session(
        self,
        name: str,
        providers: Iterable[str] | dict[str, bool] | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        connection_context: dict[str, Any] | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        commit: bool = True,
    ) -> ChatSession:
        """Create and persist a new session."""
        llm = (llm_provider or settings.llm_provider).lower()
        session = ChatSession(
            name=name.strip() or "Untitled session",
            user_id=(user_id or "").strip() or None,
            cloud_providers=_providers_map(providers),
            connection_context=dict(connection_context or {}),
            llm_provider=llm,
            llm_model=llm_model if llm_model is not None else settings.llm_model_name(llm),
            is_active=True,
            message_count=0,
            context_tokens=0,
            compression_count=0,
            analysis_results={},
            tags=list(tags or []),
            custom_metadata={},
        )
        self.db.add(session)
        if commit:
            self.db.commit()
            self.db.refresh(session)
        else:
            self.db.flush()
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """Fetch a session by id (or by unique id prefix of at least 6 characters)."""
        session = self.db.get(ChatSession, session_id)
        if session is None and len(session_id) >= 6:
            matches = self.db.scalars(
                select(ChatSession).where(ChatSession.id.like(f"{session_id}%")).limit(2)
            ).all()
            if len(matches) == 1:
                session = matches[0]
        return session

    def require_session(self, session_id: str) -> ChatSession:
        """Fetch a session or raise ``SessionNotFound``."""
        session = self.get_session(session_id)
        if session is None:
            raise SessionNotFound(f"Session {session_id} not found")
        return session

    def list_sessions(
        self,
        limit: int = 10,
        skip: int = 0,
        include_archived: bool = False,
        user_id: str | None = None,
    ) -> list[ChatSession]:
        """Most recently updated sessions first."""
        stmt = select(ChatSession)
        if not include_archived:
            stmt = stmt.where(ChatSession.is_active.is_(True))
        if user_id:
            stmt = stmt.where(ChatSession.user_id == user_id)
        stmt = stmt.order_by(ChatSession.updated_at.desc()).offset(max(0, skip)).limit(max(1, min(limit, 200)))
        return list(self.db.scalars(stmt).all())

    def count_sessions(self, include_archived: bool = False) -> int:
        """Number of sessions."""
        stmt = select(func.count()).select_from(ChatSession)  # pylint: disable=not-callable
        if not include_archived:
            stmt = stmt.where(ChatSession.is_active.is_(True))
        return int(self.db.scalar(stmt) or 0)

    def count_messages(self, role: str | None = None) -> int:
        """Number of stored messages, optionally by role."""
        stmt = select(func.count()).select_from(SessionMessage)  # pylint: disable=not-callable
        if role:
            stmt = stmt.where(SessionMessage.role == role)
        return int(self.db.scalar(stmt) or 0)

    def update_session(
        self,
        session: ChatSession,
        *,
        name: str | None = None,
        connection_context: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        commit: bool = True,
    ) -> ChatSession:
        """Update editable session fields."""
        if name is not None and name.strip():
            session.name = name.strip()
        if connection_context is not None:
            merged = dict(session.connection_context or {})
            for provider, ctx in connection_context.items():
                if isinstance(ctx, dict):
                    merged[provider] = {**(merged.get(provider) or {}), **ctx}
                else:
                    merged[provider] = ctx
            session.connection_context = merged
        if tags is not None:
            session.tags = list(tags)
        session.updated_at = utcnow()
        if commit:
            self.db.commit()
        return session

    def archive_session(self, session_id: str, commit: bool = True) -> ChatSession:
        """Soft-delete a session."""
        session = self.require_session(session_id)
        session.is_active = False
        session.updated_at = utcnow()
        if commit:
            self.db.commit()
        return session

    def restore_session(self, session_id: str, commit: bool = True) -> ChatSession:
        """Undo a soft delete."""
        session = self.require_session(session_id)
        session.is_active = True
        session.updated_at = utcnow()
        if commit:
            self.db.commit()
        return session

    def delete_session(self, session_id: str, commit: bool = True) -> None:
        """Permanently delete a session and its messages."""
        session = self.require_session(session_id)
        self.db.delete(session)
        if commit:
            self.db.commit()

    # ----- messages ---------------------------------------------------------------------

    def add_message(
        self,
        session: ChatSession,
        role: str,
        content: str,
        *,
        tokens_used: int = 0,
        provider: str | None = None,
        tags: list[str] | None = None,
        analysis: dict[str, Any] | None = None,
        is_summary: bool = False,
        commit: bool = False,
    ) -> SessionMessage:
        """Append a message to a session (flushes; commits when asked)."""
        message = session.add_message(
            role,
            content,
            tokens_used=tokens_used,
            provider=provider,
            tags=tags,
            analysis=analysis,
            is_summary=is_summary,
        )
        self.db.flush()
        if commit:
            self.db.commit()
        return message

    def get_messages(self, session_id: str, limit: int | None = None, include_summaries: bool = True) -> list[SessionMessage]:
        """Messages for a session in order; ``limit`` keeps only the most recent ones."""
        stmt = select(SessionMessage).where(SessionMessage.session_id == session_id)
        if not include_summaries:
            stmt = stmt.where(SessionMessage.is_summary.is_(False))
        stmt = stmt.order_by(SessionMessage.seq.asc())
        messages = list(self.db.scalars(stmt).all())
        if limit is not None and limit > 0:
            messages = messages[-limit:]
        return messages

    def update_analysis(self, session: ChatSession, analysis: dict[str, Any], commit: bool = False) -> None:
        """Cache the latest analysis on the session."""
        session.update_analysis(analysis)
        if commit:
            self.db.commit()

    # ----- user profiles --------------------------------------------------------------------

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        """Persisted deep-memory snapshot for a user."""
        profile = self.db.get(UserProfile, user_id)
        return dict(profile.data or {}) if profile else None

    def save_user_profile(self, user_id: str, data: dict[str, Any], commit: bool = False) -> UserProfile:
        """Create or update a user's deep-memory snapshot."""
        profile = self.db.get(UserProfile, user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id, data=dict(data))
            self.db.add(profile)
        else:
            profile.data = dict(data)
            profile.updated_at = utcnow()
        self.db.flush()
        if commit:
            self.db.commit()
        return profile
