"""
Hot Memory Layer - Prompt Context
=================================
HOT MEMORY is the small, always-injected part of the prompt:

1. Base system instructions (set by the memory manager)
2. Session metadata (name, providers, accounts)
3. The most recent interactions (short window)
4. Current task hint (last query type per provider)

It is session-scoped, in-memory and cheap to assemble.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CloudProvider(str, Enum):
    """Supported cloud providers."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    DIGITALOCEAN = "digitalocean"

    @classmethod
    def parse(cls, value: "CloudProvider | str") -> "CloudProvider":
        """Coerce a provider name (case-insensitive) or enum member into the enum."""
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:
            supported = ", ".join(member.value for member in cls)
            raise ValueError(f"Unknown cloud provider {value!r}. Supported: {supported}") from exc


@dataclass
class ProviderContext:
    """Current context for a cloud provider."""

    name: CloudProvider
    account_id: str = ""
    account_name: str | None = None
    region: str | None = None
    authenticated: bool = False
    last_query_type: str | None = None
    last_query_time: datetime | None = None

    def label(self) -> str:
        """Human-readable account label."""
        parts = [self.account_id or "default credentials"]
        if self.account_name:
            parts.append(f"({self.account_name})")
        if self.region:
            parts.append(f"| region {self.region}")
        return " ".join(parts)


@dataclass
class RecentInteraction:
    """Recent user/assistant interaction kept for short-term context."""

    role: str
    content: str
    timestamp: datetime
    tokens: int = 0


DEFAULT_SYSTEM_PROMPT = (
    "You are Shimo, an expert multi-cloud cost analytics agent. Use the available tools to "
    "retrieve real cost data, then explain spending, trends and optimisation opportunities "
    "with specific numbers."
)


