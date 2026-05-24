"""
Cold Memory Layer - Session History & Retrieval
============================================
COLD MEMORY stores full session history in SQLite and retrieves
relevant chunks on demand via search.

- Full message history with metadata
- Full-text search capabilities
- Summarization before injection (token-efficient)
- Date range queries
- Provider-specific filtering

This is the "episodic recall" - relevant past experiences.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
from enum import Enum


class MessageRole(Enum):
    """Message roles"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class StoredMessage:
    """A message stored in cold memory"""

    id: str
    session_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    tokens: int = 0
    provider: Optional[str] = None  # "aws", "azure", "gcp", "do"
    analysis_id: Optional[str] = None  # Reference to analysis result
    tags: List[str] = field(default_factory=list)  # "cost", "forecast", "inventory"

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role.value,
            "content": self.content[:100] + "..."
            if len(self.content) > 100
            else self.content,
            "timestamp": self.timestamp.isoformat(),
            "tokens": self.tokens,
            "provider": self.provider,
            "tags": self.tags,
        }


@dataclass
class AnalysisResult:
    """Cached analysis result for quick retrieval"""

    id: str
    session_id: str
    timestamp: datetime
    query: str
    provider: str
    query_type: str  # "costs", "inventory", "forecast"
    result: Dict  # Structured analysis result
    tokens_used: int = 0

    def summary(self, max_chars: int = 200) -> str:
        """Get a brief summary of the analysis"""
        summary_text = f"[{self.query_type.upper()}] {self.query}"
        if len(summary_text) > max_chars:
            summary_text = summary_text[:max_chars] + "..."
        return summary_text


@dataclass
class SearchResult:
    """Result from a cold memory search"""

    message: StoredMessage
    relevance_score: float  # 0.0 to 1.0
    context_snippet: str  # Brief preview

    def __repr__(self) -> str:
        score_str = f"{self.relevance_score:.2f}"
        return f"<SearchResult rel={score_str} role={self.message.role.value}>"


