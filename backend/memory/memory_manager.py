"""
Memory Manager - Orchestration Layer
====================================
Coordinates the four memory layers for a session:

- HOT: base system prompt + session metadata + recent turns (always injected)
- COLD: searchable history, compressed into summaries as it grows
- PROCEDURAL: skills loaded on demand for the current query
- DEEP: optional cross-session user model

The manager only assembles context and tracks state; the ``AgentHarness``
owns persistence and the LLM call.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .cold_memory import ColdMemory, MessageRole, StoredMessage, Summarizer
from .deep_memory import DeepMemory
from .hot_memory import CloudProvider, HotMemory
from .procedural_memory import ProceduralMemory

_QUERY_TYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("forecast", ("forecast", "predict", "projection", "next month", "estimate")),
    ("comparison", ("compare", "comparison", "versus", " vs ")),
    ("inventory", ("inventory", "resources", "instances", "buckets", "list all", "how many")),
    ("optimization", ("optimi", "save", "saving", "reduce", "idle", "waste", "cheaper", "recommend")),
    ("trend", ("trend", "daily", "over time", "history", "growth", "last 30 days")),
    ("costs", ("cost", "spend", "bill", "charge", "expensive", "total")),
)


def detect_query_type(text: str) -> str:
    """Classify a query into a coarse analysis type."""
    lowered = f" {text.lower()} "
    for query_type, keywords in _QUERY_TYPES:
        if any(keyword in lowered for keyword in keywords):
            return query_type
    return "analysis"


def query_tags(text: str) -> list[str]:
    """Tags for a message derived from its content."""
    tags = {detect_query_type(text)}
    lowered = text.lower()
    for provider in CloudProvider:
        if provider.value in lowered:
            tags.add(provider.value)
    if re.search(r"\b(ec2|s3|rds|lambda)\b", lowered):
        tags.add("aws")
    return sorted(tags)


@dataclass
class MemoryMetrics:
    """Memory usage and performance metrics."""

    total_messages: int = 0
    total_retrievals: int = 0
    compression_count: int = 0
    last_compression_time: datetime | None = None
    last_prompt_words: int = 0


class MemoryManager:
    """Orchestrates the four memory layers for one session."""

    def __init__(
        self,
        session_id: str,
        user_id: str | None = None,
        enable_deep_memory: bool = False,
        *,
        system_prompt: str | None = None,
        compression_threshold: int = 20,
        recent_window: int = 10,
        context_word_limit: int = 6000,
        deep_memory_state: dict[str, Any] | None = None,
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.enable_deep_memory = bool(enable_deep_memory and user_id)

        self.hot_memory = HotMemory(session_id, session_name=session_id, system_prompt=system_prompt or "")
        self.cold_memory = ColdMemory(session_id)
        self.procedural_memory = ProceduralMemory()
        self.deep_memory: DeepMemory | None = (
            DeepMemory.from_dict(user_id, deep_memory_state) if self.enable_deep_memory and user_id else None
        )

        self.metrics = MemoryMetrics()
        self.compression_threshold = max(4, int(compression_threshold))
        self.recent_window = max(2, int(recent_window))
        self.context_word_limit = max(500, int(context_word_limit))
        self._summarizer: Summarizer | None = None

    # ----- setup ------------------------------------------------------------------

    def initialize_session(
        self,
        session_name: str,
        providers: Iterable[CloudProvider | str],
        llm_provider: str,
        connection_context: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Configure the session: name, providers (with account context) and LLM."""
        self.hot_memory.session_name = session_name
        self.hot_memory.llm_provider = llm_provider
        connection_context = connection_context or {}

        provider_list = [CloudProvider.parse(p) for p in providers]
        for provider in provider_list:
            ctx = connection_context.get(provider.value, {}) or {}
            account_id = str(
                ctx.get("account_id")
                or ctx.get("subscription_id")
                or ctx.get("project_id")
                or ctx.get("team")
                or ""
            )
            self.hot_memory.add_provider(
                provider,
                account_id=account_id,
                account_name=ctx.get("account_name") or ctx.get("name"),
                region=ctx.get("region"),
            )
        if provider_list:
            self.hot_memory.set_current_provider(provider_list[0])

        if self.deep_memory:
            self.deep_memory.record_session_start()
            if llm_provider:
                self.deep_memory.set_preferred_llm(llm_provider)

    def hydrate(self, records: Iterable[dict[str, Any]]) -> int:
        """Load persisted history (``SessionMessage.to_dict`` dicts) into cold + hot memory."""
        records = list(records)
        loaded = self.cold_memory.load_from_records(records)
        self.metrics.total_messages = len(self.cold_memory.messages)
        self.hot_memory.total_messages = sum(1 for r in records if r.get("role") in ("user", "assistant"))
        self.hot_memory.compression_count = self.cold_memory.compression_count = sum(
            1 for r in records if r.get("is_summary")
        )
        for record in [r for r in records if r.get("role") in ("user", "assistant")][-self.hot_memory.max_recent_interactions :]:
            self.hot_memory.add_interaction(record["role"], str(record.get("content", "")), record.get("tokens_used", 0))
        return loaded

    def set_summarizer(self, summarizer: Summarizer | None) -> None:
        """Provide an LLM-backed summariser used during compression."""
        self._summarizer = summarizer

    # ----- query processing -------------------------------------------------------------

    def process_query(self, query: str, user_id: str | None = None) -> tuple[str, dict[str, Any]]:
        """Retrieve context for a query, record it, and assemble the prompt.

        Returns:
            (assembled_prompt, context_data)
        """
        del user_id  # kept for backwards compatibility with earlier signature

        # 0. Focus the provider the user is talking about
        detected = self.hot_memory.detect_provider(query)
        if detected:
            self.hot_memory.set_current_provider(detected)
        query_type = detect_query_type(query)
        self.hot_memory.update_query_type(query_type)

        # 1. RETRIEVE - relevant history from COLD memory (before adding this query)
        cold_results = self.cold_memory.search_by_content(query, limit=4)
        self.metrics.total_retrievals += 1
        recalled = [r.message for r in cold_results if r.message not in self.cold_memory.messages[-2:]]
        cold_summary = self.cold_memory.summarize_messages(recalled) if recalled else ""
        summaries = [m.content for m in self.cold_memory.messages if m.is_summary]

        # 2. LOAD - relevant skills from PROCEDURAL memory
        relevant_skills = self.procedural_memory.get_relevant_skills(query, limit=2)

        # 3. RECORD - the user turn in COLD + HOT memory
        provider = self.hot_memory.current_provider.value if self.hot_memory.current_provider else None
        self._add_message_to_cold(MessageRole.USER, query, provider=provider, tags=query_tags(query))
        self.hot_memory.add_interaction("user", query)
        self.hot_memory.increment_message_count()

        # 4. LEARN - DEEP memory patterns
        if self.deep_memory:
            self.deep_memory.observe_query(query)

        # 5. ASSEMBLE
        assembled = self._assemble_complete_prompt(summaries, cold_summary, bool(relevant_skills))
        self.metrics.last_prompt_words = len(assembled.split())

        context_data = {
            "query_type": query_type,
            "provider": provider,
            "retrieved_messages": len(recalled),
            "loaded_skills": [s.id for s in relevant_skills],
            "cold_summary": cold_summary[:200],
            "prompt_words": self.metrics.last_prompt_words,
            "metrics": self._get_memory_metrics_dict(),
        }
        return assembled, context_data

    def record_response(
        self,
        response: str,
        tokens_used: int = 0,
        analysis_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Record the assistant turn; returns compression info when compression ran."""
        provider = self.hot_memory.current_provider.value if self.hot_memory.current_provider else "unknown"
        tokens_used = int(tokens_used or 0)
        tags = [str(analysis_data.get("query_type"))] if analysis_data and analysis_data.get("query_type") else []
        self._add_message_to_cold(MessageRole.ASSISTANT, response, tokens=tokens_used, provider=provider, tags=tags)

        if analysis_data:
            self.cold_memory.add_analysis(
                analysis_id=f"ana_{self.metrics.total_messages}",
                query=str(analysis_data.get("summary", response))[:120],
                provider=provider,
                query_type=str(analysis_data.get("query_type") or "analysis"),
                result=analysis_data,
                tokens_used=tokens_used,
            )

        self.hot_memory.add_interaction("assistant", response, tokens=tokens_used)
        self.hot_memory.increment_message_count()

        if self.cold_memory.messages_since_summary() >= self.compression_threshold:
            return self._compress_session()
        return None

    # ----- assembly ------------------------------------------------------------------------------

    def _assemble_complete_prompt(self, summaries: list[str], cold_summary: str, has_skills: bool) -> str:
        """Compose: system prompt, hot context, user profile, history summaries, recall, skills."""
        sections = [self.hot_memory.system_prompt, self.hot_memory.assemble_context()]

        if self.deep_memory:
            user_context = self.deep_memory.get_user_context_injection()
            if user_context:
                sections.append(user_context)

        if summaries:
            sections.append("### Earlier Session Summary:\n" + "\n".join(summaries[-2:]))

        if cold_summary:
            sections.append("### Relevant Earlier Context:\n" + cold_summary)

        if has_skills:
            skills_injection = self.procedural_memory.assemble_skills_injection(max_tokens=1200)
            if skills_injection:
                sections.append(skills_injection)

        complete = "\n\n".join(section for section in sections if section)
        words = complete.split()
        if len(words) > self.context_word_limit:
            complete = " ".join(words[: self.context_word_limit]) + "\n...(context trimmed)"
        return complete

    # ----- compression ----------------------------------------------------------------------------

    def _compress_session(self) -> dict[str, Any]:
        compressed, summary = self.cold_memory.compress(keep_recent=self.recent_window, summarizer=self._summarizer)
        result = {"compressed_messages": compressed, "pruned_messages": 0, "summary": summary}
        if compressed:
            self.hot_memory.increment_compression_count()
            self.metrics.compression_count += 1
            self.metrics.last_compression_time = datetime.now()
        return result

    def force_compression(self) -> dict[str, Any]:
        """Compress now, regardless of thresholds."""
        result = self._compress_session()
        result["pruned_messages"] = self.cold_memory.prune_retention_window()
        self.procedural_memory.clear_loaded_skills()
        self.hot_memory.clear_interactions()
        return result

    # ----- utilities ----------------------------------------------------------------------------------

    def _add_message_to_cold(
        self,
        role: MessageRole,
        content: str,
        tokens: int = 0,
        provider: str | None = None,
        tags: list[str] | None = None,
    ) -> StoredMessage:
        self.metrics.total_messages += 1
        if provider is None and self.hot_memory.current_provider:
            provider = self.hot_memory.current_provider.value
        return self.cold_memory.add_message(
            msg_id=f"msg_{self.metrics.total_messages}_{role.value}",
            role=role,
            content=content,
            provider=provider,
            tokens=tokens,
            tags=tags or [],
        )

    def deep_memory_state(self) -> dict[str, Any] | None:
        """Snapshot of the deep-memory layer for persistence."""
        return self.deep_memory.to_dict() if self.deep_memory else None

    def get_memory_status(self) -> dict[str, Any]:
        """Status of every layer."""
        return {
            "hot_memory": self.hot_memory.get_session_stats(),
            "cold_memory": self.cold_memory.get_stats(),
            "procedural_memory": {
                "total_skills": len(self.procedural_memory.skills),
                "loaded_skills": sorted(self.procedural_memory.loaded_skills),
            },
            "deep_memory": self.deep_memory.get_stats() if self.deep_memory else None,
            "metrics": self._get_memory_metrics_dict(),
        }

    def _get_memory_metrics_dict(self) -> dict[str, Any]:
        return {
            "total_messages": self.metrics.total_messages,
            "total_retrievals": self.metrics.total_retrievals,
            "compression_count": self.metrics.compression_count,
            "compression_threshold": self.compression_threshold,
            "messages_since_summary": self.cold_memory.messages_since_summary(),
            "last_compression": (
                self.metrics.last_compression_time.isoformat() if self.metrics.last_compression_time else None
            ),
            "last_prompt_words": self.metrics.last_prompt_words,
        }

    def export_session(self) -> dict[str, Any]:
        """Snapshot for archival/export."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "hot_memory": self.hot_memory.to_dict(),
            "cold_memory_stats": self.cold_memory.get_stats(),
            "message_count": len(self.cold_memory.messages),
            "analysis_count": len(self.cold_memory.analyses),
            "deep_memory": self.deep_memory_state(),
            "exported_at": datetime.now().isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<MemoryManager session={self.session_id} msgs={self.metrics.total_messages} "
            f"compressions={self.metrics.compression_count}>"
        )
