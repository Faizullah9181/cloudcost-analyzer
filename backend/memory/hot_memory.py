"""
Hot Memory Layer - Prompt Management
============================================
HOT MEMORY keeps the system prompt + immediate context always available.
- Always injected into every LLM call
- Tiny (500-1000 tokens)
- Session-scoped (recreated per session)
- Fast (no database lookups)

Key Components:
1. System Prompt (core instructions)
2. Session Metadata (provider, account, etc.)
3. Recent Interactions (last 2-3 messages for context)
4. Current Provider Context (current cloud provider state)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class CloudProvider(Enum):
    """Supported cloud providers"""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    DIGITALOCEAN = "digitalocean"


@dataclass
class ProviderContext:
    """Current context for a cloud provider"""

    name: CloudProvider
    account_id: str
    account_name: Optional[str] = None
    region: Optional[str] = None
    authenticated: bool = False
    last_query_type: Optional[str] = None  # "costs", "inventory", "forecast", etc.
    last_query_time: Optional[datetime] = None


@dataclass
class RecentInteraction:
    """Recent user/assistant interaction for context"""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    tokens: int = 0


@dataclass
class HotMemory:
    """
    HOT MEMORY - Always available prompt context.

    Contains:
    - System instructions
    - Session metadata
    - Active providers
    - Recent interactions (2-3 messages)
    - Current context
    """

    session_id: str
    session_name: str

    # Core system instructions
    system_prompt: str

    # Session metadata
    active_providers: List[CloudProvider] = field(default_factory=list)
    current_provider: Optional[CloudProvider] = None
    llm_provider: str = "bedrock"
    created_at: datetime = field(default_factory=datetime.now)

    # Provider-specific contexts
    provider_contexts: Dict[CloudProvider, ProviderContext] = field(
        default_factory=dict
    )

    # Recent interactions (keep only 2-3)
    recent_interactions: List[RecentInteraction] = field(default_factory=list)
    max_recent_interactions: int = 3

    # Session statistics
    total_messages: int = 0
    session_duration_minutes: int = 0
    compression_count: int = 0

    def __post_init__(self):
        """Validate hot memory on creation"""
        if not self.system_prompt:
            self.system_prompt = self._default_system_prompt()

    # ========== SYSTEM PROMPT ==========

    @staticmethod
    def _default_system_prompt() -> str:
        """Default system prompt for cloud cost analysis"""
        return """You are Shimo, an expert cloud cost analytics agent.

Your role:
- Analyze cloud infrastructure costs across multiple providers (AWS, Azure, GCP, DigitalOcean)
- Identify cost optimization opportunities
- Provide actionable recommendations
- Track spending trends and patterns
- Forecast future costs

Key capabilities:
1. COST ANALYSIS - Break down costs by service, region, or tag
2. TREND ANALYSIS - Show daily/weekly/monthly trends
3. RESOURCE INVENTORY - List and categorize resources
4. OPTIMIZATION - Recommend cost-saving strategies
5. FORECASTING - Predict future spending

When analyzing costs:
- Always show data in a structured format (tables, comparisons, trends)
- Include percentage breakdowns and top items
- Highlight unusual spikes or savings opportunities
- Provide specific, actionable recommendations
- Compare across providers when multi-cloud is enabled

Session Context:
- You have access to real-time cost data through cloud provider APIs
- Each analysis retrieves fresh data from the providers
- Long sessions are supported with automatic context compression
- You can access previous analyses from this session's memory