class ColdMemory:
    """
    COLD MEMORY - Session history storage and retrieval.

    Simulates SQLite queries without actual DB (DB layer exists separately).
    This class handles:
    1. Storing messages with metadata
    2. Full-text search
    3. Summarization
    4. Retrieval strategies
    """

    def __init__(self, session_id: str):
        """
        Initialize cold memory for a session.

        Args:
            session_id: Session identifier
        """
        self.session_id = session_id
        self.messages: List[StoredMessage] = []
        self.analyses: List[AnalysisResult] = []
        self.retention_days: int = 14  # Roll window

    # ========== STORAGE ==========

    def add_message(
        self,
        msg_id: str,
        role: MessageRole,
        content: str,
        provider: Optional[str] = None,
        tags: Optional[List[str]] = None,
        tokens: int = 0,
    ) -> StoredMessage:
        """
        Add a message to cold memory.

        Args:
            msg_id: Unique message ID
            role: Message role (user/assistant/system)
            content: Message content
            provider: Cloud provider context
            tags: Search tags ("cost", "forecast", etc.)
            tokens: Token count

        Returns:
            Stored message object
        """
        message = StoredMessage(
            id=msg_id,
            session_id=self.session_id,
            role=role,
            content=content,
            timestamp=datetime.now(),
            tokens=tokens,
            provider=provider,
            tags=tags or [],
        )
        self.messages.append(message)
        return message

    def add_analysis(
        self,
        analysis_id: str,
        query: str,
        provider: str,
        query_type: str,
        result: Dict,
        tokens_used: int = 0,
    ) -> AnalysisResult:
        """
        Store an analysis result for quick recall.

        Args:
            analysis_id: Unique analysis ID
            query: Original query
            provider: Cloud provider
            query_type: Type of query ("costs", "inventory", "forecast")
            result: Structured analysis result
            tokens_used: Tokens consumed

        Returns:
            Analysis result object
        """
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

    # ========== SEARCH STRATEGIES ==========

    def search_by_content(
        self, query: str, limit: int = 5, provider_filter: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Full-text search for relevant messages.

        Simple implementation: keyword matching.
        For production, this would use SQLite FTS5 (Full-Text Search).

        Args:
            query: Search query
            limit: Max results
            provider_filter: Filter by provider

        Returns:
            List of search results ranked by relevance
        """
        query_lower = query.lower()
        keywords = query_lower.split()

        results = []

        # Score each message
        for message in self.messages:
            if provider_filter and message.provider != provider_filter:
                continue

            content_lower = message.content.lower()

            # Calculate relevance score
            score = 0.0

            # Exact match: highest score
            if query_lower in content_lower:
                score += 0.8

            # Keyword matching
            keyword_matches = sum(1 for kw in keywords if kw in content_lower)
            score += (keyword_matches / len(keywords)) * 0.5 if keywords else 0

            # Tag matching
            if any(tag in keywords for tag in message.tags):
                score += 0.3

            # Recency bonus (recent = higher)
            hours_ago = (datetime.now() - message.timestamp).total_seconds() / 3600
            recency_bonus = max(0, 1 - (hours_ago / 24))  # Decays over 24h
            score += recency_bonus * 0.2

            if score > 0:
                # Create snippet
                start = max(0, content_lower.find(query_lower) - 50)
                end = min(len(message.content), start + 200)
                snippet = message.content[start:end]

                results.append(
                    SearchResult(
                        message=message, relevance_score=score, context_snippet=snippet
                    )
                )

        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]

    def search_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        provider_filter: Optional[str] = None,
    ) -> List[StoredMessage]:
        """
        Retrieve messages within a date range.

        Args:
            start_date: Start of range
            end_date: End of range
            provider_filter: Filter by provider

        Returns:
            Matching messages
        """
        results = []
        for message in self.messages:
            if start_date <= message.timestamp <= end_date:
                if provider_filter is None or message.provider == provider_filter:
                    results.append(message)

        return sorted(results, key=lambda m: m.timestamp)

    def search_by_tag(self, tag: str, limit: int = 10) -> List[StoredMessage]:
        """
        Find messages with a specific tag.

        Args:
            tag: Tag to search for ("cost", "forecast", "inventory")
            limit: Max results

        Returns:
            Matching messages sorted by recency
        """
        results = [m for m in self.messages if tag in m.tags]
        results.sort(key=lambda m: m.timestamp, reverse=True)
        return results[:limit]

    def search_by_provider(self, provider: str, limit: int = 20) -> List[StoredMessage]:
        """Find messages related to a specific provider"""
        results = [m for m in self.messages if m.provider == provider]
        results.sort(key=lambda m: m.timestamp, reverse=True)
        return results[:limit]

    # ========== ANALYSIS RECALL ==========

    def find_similar_analyses(
        self, query_type: str, provider: str, limit: int = 3
    ) -> List[AnalysisResult]:
        """
        Find similar past analyses for context.

        Args:
            query_type: Type of analysis ("costs", "inventory", "forecast")
            provider: Cloud provider
            limit: Max results

        Returns:
            Similar analyses
        """
        results = [
            a
            for a in self.analyses
            if a.query_type == query_type and a.provider == provider
        ]
        results.sort(key=lambda a: a.timestamp, reverse=True)
        return results[:limit]

    # ========== SUMMARIZATION ==========

    def summarize_messages(
        self, messages: List[StoredMessage], max_tokens: int = 500
    ) -> str:
        """
        Summarize a set of messages for context injection.

        In production, this would use the LLM to summarize.
        Here: simple extractive summarization.

        Args:
            messages: Messages to summarize
            max_tokens: Max tokens in summary

        Returns:
            Summary text
        """
        if not messages:
            return ""

        # Extract key information
        summary_parts = []

        # Count messages by role
        user_msgs = [m for m in messages if m.role == MessageRole.USER]
        assistant_msgs = [m for m in messages if m.role == MessageRole.ASSISTANT]

        if user_msgs:
            summary_parts.append(f"User asked {len(user_msgs)} questions")
            if user_msgs[-1].tags:
                summary_parts.append(f"Focus areas: {', '.join(user_msgs[-1].tags)}")

        if assistant_msgs:
            summary_parts.append(f"Received {len(assistant_msgs)} analysis responses")

        # Get most recent message by each provider
        providers = set(m.provider for m in messages if m.provider)
        if providers:
            summary_parts.append(f"Analyzed providers: {', '.join(sorted(providers))}")

        # Get all tags
        all_tags = set()
        for m in messages:
            all_tags.update(m.tags)
        if all_tags:
            summary_parts.append(f"Topics: {', '.join(sorted(all_tags))}")

        return " | ".join(summary_parts)

    def get_context_summary(self) -> str:
        """
        Get a brief context summary of the entire session history.

        Returns:
            Summary text
        """
        lines = []
        lines.append("### Cold Memory Summary:")

        if not self.messages:
            lines.append("(No history)")
            return "\n".join(lines)

        lines.append(f"Total messages: {len(self.messages)}")
        lines.append(
            f"Date range: {self.messages[0].timestamp.date()} to {self.messages[-1].timestamp.date()}"
        )

        # Count by role
        user_count = sum(1 for m in self.messages if m.role == MessageRole.USER)
        assistant_count = sum(
            1 for m in self.messages if m.role == MessageRole.ASSISTANT
        )
        lines.append(f"Messages: {user_count} user, {assistant_count} assistant")

        # Providers
        providers = set(m.provider for m in self.messages if m.provider)
        if providers:
            lines.append(f"Providers: {', '.join(sorted(providers))}")

        # Recent analyses
        if self.analyses:
            lines.append(f"Analyses: {len(self.analyses)} stored")
            recent = self.analyses[-1]
            lines.append(f"Last: {recent.query_type} on {recent.provider}")

        return "\n".join(lines)

    # ========== RETENTION & CLEANUP ==========

    def get_old_messages(self, days: int = 14) -> List[StoredMessage]:
        """Get messages older than N days for archival"""
        cutoff = datetime.now() - timedelta(days=days)
        return [m for m in self.messages if m.timestamp < cutoff]

    def compress_old_messages(self, days: int = 7) -> Tuple[int, str]:
        """
        Compress old messages (for long sessions).

        Returns:
            (count_compressed, summary_text)
        """
        old = self.get_old_messages(days)
        if not old:
            return 0, ""

        summary = self.summarize_messages(old)
        # In production: remove old and add summary as single message
        return len(old), summary

    def prune_retention_window(self) -> int:
        """
        Remove messages outside retention window.

        Returns:
            Number of messages removed
        """
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        original_count = len(self.messages)
        self.messages = [m for m in self.messages if m.timestamp >= cutoff]
        return original_count - len(self.messages)

    # ========== STATISTICS ==========

    def get_stats(self) -> Dict:
        """
        Get cold memory statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "session_id": self.session_id,
            "total_messages": len(self.messages),
            "total_analyses": len(self.analyses),
            "message_breakdown": {
                "user": sum(1 for m in self.messages if m.role == MessageRole.USER),
                "assistant": sum(
                    1 for m in self.messages if m.role == MessageRole.ASSISTANT
                ),
            },
            "providers": list(set(m.provider for m in self.messages if m.provider)),
            "tags_used": list(set(tag for m in self.messages for tag in m.tags)),
            "total_tokens": sum(m.tokens for m in self.messages),
            "date_range": {
                "first": self.messages[0].timestamp.isoformat()
                if self.messages
                else None,
                "last": self.messages[-1].timestamp.isoformat()
                if self.messages
                else None,
            },
        }

    def __repr__(self) -> str:
        return f"<ColdMemory session={self.session_id} msgs={len(self.messages)} analyses={len(self.analyses)}>"


