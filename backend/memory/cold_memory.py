"""
Cold Memory Layer - Session History & Retrieval
================================================
COLD MEMORY is the searchable history of a session. It is an in-process index
that the harness hydrates from the database on resume and keeps in sync as the
conversation progresses. Persistence itself lives in ``SessionStore``.

- Keyword search with recency weighting
- Extractive summaries (or an LLM summariser supplied by the harness)
- Compression: old turns collapse into a single summary message
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

_STOPWORDS = {
    "the", "a", "an", "my", "me", "what", "is", "are", "of", "for", "to", "in", "on",
    "show", "and", "this", "that", "how", "much", "do", "i", "we", "our", "please", "can",
    "you", "give", "get", "with", "by", "be", "it", "its", "was", "were", "about", "from",
}


class MessageRole(str, Enum):
    """Message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class StoredMessage:
    """A message stored in cold memory."""

    id: str
    session_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    tokens: int = 0
    provider: str | None = None
    analysis_id: str | None = None
    tags: list[str] = field(default_factory=list)
    is_summary: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialisable snapshot (content truncated)."""
        content = self.content if len(self.content) <= 200 else self.content[:200] + "..."
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role.value,
            "content": content,
            "timestamp": self.timestamp.isoformat(),
            "tokens": self.tokens,
            "provider": self.provider,
            "tags": list(self.tags),
            "is_summary": self.is_summary,
        }


@dataclass
class AnalysisResult:
    """Cached analysis result for quick recall."""

    id: str
    session_id: str
    timestamp: datetime
    query: str
    provider: str
    query_type: str
    result: dict[str, Any]
    tokens_used: int = 0

    def summary(self, max_chars: int = 200) -> str:
        """Brief description."""
        text = f"[{self.query_type.upper()}] {self.query}"
        return text if len(text) <= max_chars else text[:max_chars] + "..."


@dataclass
class SearchResult:
    """Result from a cold memory search."""

    message: StoredMessage
    relevance_score: float
    context_snippet: str

    def __repr__(self) -> str:
        return f"<SearchResult rel={self.relevance_score:.2f} role={self.message.role.value}>"


Summarizer = Callable[[list[StoredMessage]], str]


def _first_sentence(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    match = re.search(r"[.!?](\s|$)", text)
    sentence = text[: match.end()].strip() if match else text
    return sentence if len(sentence) <= limit else sentence[:limit].rstrip() + "..."


def _truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


class ColdMemory:
    """Session history index with search, summarisation and compression."""

    def __init__(self, session_id: str, retention_days: int = 30):
        self.session_id = session_id
        self.messages: list[StoredMessage] = []
        self.analyses: list[AnalysisResult] = []
        self.retention_days = retention_days
        self.compression_count = 0
        self._counter = 0

    # ----- storage ------------------------------------------------------------

    def _next_id(self, role: MessageRole) -> str:
        self._counter += 1
        return f"msg_{self._counter}_{role.value}"

    def add_message(
        self,
        msg_id: str | None,
        role: MessageRole | str,
        content: str,
        provider: str | None = None,
        tags: list[str] | None = None,
        tokens: int = 0,
        timestamp: datetime | None = None,
        is_summary: bool = False,
    ) -> StoredMessage:
        """Append a message to the index."""
        role = MessageRole(role) if not isinstance(role, MessageRole) else role
        message = StoredMessage(
            id=msg_id or self._next_id(role),
            session_id=self.session_id,
            role=role,
            content=content,
            timestamp=timestamp or datetime.now(),
            tokens=int(tokens or 0),
            provider=provider,
            tags=list(tags or []),
            is_summary=is_summary,
        )
        self.messages.append(message)
        return message

    def load_from_records(self, records: Iterable[dict[str, Any]]) -> int:
        """Hydrate from persisted message dicts (``SessionMessage.to_dict`` shape)."""
        loaded = 0
        for record in records:
            role = record.get("role", "user")
            if role not in MessageRole._value2member_map_:
                continue
            timestamp = record.get("timestamp")
            parsed: datetime | None = None
            if isinstance(timestamp, datetime):
                parsed = timestamp
            elif isinstance(timestamp, str):
                try:
                    parsed = datetime.fromisoformat(timestamp)
                except ValueError:
                    parsed = None
            if parsed is not None and parsed.tzinfo is not None:
                parsed = parsed.astimezone().replace(tzinfo=None)
            self.add_message(
                msg_id=record.get("id"),
                role=MessageRole(role),
                content=str(record.get("content", "")),
                provider=record.get("provider"),
                tags=list(record.get("tags") or []),
                tokens=int(record.get("tokens_used") or record.get("tokens") or 0),
                timestamp=parsed,
                is_summary=bool(record.get("is_summary")),
            )
            loaded += 1
        return loaded

    def add_analysis(
        self,
        analysis_id: str,
        query: str,
        provider: str,
        query_type: str,
        result: dict[str, Any],
        tokens_used: int = 0,
    ) -> AnalysisResult:
        """Store a structured analysis for later recall."""
        analysis = AnalysisResult(
            id=analysis_id,
            session_id=self.session_id,
            timestamp=datetime.now(),
            query=query,
            provider=provider,
            query_type=query_type,
            result=result,
            tokens_used=tokens_used,
        )
        self.analyses.append(analysis)
        return analysis

    # ----- search ---------------------------------------------------------------

    @staticmethod
    def _keywords(query: str) -> list[str]:
        words = re.findall(r"[a-z0-9]+", query.lower())
        keywords = [w for w in words if w not in _STOPWORDS and len(w) > 1]
        return keywords or words

    def search_by_content(
        self, query: str, limit: int = 5, provider_filter: str | None = None
    ) -> list[SearchResult]:
        """Keyword search ranked by overlap, tags and recency."""
        query_lower = " ".join(query.lower().split())
        keywords = self._keywords(query)
        if not keywords:
            return []

        now = datetime.now()
        results: list[SearchResult] = []
        for message in self.messages:
            if provider_filter and message.provider != provider_filter:
                continue
            content_lower = message.content.lower()
            score = 0.0
            if query_lower and query_lower in content_lower:
                score += 0.8
            matches = sum(1 for kw in keywords if re.search(rf"\b{re.escape(kw)}", content_lower))
            score += (matches / len(keywords)) * 0.5
            if any(tag in keywords for tag in message.tags):
                score += 0.3
            hours_ago = max(0.0, (now - message.timestamp).total_seconds() / 3600)
            score += max(0.0, 1 - hours_ago / 24) * 0.2
            if matches == 0 and query_lower not in content_lower:
                continue
            position = content_lower.find(keywords[0])
            start = max(0, position - 60) if position >= 0 else 0
            snippet = _truncate(message.content[start : start + 220], 220)
            results.append(SearchResult(message=message, relevance_score=round(score, 3), context_snippet=snippet))

        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]

    def search_by_date_range(
        self, start_date: datetime, end_date: datetime, provider_filter: str | None = None
    ) -> list[StoredMessage]:
        """Messages within a time window."""
        return sorted(
            (
                m
                for m in self.messages
                if start_date <= m.timestamp <= end_date and (provider_filter is None or m.provider == provider_filter)
            ),
            key=lambda m: m.timestamp,
        )

    def search_by_tag(self, tag: str, limit: int = 10) -> list[StoredMessage]:
        """Messages carrying a tag, newest first."""
        results = [m for m in self.messages if tag in m.tags]
        results.sort(key=lambda m: m.timestamp, reverse=True)
        return results[:limit]

    def search_by_provider(self, provider: str, limit: int = 20) -> list[StoredMessage]:
        """Messages about a provider, newest first."""
        results = [m for m in self.messages if m.provider == provider]
        results.sort(key=lambda m: m.timestamp, reverse=True)
        return results[:limit]

    def find_similar_analyses(self, query_type: str, provider: str, limit: int = 3) -> list[AnalysisResult]:
        """Past analyses of the same kind for the same provider."""
        results = [a for a in self.analyses if a.query_type == query_type and a.provider == provider]
        results.sort(key=lambda a: a.timestamp, reverse=True)
        return results[:limit]

    # ----- summarisation ----------------------------------------------------------

    def summarize_messages(self, messages: list[StoredMessage], max_chars: int = 900) -> str:
        """Extractive summary of a set of messages."""
        if not messages:
            return ""
        parts: list[str] = []
        prior = [m.content for m in messages if m.is_summary]
        if prior:
            parts.append("Earlier summary: " + " ".join(_truncate(p, 300) for p in prior))
        questions = [m.content for m in messages if m.role == MessageRole.USER][-6:]
        if questions:
            parts.append("User asked: " + "; ".join(_truncate(q, 120) for q in questions))
        findings = [m.content for m in messages if m.role == MessageRole.ASSISTANT and not m.is_summary][-6:]
        if findings:
            parts.append("Key findings: " + " | ".join(_first_sentence(f) for f in findings))
        providers = sorted({m.provider for m in messages if m.provider})
        if providers:
            parts.append("Providers discussed: " + ", ".join(providers))
        return _truncate("\n".join(parts), max_chars)

    def get_context_summary(self) -> str:
        """Short description of the whole history."""
        if not self.messages:
            return "### Cold Memory Summary:\n(No history)"
        lines = ["### Cold Memory Summary:", f"Total messages: {len(self.messages)}"]
        lines.append(f"Date range: {self.messages[0].timestamp.date()} to {self.messages[-1].timestamp.date()}")
        user_count = sum(1 for m in self.messages if m.role == MessageRole.USER)
        assistant_count = sum(1 for m in self.messages if m.role == MessageRole.ASSISTANT)
        lines.append(f"Messages: {user_count} user, {assistant_count} assistant")
        providers = sorted({m.provider for m in self.messages if m.provider})
        if providers:
            lines.append("Providers: " + ", ".join(providers))
        if self.analyses:
            recent = self.analyses[-1]
            lines.append(f"Analyses: {len(self.analyses)} stored (last: {recent.query_type} on {recent.provider})")
        return "\n".join(lines)

    # ----- compression & retention ---------------------------------------------------

    def messages_since_summary(self) -> int:
        """Number of non-summary messages after the last summary."""
        count = 0
        for message in reversed(self.messages):
            if message.is_summary:
                break
            count += 1
        return count

    def compress(self, keep_recent: int = 10, summarizer: Summarizer | None = None) -> tuple[int, str]:
        """Collapse everything but the last ``keep_recent`` messages into one summary.

        Returns:
            (number of messages compressed, summary text)
        """
        keep_recent = max(0, keep_recent)
        older = self.messages[:-keep_recent] if keep_recent else list(self.messages)
        recent = self.messages[len(older):]
        compressible = [m for m in older if not m.is_summary]
        if not compressible:
            return 0, ""

        summary_text = ""
        if summarizer is not None:
            try:
                summary_text = (summarizer(older) or "").strip()
            except Exception:  # pylint: disable=broad-exception-caught
                summary_text = ""
        if not summary_text:
            summary_text = self.summarize_messages(older)

        self.compression_count += 1
        summary = StoredMessage(
            id=f"summary_{self.compression_count}",
            session_id=self.session_id,
            role=MessageRole.SYSTEM,
            content=summary_text,
            timestamp=datetime.now(),
            tags=["summary"],
            is_summary=True,
        )
        self.messages = [summary, *recent]
        return len(compressible), summary_text

    def compress_old_messages(self, days: int = 7) -> tuple[int, str]:
        """Compress messages older than ``days`` (kept for API compatibility)."""
        cutoff = datetime.now() - timedelta(days=days)
        recent_count = sum(1 for m in self.messages if m.timestamp >= cutoff)
        return self.compress(keep_recent=recent_count)

    def get_old_messages(self, days: int = 14) -> list[StoredMessage]:
        """Messages older than N days."""
        cutoff = datetime.now() - timedelta(days=days)
        return [m for m in self.messages if m.timestamp < cutoff]

    def prune_retention_window(self) -> int:
        """Drop messages outside the retention window (summaries are kept)."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        before = len(self.messages)
        self.messages = [m for m in self.messages if m.is_summary or m.timestamp >= cutoff]
        return before - len(self.messages)

    # ----- stats -----------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Statistics for status displays."""
        return {
            "session_id": self.session_id,
            "total_messages": len(self.messages),
            "total_analyses": len(self.analyses),
            "summaries": sum(1 for m in self.messages if m.is_summary),
            "compression_count": self.compression_count,
            "message_breakdown": {
                "user": sum(1 for m in self.messages if m.role == MessageRole.USER),
                "assistant": sum(1 for m in self.messages if m.role == MessageRole.ASSISTANT),
                "system": sum(1 for m in self.messages if m.role == MessageRole.SYSTEM),
            },
            "providers": sorted({m.provider for m in self.messages if m.provider}),
            "tags_used": sorted({tag for m in self.messages for tag in m.tags}),
            "total_tokens": sum(m.tokens for m in self.messages),
            "date_range": {
                "first": self.messages[0].timestamp.isoformat() if self.messages else None,
                "last": self.messages[-1].timestamp.isoformat() if self.messages else None,
            },
        }

    def __repr__(self) -> str:
        return f"<ColdMemory session={self.session_id} msgs={len(self.messages)} analyses={len(self.analyses)}>"
