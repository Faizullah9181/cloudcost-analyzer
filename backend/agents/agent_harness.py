"""
Agent Harness - Memory-Aware Agent Runtime
==========================================
``AgentHarness`` is the single runtime used by the CLI and the HTTP API. For a
session it:

1. Persists the session, its messages and analyses (``SessionStore``)
2. Maintains the 4-layer memory (``MemoryManager``) and injects it into the prompt
3. Builds a Strands agent with the tools for the session's cloud providers
4. Runs queries, parses the structured JSON answer, and records everything
5. Compresses long sessions automatically and replays history on resume
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.agents.cost_analyzer import (
    build_agent,
    estimate_tokens,
    extract_json,
    normalize_analysis,
    result_text,
    tool_calls_from_metrics,
    usage_from_metrics,
)
from backend.agents.llm import build_model
from backend.agents.prompts import SUMMARIZER_PROMPT, build_base_system_prompt
from backend.agents.tools import get_tools, tool_names
from backend.config import SUPPORTED_CLOUD_PROVIDERS, settings
from backend.memory import CloudProvider, MemoryManager, query_tags
from backend.memory.cold_memory import StoredMessage
from backend.models import ChatSession
from backend.services.session_store import SessionStore

logger = logging.getLogger(__name__)

# Non-secret connection fields that may be stored with the session.
_CONTEXT_FIELDS = {
    "aws": ("account_id", "account_name", "region", "auth_method", "notes"),
    "azure": ("subscription_id", "account_name", "auth_method", "notes"),
    "gcp": ("project_id", "account_name", "auth_method", "notes"),
    "digitalocean": ("account_name", "team", "auth_method", "notes"),
}

# Secret fields that are applied to the running process only, never persisted.
_SECRET_FIELDS = {
    "aws": {
        "access_key_id": "aws_access_key_id",
        "secret_access_key": "aws_secret_access_key",
        "session_token": "aws_session_token",
        "profile": "aws_profile",
    },
    "azure": {
        "tenant_id": "azure_tenant_id",
        "client_id": "azure_client_id",
        "client_secret": "azure_client_secret",
    },
    "gcp": {"service_account_json": "gcp_service_account_json"},
    "digitalocean": {"api_token": "digitalocean_api_token"},
}


@dataclass
class AnalysisTurn:
    """Outcome of one ``AgentHarness.analyze`` call."""

    success: bool
    response: str
    analysis: dict[str, Any]
    raw_response: str = ""
    error: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    memory_context: dict[str, Any] = field(default_factory=dict)
    compression: dict[str, Any] | None = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialisable representation."""
        return {
            "success": self.success,
            "response": self.response,
            "analysis": self.analysis,
            "error": self.error,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "memory": self.memory_context,
            "compression": self.compression,
            "duration_seconds": round(self.duration_seconds, 3),
        }