# ========== EXAMPLE USAGE ==========

if __name__ == "__main__":
    import json

    # Create cold memory
    cold = ColdMemory("sess_example_123")

    # Simulate some messages
    cold.add_message(
        "msg_001",
        MessageRole.USER,
        "What are my AWS costs?",
        provider="aws",
        tags=["cost", "analysis"],
    )
    cold.add_message(
        "msg_002",
        MessageRole.ASSISTANT,
        "Your AWS costs are: EC2 $2,341, RDS $891, S3 $234...",
        provider="aws",
        tags=["cost"],
    )
    cold.add_message(
        "msg_003",
        MessageRole.USER,
        "Compare with Azure",
        provider="azure",
        tags=["cost", "comparison"],
    )
    cold.add_message(
        "msg_004",
        MessageRole.ASSISTANT,
        "Azure costs: Compute $1,500, Storage $450...",
        provider="azure",
        tags=["cost"],
    )
    cold.add_message(
        "msg_005", MessageRole.USER, "Forecast next month", tags=["forecast"]
    )

    # Store analysis
    cold.add_analysis(
        "ana_001",
        "AWS cost breakdown",
        "aws",
        "costs",
        {"ec2": 2341, "rds": 891, "s3": 234},
    )

    print("=" * 60)
    print("COLD MEMORY TESTS")
    print("=" * 60)

    # Search
    print("\n1. Search for 'costs':")
    results = cold.search_by_content("costs")
    for r in results:
        print(
            f"   - {r.message.role.value}: {r.context_snippet[:60]}... (score: {r.relevance_score:.2f})"
        )

    # By tag
    print("\n2. Messages tagged 'cost':")
    cost_msgs = cold.search_by_tag("cost")
    for m in cost_msgs:
        print(f"   - {m.role.value}: {m.content[:50]}...")

    # By provider
    print("\n3. AWS messages:")
    aws_msgs = cold.search_by_provider("aws")
    for m in aws_msgs:
        print(f"   - {m.role.value}: {m.content[:50]}...")

    # Summarize
    print("\n4. Summary:")
    summary = cold.summarize_messages(cold.messages)
    print(f"   {summary}")

    # Stats
    print("\n5. Statistics:")
    print(json.dumps(cold.get_stats(), indent=2, default=str))

    # Context summary
    print("\n6. Context Summary:")
    print(cold.get_context_summary())