Respond in a professional, data-driven manner.
Include specific numbers, percentages, and actionable insights."""

    def set_system_prompt(self, prompt: str) -> None:
        """
        Update the system prompt for this session.

        Args:
            prompt: New system prompt text
        """
        self.system_prompt = prompt

    def get_system_prompt(self) -> str:
        """
        Get the current system prompt.

        Returns:
            Complete system prompt with instructions
        """
        return self.system_prompt

    # ========== PROVIDER MANAGEMENT ==========

    def add_provider(
        self,
        provider: CloudProvider,
        account_id: str,
        account_name: Optional[str] = None,
        region: Optional[str] = None,
    ) -> None:
        """
        Add an active cloud provider to this session.

        Args:
            provider: Cloud provider (AWS, Azure, GCP, DigitalOcean)
            account_id: Provider-specific account ID
            account_name: Human-readable account name
            region: Default region/location
        """
        if provider not in self.active_providers:
            self.active_providers.append(provider)

        self.provider_contexts[provider] = ProviderContext(
            name=provider,
            account_id=account_id,
            account_name=account_name,
            region=region,
            authenticated=True,
        )

    def set_current_provider(self, provider: CloudProvider) -> None:
        """
        Set the current active provider.

        Args:
            provider: Provider to set as current

        Raises:
            ValueError: If provider not in active_providers
        """
        if provider not in self.active_providers:
            raise ValueError(f"{provider.value} not in active providers")
        self.current_provider = provider

    def get_current_provider(self) -> Optional[ProviderContext]:
        """Get the current active provider context"""
        if self.current_provider is None:
            return None
        return self.provider_contexts.get(self.current_provider)

    def get_provider_context(
        self, provider: CloudProvider
    ) -> Optional[ProviderContext]:
        """Get context for a specific provider"""
        return self.provider_contexts.get(provider)

    # ========== RECENT INTERACTIONS ==========

    def add_interaction(self, role: str, content: str, tokens: int = 0) -> None:
        """
        Add a recent interaction to the hot memory.
        Keeps only the last N interactions (default 3).

        Args:
            role: "user" or "assistant"
            content: Message content
            tokens: Approximate token count
        """
        interaction = RecentInteraction(
            role=role, content=content, timestamp=datetime.now(), tokens=tokens
        )
        self.recent_interactions.append(interaction)

        # Keep only recent interactions
        if len(self.recent_interactions) > self.max_recent_interactions:
            self.recent_interactions = self.recent_interactions[
                -self.max_recent_interactions :
            ]

    def get_recent_interactions_text(self) -> str:
        """
        Get formatted text of recent interactions for prompt injection.

        Returns:
            Formatted string with recent conversation context
        """
        if not self.recent_interactions:
            return ""

        lines = ["### Recent Context:", ""]
        for interaction in self.recent_interactions[-2:]:  # Show last 2
            role_label = "User" if interaction.role == "user" else "Assistant"
            # Truncate long messages
            content = interaction.content
            if len(content) > 200:
                content = content[:200] + "..."
            lines.append(f"{role_label}: {content}")

        return "\n".join(lines)

    def clear_interactions(self) -> None:
        """Clear recent interactions (for long sessions)"""
        self.recent_interactions = []

    # ========== SESSION METADATA ==========

    def get_session_metadata_text(self) -> str:
        """
        Get formatted session metadata for injection into prompt.

        Returns:
            Formatted string with session info
        """
        metadata = [
            "### Session Information:",
            f"Session: {self.session_name}",
            f"ID: {self.session_id}",
        ]

        # Provider info
        if self.active_providers:
            provider_list = ", ".join([p.value.upper() for p in self.active_providers])
            metadata.append(f"Providers: {provider_list}")

        # Current provider
        if self.current_provider:
            ctx = self.provider_contexts[self.current_provider]
            provider_info = f"  Account: {ctx.account_id}"
            if ctx.account_name:
                provider_info += f" ({ctx.account_name})"
            if ctx.region:
                provider_info += f" | Region: {ctx.region}"
            metadata.append(
                f"Current: {self.current_provider.value.upper()}{provider_info}"
            )

        # Stats
        metadata.append(f"Messages: {self.total_messages}")
        if self.compression_count > 0:
            metadata.append(f"Compressions: {self.compression_count}")

        return "\n".join(metadata)

    # ========== PROMPT ASSEMBLY ==========

    def assemble_prompt_injection(self) -> str:
        """
        Assemble the complete HOT MEMORY injection for the prompt.
        This is what gets injected into every LLM call.

        Returns:
            Complete prompt injection text (500-1000 tokens)
        """
        sections = []

        # 1. System prompt (core)
        sections.append(self.system_prompt)

        # 2. Session metadata
        sections.append("")
        sections.append(self.get_session_metadata_text())

        # 3. Recent interactions (if any)
        recent = self.get_recent_interactions_text()
        if recent:
            sections.append("")
            sections.append(recent)

        # 4. Current task guidance
        if self.current_provider:
            ctx = self.provider_contexts[self.current_provider]
            if ctx.last_query_type:
                sections.append("\n### Current Task:")
                sections.append(
                    f"Analyzing {ctx.last_query_type} for {self.current_provider.value.upper()}"
                )

        return "\n".join(sections)

    def update_query_type(self, query_type: str) -> None:
        """
        Track the type of query being asked (for recent context).

        Args:
            query_type: Type of query ("costs", "inventory", "forecast", etc.)
        """
        if self.current_provider:
            ctx = self.provider_contexts[self.current_provider]
            ctx.last_query_type = query_type
            ctx.last_query_time = datetime.now()

    # ========== SESSION TRACKING ==========

    def increment_message_count(self) -> None:
        """Increment total message count"""
        self.total_messages += 1

    def increment_compression_count(self) -> None:
        """Increment compression count (for tracking long sessions)"""
        self.compression_count += 1

    def get_session_stats(self) -> Dict:
        """
        Get session statistics.

        Returns:
            Dictionary with session stats
        """
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "llm_provider": self.llm_provider,
            "active_providers": [p.value for p in self.active_providers],
            "current_provider": self.current_provider.value
            if self.current_provider
            else None,
            "total_messages": self.total_messages,
            "compression_count": self.compression_count,
            "recent_interactions": len(self.recent_interactions),
            "created_at": self.created_at.isoformat(),
        }

    # ========== SERIALIZATION ==========

    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "system_prompt": self.system_prompt[:100] + "...",  # Truncate
            "active_providers": [p.value for p in self.active_providers],
            "current_provider": self.current_provider.value
            if self.current_provider
            else None,
            "llm_provider": self.llm_provider,
            "total_messages": self.total_messages,
            "compression_count": self.compression_count,
            "stats": self.get_session_stats(),
        }

    def __repr__(self) -> str:
        """String representation"""
        providers = ", ".join([p.value.upper() for p in self.active_providers])
        return (
            f"<HotMemory session={self.session_name} "
            f"providers={providers} "
            f"msgs={self.total_messages}>"
        )


# ========== EXAMPLE USAGE ==========

if __name__ == "__main__":
    import json

    # Create a session
    hot_mem = HotMemory(
        session_id="sess_example_123", session_name="Multi-Cloud Q2 Analysis"
    )

    # Add providers
    hot_mem.add_provider(
        CloudProvider.AWS,
        account_id="123456789012",
        account_name="Production",
        region="us-east-1",
    )
    hot_mem.add_provider(
        CloudProvider.AZURE, account_id="sub-abc123", account_name="Azure Enterprise"
    )

    # Set current provider
    hot_mem.set_current_provider(CloudProvider.AWS)

    # Add some interactions
    hot_mem.add_interaction("user", "What are my AWS costs?")
    hot_mem.add_interaction("assistant", "Based on your usage...")
    hot_mem.add_interaction("user", "Forecast next month")

    # Update query type
    hot_mem.update_query_type("forecast")

    # Increment message count
    hot_mem.increment_message_count()
    hot_mem.increment_message_count()
    hot_mem.increment_message_count()

    # Get assembled prompt injection
    print("=" * 60)
    print("ASSEMBLED PROMPT INJECTION:")
    print("=" * 60)
    print(hot_mem.assemble_prompt_injection())

    print("\n" + "=" * 60)
    print("SESSION STATS:")
    print("=" * 60)
    print(json.dumps(hot_mem.get_session_stats(), indent=2))