class AgentHarness:
    """Memory-aware agent runtime bound to one persisted session at a time."""

    def __init__(
        self,
        store: SessionStore | None = None,
        *,
        callback_handler: Callable[..., Any] | None = None,
        enable_deep_memory: bool = True,
        llm_summaries: bool | None = None,
        agent_factory: Callable[..., Any] | None = None,
    ):
        self.store = store or SessionStore()
        self._owns_store = store is None
        self.callback_handler = callback_handler
        self.enable_deep_memory = enable_deep_memory
        self.llm_summaries = settings.memory_llm_summaries if llm_summaries is None else llm_summaries
        self._agent_factory = agent_factory or build_agent

        self.session: ChatSession | None = None
        self.memory_manager: MemoryManager | None = None
        self._model = None
        self._messages: list[dict[str, Any]] = []

        self.is_active = False
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.query_count = 0
        self.tool_calls: list[dict[str, Any]] = []

    # ----- properties ----------------------------------------------------------------

    @property
    def session_id(self) -> str | None:
        """Id of the bound session."""
        return self.session.id if self.session else None

    @property
    def session_name(self) -> str | None:
        """Name of the bound session."""
        return self.session.name if self.session else None

    @property
    def providers(self) -> list[str]:
        """Enabled cloud providers for the bound session."""
        return self.session.enabled_providers() if self.session else []

    @property
    def active_providers(self) -> list[CloudProvider]:
        """Enabled providers as enum members."""
        return [CloudProvider.parse(p) for p in self.providers]

    @property
    def llm_provider(self) -> str:
        """LLM provider for the bound session."""
        return self.session.llm_provider if self.session else settings.llm_provider

    @property
    def connection_context(self) -> dict[str, Any]:
        """Non-secret connection context stored with the session."""
        return dict(self.session.connection_context or {}) if self.session else {}

    @property
    def user_id(self) -> str | None:
        """User id of the bound session."""
        return self.session.user_id if self.session else None

    # ----- session lifecycle -----------------------------------------------------------

    def create_session(
        self,
        session_name: str,
        providers: list[CloudProvider | str],
        llm_provider: str | None = None,
        connection_context: dict[str, dict[str, Any]] | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        credentials: dict[str, dict[str, Any]] | None = None,
    ) -> ChatSession:
        """Create a new persisted session and bind the harness to it.

        ``credentials`` (if given) is split into non-secret connection context, which is
        stored, and secrets, which are applied to the running process only.
        """
        provider_names = [CloudProvider.parse(p).value for p in providers]
        if not provider_names:
            raise ValueError("At least one cloud provider is required")
        context = dict(connection_context or {})
        for provider, creds in (credentials or {}).items():
            safe, _ = self._split_credentials(provider, creds)
            if safe:
                context[provider] = {**(context.get(provider) or {}), **safe}
            self._apply_secrets(provider, creds)

        session = self.store.create_session(
            name=session_name,
            providers=provider_names,
            llm_provider=llm_provider,
            connection_context=context,
            user_id=user_id,
            tags=tags,
        )
        self._attach(session, hydrate=False)
        logger.info("Created session %s (%s) providers=%s llm=%s", session.id, session.name, provider_names, session.llm_provider)
        return session

    def load_session(self, session_id: str) -> ChatSession:
        """Bind to an existing session, replaying its history into memory and the agent."""
        session = self.store.require_session(session_id)
        self._attach(session, hydrate=True)
        logger.info("Loaded session %s (%s) with %d messages", session.id, session.name, session.message_count)
        return session

    def _attach(self, session: ChatSession, hydrate: bool) -> None:
        self.session = session
        self.is_active = True
        self.last_activity = datetime.now()
        self._model = None
        self._messages = []
        self.tool_calls = []

        user_id = session.user_id
        deep_state = self.store.get_user_profile(user_id) if (user_id and self.enable_deep_memory) else None
        self.memory_manager = MemoryManager(
            session_id=session.id,
            user_id=user_id,
            enable_deep_memory=self.enable_deep_memory,
            system_prompt=build_base_system_prompt(self.providers, self.connection_context),
            compression_threshold=settings.memory_compression_threshold,
            recent_window=settings.memory_recent_window,
            context_word_limit=settings.memory_context_word_limit,
            deep_memory_state=deep_state,
        )
        self.memory_manager.initialize_session(
            session_name=session.name,
            providers=self.providers,
            llm_provider=session.llm_provider,
            connection_context=self.connection_context,
        )
        if self.llm_summaries:
            self.memory_manager.set_summarizer(self._summarize_with_llm)

        if hydrate:
            records = [m.to_dict() for m in self.store.get_messages(session.id)]
            self.memory_manager.hydrate(records)
            self._messages = self._build_replay_messages(records, self.memory_manager.recent_window)
        self.query_count = 0

    # ----- credentials -------------------------------------------------------------------

    @staticmethod
    def _split_credentials(provider: str, creds: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
        provider = CloudProvider.parse(provider).value
        creds = creds or {}
        safe = {k: v for k, v in creds.items() if k in _CONTEXT_FIELDS.get(provider, ()) and v not in (None, "")}
        secrets = {k: v for k, v in creds.items() if k in _SECRET_FIELDS.get(provider, {}) and v not in (None, "")}
        return safe, secrets

    def _apply_secrets(self, provider: str, creds: dict[str, Any] | None) -> None:
        provider = CloudProvider.parse(provider).value
        _, secrets = self._split_credentials(provider, creds)
        for key, value in secrets.items():
            setattr(settings, _SECRET_FIELDS[provider][key], str(value))
        if provider == "aws" and (creds or {}).get("region"):
            settings.aws_region = str(creds["region"])
        if provider == "azure" and (creds or {}).get("subscription_id"):
            settings.azure_subscription_id = str(creds["subscription_id"])
        if provider == "gcp" and (creds or {}).get("project_id"):
            settings.gcp_project_id = str(creds["project_id"])
        if secrets:
            self._model = None  # credentials may affect the Bedrock client

    def set_provider_credentials(self, provider: CloudProvider | str, credentials: dict[str, Any]) -> None:
        """Attach provider credentials: context is persisted, secrets stay in-process."""
        name = CloudProvider.parse(provider).value
        if name not in SUPPORTED_CLOUD_PROVIDERS:
            raise ValueError(f"Unsupported provider {name}")
        safe, _ = self._split_credentials(name, credentials)
        self._apply_secrets(name, credentials)
        if self.session is not None:
            if safe:
                self.store.update_session(self.session, connection_context={name: safe}, commit=True)
            if name not in self.providers:
                self.session.cloud_providers[name] = True
                self.store.commit()
            self._refresh_prompt()

    def get_provider_credentials(self, provider: CloudProvider | str) -> dict[str, Any] | None:
        """Stored (non-secret) connection context for a provider."""
        return self.connection_context.get(CloudProvider.parse(provider).value)

    def _refresh_prompt(self) -> None:
        if self.memory_manager and self.session:
            self.memory_manager.hot_memory.set_system_prompt(
                build_base_system_prompt(self.providers, self.connection_context)
            )
            self.memory_manager.initialize_session(
                self.session.name, self.providers, self.session.llm_provider, self.connection_context
            )

    # ----- agent plumbing -----------------------------------------------------------------

    def _ensure_model(self):
        if self._model is None:
            self._model = build_model(self.llm_provider)
        return self._model

    def _make_agent(self, system_prompt: str):
        assert self.memory_manager is not None
        return self._agent_factory(
            system_prompt=system_prompt,
            providers=self.providers,
            model=self._ensure_model(),
            messages=list(self._messages),
            callback_handler=self.callback_handler,
            window_size=max(20, self.memory_manager.recent_window * 4),
        )

    @staticmethod
    def _build_replay_messages(records: list[dict[str, Any]], recent_window: int) -> list[dict[str, Any]]:
        """Turn stored turns into an alternating user/assistant Strands message list."""
        turns = [r for r in records if r.get("role") in ("user", "assistant") and not r.get("is_summary")]
        messages: list[dict[str, Any]] = []
        for record in turns[-(recent_window * 2) :]:
            content = str(record.get("content") or "").strip()
            role = record["role"]
            if not content:
                continue
            if not messages and role != "user":
                continue
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"][0]["text"] += f"\n\n{content}"
            else:
                messages.append({"role": role, "content": [{"text": content}]})
        if messages and messages[-1]["role"] == "user":
            messages.pop()
        return messages

    def _trim_history(self) -> None:
        """Keep only recent text turns in the agent's conversation after compression."""
        assert self.memory_manager is not None
        records = [
            {"role": m["role"], "content": "".join(b.get("text", "") for b in m.get("content", []) if isinstance(b, dict))}
            for m in self._messages
            if m.get("role") in ("user", "assistant")
        ]
        self._messages = self._build_replay_messages(records, self.memory_manager.recent_window // 2 or 1)

    def _summarize_with_llm(self, messages: list[StoredMessage]) -> str:
        """Summarise old turns with the session's model (falls back to extractive on failure)."""
        transcript = "\n".join(f"{m.role.value}: {m.content}" for m in messages if m.content.strip())
        if not transcript:
            return ""
        agent = self._agent_factory(
            system_prompt=SUMMARIZER_PROMPT,
            model=self._ensure_model(),
            tools=[],
            callback_handler=None,
            window_size=4,
        )
        return result_text(agent(f"Summarise this conversation:\n\n{transcript[-12000:]}")).strip()

    # ----- query processing -------------------------------------------------------------------

    def analyze(self, query: str, stream: bool = False) -> AnalysisTurn:  # pylint: disable=unused-argument
        """Run one query through memory, the agent and persistence."""
        if not self.session or not self.memory_manager:
            raise RuntimeError("No active session. Call create_session() or load_session() first.")
        query = query.strip()
        if not query:
            raise ValueError("Query must not be empty")

        started = time.perf_counter()
        self.query_count += 1
        self.last_activity = datetime.now()

        assembled_prompt, memory_context = self.memory_manager.process_query(query)
        provider = memory_context.get("provider")
        logger.debug(
            "[MEMORY] recalled=%s skills=%s prompt_words=%s",
            memory_context.get("retrieved_messages"),
            memory_context.get("loaded_skills"),
            memory_context.get("prompt_words"),
        )

        self.store.add_message(self.session, "user", query, provider=provider, tags=query_tags(query))
        self.store.commit()

        raw = ""
        tool_calls: list[dict[str, Any]] = []
        usage: dict[str, int] = {}
        error: str | None = None
        try:
            agent = self._make_agent(assembled_prompt)
            result = agent(query)
            self._messages = list(agent.messages)
            raw = result_text(result)
            tool_calls = tool_calls_from_metrics(result.metrics)
            usage = usage_from_metrics(result.metrics)
            analysis = normalize_analysis(extract_json(raw), raw, query)
            success = True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.exception("Agent run failed for session %s", self.session.id)
            error = f"{type(exc).__name__}: {exc}"
            analysis = normalize_analysis(None, f"Analysis failed: {error}", query)
            success = False

        response_text = analysis["summary"]
        tokens = usage.get("total_tokens") or estimate_tokens(raw or response_text)
        compression = self.memory_manager.record_response(response_text, tokens_used=tokens, analysis_data=analysis)

        stored_analysis = {k: v for k, v in analysis.items() if k not in ("a2ui_messages", "raw_response")}
        self.store.add_message(
            self.session,
            "assistant",
            response_text,
            tokens_used=tokens,
            provider=provider,
            tags=[analysis["query_type"]] + (["error"] if not success else []),
            analysis=stored_analysis if success else None,
        )
        if success:
            self.store.update_analysis(self.session, stored_analysis)

        if compression and compression.get("compressed_messages"):
            self.session.compression_count = (self.session.compression_count or 0) + 1
            self.store.add_message(
                self.session, "system", compression["summary"], tags=["summary"], is_summary=True
            )
            self._trim_history()

        self._persist_deep_memory()
        self.store.commit()
        self.tool_calls.extend(tool_calls)

        return AnalysisTurn(
            success=success,
            response=response_text,
            analysis=analysis,
            raw_response=raw,
            error=error,
            tool_calls=tool_calls,
            usage=usage,
            memory_context=memory_context,
            compression=compression,
            duration_seconds=time.perf_counter() - started,
        )

    def _persist_deep_memory(self) -> None:
        if self.memory_manager and self.memory_manager.deep_memory and self.user_id:
            self.store.save_user_profile(self.user_id, self.memory_manager.deep_memory_state() or {})

    # ----- long-session management -------------------------------------------------------------

    def compress_context(self) -> dict[str, Any]:
        """Manually compress the session context."""
        if not self.session or not self.memory_manager:
            raise RuntimeError("No active session")
        result = self.memory_manager.force_compression()
        if result.get("compressed_messages"):
            self.session.compression_count = (self.session.compression_count or 0) + 1
            self.store.add_message(self.session, "system", result["summary"], tags=["summary"], is_summary=True)
            self._trim_history()
            self.store.commit()
        result["compression_count"] = int(self.session.compression_count or 0)
        return result

    def check_compression_needed(self) -> bool:
        """Whether the next response will trigger automatic compression."""
        if not self.memory_manager:
            return False
        remaining = self.memory_manager.compression_threshold - self.memory_manager.cold_memory.messages_since_summary()
        return remaining <= 2

    # ----- introspection ---------------------------------------------------------------------------

    def get_session_info(self) -> dict[str, Any]:
        """Session summary."""
        info = self.session.to_dict() if self.session else {}
        info.update(
            {
                "query_count": self.query_count,
                "is_active": self.is_active,
                "harness_started_at": self.created_at.isoformat(),
                "last_activity": self.last_activity.isoformat(),
                "tools": tool_names(self.providers),
            }
        )
        return info

    def get_memory_status(self) -> dict[str, Any]:
        """Status of the four memory layers."""
        return self.memory_manager.get_memory_status() if self.memory_manager else {}

    def get_health_status(self) -> dict[str, Any]:
        """Health summary for the CLI ``/health`` command."""
        if not self.memory_manager:
            return {"session_active": False}
        status = self.memory_manager.get_memory_status()
        return {
            "session_active": self.is_active,
            "llm": f"{self.llm_provider}/{settings.llm_model_name(self.llm_provider)}",
            "providers": self.providers,
            "tools": len(get_tools(self.providers)),
            "memory_layers": {
                "hot": status["hot_memory"]["recent_interactions"],
                "cold": status["cold_memory"]["total_messages"],
                "procedural": status["procedural_memory"]["total_skills"],
                "deep": "enabled" if self.memory_manager.deep_memory else "disabled",
            },
            "compression_status": {
                "compressions": status["metrics"]["compression_count"],
                "threshold": status["metrics"]["compression_threshold"],
                "messages_since_summary": status["metrics"]["messages_since_summary"],
                "last_compression": status["metrics"]["last_compression"],
            },
            "query_stats": {
                "total_queries": self.query_count,
                "tool_calls": sum(call.get("calls", 0) for call in self.tool_calls),
            },
        }

    def export_session(self) -> dict[str, Any]:
        """Full export: persisted session + memory snapshot."""
        if not self.session:
            return {}
        self.store.db.refresh(self.session)
        export = self.session.to_export()
        export["memory"] = self.memory_manager.export_session() if self.memory_manager else None
        export["query_count"] = self.query_count
        return export

    def list_sessions(self, limit: int = 10, include_archived: bool = False) -> list[dict[str, Any]]:
        """Recent sessions as dicts."""
        return [s.to_dict() for s in self.store.list_sessions(limit=limit, include_archived=include_archived)]

    def delete_session(self, session_id: str | None = None, hard: bool = False) -> None:
        """Archive (default) or permanently delete a session."""
        target = session_id or self.session_id
        if not target:
            raise RuntimeError("No session to delete")
        if hard:
            self.store.delete_session(target)
        else:
            self.store.archive_session(target)
        if self.session and self.session.id == target:
            self.is_active = False

    def end_session(self) -> dict[str, Any]:
        """Finish the interactive session (keeps it resumable) and return a summary."""
        if self.memory_manager and self.memory_manager.deep_memory:
            self.memory_manager.deep_memory.record_session_end()
            self._persist_deep_memory()
            self.store.commit()
        self.is_active = False
        return {
            "session_id": self.session_id,
            "duration_minutes": round((datetime.now() - self.created_at).total_seconds() / 60, 2),
            "query_count": self.query_count,
            "message_count": int(self.session.message_count or 0) if self.session else 0,
            "compression_count": int(self.session.compression_count or 0) if self.session else 0,
        }

    def close(self) -> None:
        """Release the database session if the harness created it."""
        if self._owns_store:
            self.store.close()

    def __enter__(self) -> "AgentHarness":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<AgentHarness session={self.session_id} queries={self.query_count} providers={self.providers}>"