@dataclass
class HotMemory:
    """Always-available prompt context for a session."""

    session_id: str
    session_name: str = ""
    system_prompt: str = ""

    active_providers: list[CloudProvider] = field(default_factory=list)
    current_provider: CloudProvider | None = None
    llm_provider: str = "bedrock"
    created_at: datetime = field(default_factory=datetime.now)

    provider_contexts: dict[CloudProvider, ProviderContext] = field(default_factory=dict)

    recent_interactions: list[RecentInteraction] = field(default_factory=list)
    max_recent_interactions: int = 6
    recent_content_chars: int = 300

    total_messages: int = 0
    compression_count: int = 0

    def __post_init__(self) -> None:
        if not self.system_prompt:
            self.system_prompt = DEFAULT_SYSTEM_PROMPT
        if not self.session_name:
            self.session_name = self.session_id

    # ----- system prompt --------------------------------------------------

    def set_system_prompt(self, prompt: str) -> None:
        """Replace the base system prompt."""
        self.system_prompt = prompt

    def get_system_prompt(self) -> str:
        """Return the base system prompt."""
        return self.system_prompt

    # ----- providers --------------------------------------------------------

    def add_provider(
        self,
        provider: CloudProvider | str,
        account_id: str = "",
        account_name: str | None = None,
        region: str | None = None,
    ) -> ProviderContext:
        """Register an active provider for this session."""
        provider = CloudProvider.parse(provider)
        if provider not in self.active_providers:
            self.active_providers.append(provider)
        context = ProviderContext(
            name=provider,
            account_id=account_id or "",
            account_name=account_name,
            region=region,
            authenticated=True,
        )
        self.provider_contexts[provider] = context
        if self.current_provider is None:
            self.current_provider = provider
        return context

    def set_current_provider(self, provider: CloudProvider | str) -> None:
        """Switch the provider the conversation is currently focused on."""
        provider = CloudProvider.parse(provider)
        if provider not in self.active_providers:
            raise ValueError(f"{provider.value} not in active providers")
        self.current_provider = provider

    def get_current_provider(self) -> ProviderContext | None:
        """Context of the current provider."""
        if self.current_provider is None:
            return None
        return self.provider_contexts.get(self.current_provider)

    def get_provider_context(self, provider: CloudProvider | str) -> ProviderContext | None:
        """Context for a specific provider."""
        return self.provider_contexts.get(CloudProvider.parse(provider))

    def detect_provider(self, text: str) -> CloudProvider | None:
        """Guess which active provider a query is about, if it names one."""
        lowered = text.lower()
        aliases = {
            CloudProvider.AWS: ("aws", "amazon", "ec2", "s3", "rds", "lambda"),
            CloudProvider.AZURE: ("azure", "microsoft"),
            CloudProvider.GCP: ("gcp", "google", "bigquery", "gce"),
            CloudProvider.DIGITALOCEAN: ("digitalocean", "digital ocean", "droplet"),
        }
        for provider in self.active_providers:
            if any(alias in lowered for alias in aliases[provider]):
                return provider
        return None

    # ----- recent interactions ----------------------------------------------

    def add_interaction(self, role: str, content: str, tokens: int = 0) -> None:
        """Append an interaction, keeping only the most recent window."""
        self.recent_interactions.append(
            RecentInteraction(role=role, content=content, timestamp=datetime.now(), tokens=tokens)
        )
        if len(self.recent_interactions) > self.max_recent_interactions:
            self.recent_interactions = self.recent_interactions[-self.max_recent_interactions :]

    def get_recent_interactions_text(self) -> str:
        """Recent conversation window formatted for the prompt."""
        if not self.recent_interactions:
            return ""
        lines = ["### Recent Context:"]
        for interaction in self.recent_interactions:
            label = "User" if interaction.role == "user" else "Assistant"
            content = " ".join(interaction.content.split())
            if len(content) > self.recent_content_chars:
                content = content[: self.recent_content_chars] + "..."
            lines.append(f"{label}: {content}")
        return "\n".join(lines)

    def clear_interactions(self) -> None:
        """Drop the recent window (used after compression)."""
        self.recent_interactions = []

    # ----- metadata -----------------------------------------------------------

    def get_session_metadata_text(self) -> str:
        """Session metadata block for the prompt."""
        lines = ["### Session Information:", f"Session: {self.session_name}", f"ID: {self.session_id}"]
        if self.active_providers:
            lines.append("Providers: " + ", ".join(p.value.upper() for p in self.active_providers))
            for provider in self.active_providers:
                ctx = self.provider_contexts.get(provider)
                if ctx:
                    lines.append(f"  - {provider.value.upper()}: {ctx.label()}")
        if self.current_provider:
            lines.append(f"Current focus: {self.current_provider.value.upper()}")
        lines.append(f"Messages so far: {self.total_messages}")
        if self.compression_count:
            lines.append(f"Context compressions: {self.compression_count}")
        return "\n".join(lines)

    def assemble_context(self) -> str:
        """Everything except the base system prompt: metadata, recent turns, task hint."""
        sections = [self.get_session_metadata_text()]
        recent = self.get_recent_interactions_text()
        if recent:
            sections.append(recent)
        ctx = self.get_current_provider()
        if ctx and ctx.last_query_type:
            sections.append(f"### Current Task:\nAnalyzing {ctx.last_query_type} for {ctx.name.value.upper()}")
        return "\n\n".join(sections)

    def assemble_prompt_injection(self) -> str:
        """Base system prompt followed by the hot context."""
        return f"{self.system_prompt}\n\n{self.assemble_context()}"

    def update_query_type(self, query_type: str) -> None:
        """Track the kind of analysis the user is doing right now."""
        ctx = self.get_current_provider()
        if ctx:
            ctx.last_query_type = query_type
            ctx.last_query_time = datetime.now()

    # ----- counters -------------------------------------------------------------

    def increment_message_count(self, by: int = 1) -> None:
        """Bump the message counter."""
        self.total_messages += by

    def increment_compression_count(self) -> None:
        """Bump the compression counter."""
        self.compression_count += 1

    def get_session_stats(self) -> dict[str, Any]:
        """Statistics for status displays."""
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "llm_provider": self.llm_provider,
            "active_providers": [p.value for p in self.active_providers],
            "current_provider": self.current_provider.value if self.current_provider else None,
            "total_messages": self.total_messages,
            "compression_count": self.compression_count,
            "recent_interactions": len(self.recent_interactions),
            "created_at": self.created_at.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialisable snapshot."""
        return {
            **self.get_session_stats(),
            "providers": {
                provider.value: {
                    "account_id": ctx.account_id,
                    "account_name": ctx.account_name,
                    "region": ctx.region,
                    "last_query_type": ctx.last_query_type,
                }
                for provider, ctx in self.provider_contexts.items()
            },
        }

    def __repr__(self) -> str:
        providers = ", ".join(p.value.upper() for p in self.active_providers)
        return f"<HotMemory session={self.session_name!r} providers={providers} msgs={self.total_messages}>"
