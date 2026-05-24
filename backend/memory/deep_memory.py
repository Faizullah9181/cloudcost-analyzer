"""
Deep Memory Layer - User Modeling (Optional)
============================================
DEEP MEMORY stores cross-session user preferences and patterns.
This layer is optional and enables personalization.

- User preferences (favorite LLM, report style, etc.)
- Historical patterns (common queries, preferred providers)
- User traits (timezone, language, expertise level)
- Behavioral patterns

Inspired by Honcho's user modeling approach.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import json


class ReportStyle(Enum):
    """User report style preference"""

    DETAILED = "detailed"
    SUMMARY = "summary"
    TECHNICAL = "technical"
    EXECUTIVE = "executive"


class ExpertiseLevel(Enum):
    """User expertise with cloud platforms"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class UserTrait:
    """A user trait or preference"""

    name: str
    value: any
    confidence: float = 0.5  # 0.0 to 1.0 (how confident are we?)
    updated_at: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return f"{self.name}={self.value} (confidence: {self.confidence:.1f})"


@dataclass
class UserPattern:
    """A behavioral pattern observed in user"""

    pattern_type: str  # "common_query", "preferred_provider", "time_pattern"
    pattern_value: str
    frequency: int = 1
    confidence: float = 0.5
    last_seen: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return f"{self.pattern_type}:{self.pattern_value} (freq={self.frequency})"


class DeepMemory:
    """
    DEEP MEMORY - User modeling across sessions.

    Stores:
    - User preferences and settings
    - Historical patterns and behaviors
    - User traits (expertise, timezone, etc.)
    - Learning from past interactions

    This is optional but enables better personalization.
    """

    def __init__(self, user_id: str):
        """
        Initialize deep memory for a user.

        Args:
            user_id: Unique user identifier
        """
        self.user_id = user_id

        # Preferences
        self.preferred_llm: str = "bedrock"
        self.report_style: ReportStyle = ReportStyle.DETAILED
        self.preferred_providers: List[str] = []
        self.timezone: str = "UTC"
        self.language: str = "en"

        # Traits
        self.traits: Dict[str, UserTrait] = {}

        # Patterns
        self.patterns: Dict[str, List[UserPattern]] = {
            "common_queries": [],
            "preferred_providers": [],
            "time_patterns": [],
            "cost_concerns": [],
        }

        # Statistics
        self.total_sessions: int = 0
        self.total_queries: int = 0
        self.created_at: datetime = datetime.now()
        self.last_active: datetime = datetime.now()

    # ========== PREFERENCES ==========

    def set_preferred_llm(self, llm: str) -> None:
        """Set preferred LLM provider"""
        self.preferred_llm = llm
        self._add_trait("preferred_llm", llm)

    def set_report_style(self, style: ReportStyle) -> None:
        """Set preferred report style"""
        self.report_style = style
        self._add_trait("report_style", style.value)

    def set_timezone(self, timezone: str) -> None:
        """Set user timezone"""
        self.timezone = timezone
        self._add_trait("timezone", timezone)

    def set_preferred_providers(self, providers: List[str]) -> None:
        """Set preferred cloud providers"""
        self.preferred_providers = providers
        self._add_trait("preferred_providers", ",".join(providers))

    def set_expertise_level(self, level: ExpertiseLevel) -> None:
        """Set user expertise level"""
        self._add_trait("expertise_level", level.value)

    # ========== TRAIT MANAGEMENT ==========

    def _add_trait(self, name: str, value: any, confidence: float = 0.8) -> None:
        """Add or update a user trait"""
        if name in self.traits:
            # Update confidence based on consistency
            old = self.traits[name]
            if old.value == value:
                # Same value: increase confidence
                confidence = min(1.0, old.confidence + 0.1)
            else:
                # Different value: reset confidence
                confidence = 0.5

        self.traits[name] = UserTrait(name=name, value=value, confidence=confidence)

    def get_trait(self, name: str) -> Optional[UserTrait]:
        """Get a specific trait"""
        return self.traits.get(name)

    def get_all_traits(self) -> Dict[str, UserTrait]:
        """Get all traits"""
        return self.traits.copy()

    def get_high_confidence_traits(self, min_confidence: float = 0.7) -> Dict[str, any]:
        """Get only high-confidence traits"""
        return {
            name: trait.value
            for name, trait in self.traits.items()
            if trait.confidence >= min_confidence
        }

    # ========== PATTERN TRACKING ==========

    def observe_pattern(
        self, pattern_type: str, pattern_value: str, confidence: float = 0.6
    ) -> None:
        """
        Record an observed pattern in user behavior.

        Args:
            pattern_type: Type of pattern
            pattern_value: Pattern value
            confidence: How confident are we?
        """
        if pattern_type not in self.patterns:
            self.patterns[pattern_type] = []

        # Check if we've seen this pattern
        for pattern in self.patterns[pattern_type]:
            if pattern.pattern_value == pattern_value:
                pattern.frequency += 1
                pattern.last_seen = datetime.now()
                # Increase confidence
                pattern.confidence = min(1.0, pattern.confidence + 0.1)
                return

        # New pattern
        self.patterns[pattern_type].append(
            UserPattern(
                pattern_type=pattern_type,
                pattern_value=pattern_value,
                frequency=1,
                confidence=confidence,
            )
        )

    def observe_query(self, query: str) -> None:
        """Record that user asked a query"""
        self.total_queries += 1
        self.observe_pattern("common_queries", query, confidence=0.5)

    def observe_provider_use(self, provider: str) -> None:
        """Record provider usage"""
        self.observe_pattern("preferred_providers", provider, confidence=0.7)

    def observe_cost_concern(self, concern: str) -> None:
        """Record cost-related concerns"""
        self.observe_pattern("cost_concerns", concern, confidence=0.6)

    def get_common_patterns(
        self, pattern_type: str, limit: int = 5
    ) -> List[UserPattern]:
        """Get most common patterns of a type, sorted by frequency"""
        patterns = self.patterns.get(pattern_type, [])
        sorted_patterns = sorted(
            patterns, key=lambda p: (p.frequency, p.confidence), reverse=True
        )
        return sorted_patterns[:limit]

    def get_common_queries(self) -> List[str]:
        """Get top common queries"""
        patterns = self.get_common_patterns("common_queries", limit=5)
        return [p.pattern_value for p in patterns]

    def get_preferred_providers(self) -> List[str]:
        """Get user's preferred providers based on patterns"""
        patterns = self.get_common_patterns("preferred_providers", limit=3)
        return [p.pattern_value for p in patterns]

    # ========== USER CONTEXT GENERATION ==========

    def get_user_context_injection(self) -> str:
        """
        Generate user context for injection into prompt.

        Returns:
            Formatted user context
        """
        lines = ["### User Profile:"]

        # Preferences
        lines.append(f"LLM: {self.preferred_llm}")
        lines.append(f"Report style: {self.report_style.value}")

        # Traits
        high_conf_traits = self.get_high_confidence_traits(min_confidence=0.7)
        if high_conf_traits:
            for name, value in high_conf_traits.items():
                if name not in ["preferred_llm", "report_style"]:
                    lines.append(f"{name.replace('_', ' ').title()}: {value}")

        # Patterns
        common_queries = self.get_common_queries()
        if common_queries:
            lines.append(f"\nCommon topics: {', '.join(common_queries[:2])}")

        preferred = self.get_preferred_providers()
        if preferred:
            lines.append(f"Preferred providers: {', '.join(preferred)}")

        return "\n".join(lines)

    # ========== SESSION TRACKING ==========

    def record_session_start(self) -> None:
        """Record that a new session started"""
        self.total_sessions += 1
        self.last_active = datetime.now()

    def record_session_end(self) -> None:
        """Record that session ended"""
        self.last_active = datetime.now()

    # ========== LEARNING & ADAPTATION ==========

    def infer_preferences_from_session(self, session_data: Dict) -> None:
        """
        Learn user preferences from a completed session.

        Args:
            session_data: Session information
        """
        # Infer LLM preference
        if "llm_provider" in session_data:
            self.set_preferred_llm(session_data["llm_provider"])

        # Infer providers
        if "providers_used" in session_data:
            for provider in session_data["providers_used"]:
                self.observe_provider_use(provider)

        # Infer query patterns
        if "queries" in session_data:
            for query in session_data["queries"]:
                self.observe_query(query)

        # Infer concerns
        if "cost_concerns" in session_data:
            for concern in session_data["cost_concerns"]:
                self.observe_cost_concern(concern)

    # ========== RECOMMENDATIONS ==========

    def get_recommendations(self) -> Dict:
        """
        Generate recommendations based on user patterns.

        Returns:
            Recommendations dict
        """
        recommendations = {}

        # Suggest analysis based on patterns
        if self.total_queries > 5:
            common = self.get_common_queries()
            if common:
                recommendations["suggested_analysis"] = common[0]

        # Suggest providers
        if self.get_preferred_providers():
            recommendations["suggested_providers"] = self.get_preferred_providers()

        # Suggest optimization based on cost concerns
        cost_concerns = self.get_common_patterns("cost_concerns", limit=2)
        if cost_concerns:
            recommendations["focus_areas"] = [p.pattern_value for p in cost_concerns]

        return recommendations

    # ========== STATISTICS ==========

    def get_stats(self) -> Dict:
        """Get user statistics"""
        return {
            "user_id": self.user_id,
            "total_sessions": self.total_sessions,
            "total_queries": self.total_queries,
            "traits": len(self.traits),
            "high_confidence_traits": len(self.get_high_confidence_traits()),
            "patterns": {ptype: len(plist) for ptype, plist in self.patterns.items()},
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
        }

    def get_profile_summary(self) -> str:
        """Get a summary of user profile"""
        lines = []
        lines.append(f"User: {self.user_id}")
        lines.append(f"Sessions: {self.total_sessions}")
        lines.append(f"Queries: {self.total_queries}")

        if self.get_preferred_providers():
            lines.append(f"Providers: {', '.join(self.get_preferred_providers())}")

        if self.get_common_queries():
            lines.append(f"Common topics: {', '.join(self.get_common_queries()[:2])}")

        return " | ".join(lines)

    def __repr__(self) -> str:
        return (
            f"<DeepMemory user={self.user_id} "
            f"sessions={self.total_sessions} "
            f"queries={self.total_queries}>"
        )


# ========== EXAMPLE USAGE ==========

if __name__ == "__main__":
    import json

    # Create user
    deep_mem = DeepMemory("user_johndoe_123")

    print("=" * 60)
    print("DEEP MEMORY (USER MODELING) TESTS")
    print("=" * 60)

    # Set preferences
    deep_mem.set_preferred_llm("bedrock")
    deep_mem.set_report_style(ReportStyle.DETAILED)
    deep_mem.set_timezone("America/New_York")
    deep_mem.set_expertise_level(ExpertiseLevel.INTERMEDIATE)

    print("\n1. Preferences set:")
    print(f"   LLM: {deep_mem.preferred_llm}")
    print(f"   Style: {deep_mem.report_style.value}")
    print(f"   Timezone: {deep_mem.timezone}")

    # Simulate sessions
    print("\n2. Simulating user sessions:")

    deep_mem.record_session_start()
    deep_mem.observe_query("What are my EC2 costs?")
    deep_mem.observe_provider_use("aws")
    deep_mem.observe_cost_concern("EC2 spending too high")
    deep_mem.total_queries += 1
    deep_mem.record_session_end()
    print("   Session 1: EC2 cost analysis")

    deep_mem.record_session_start()
    deep_mem.observe_query("AWS vs Azure comparison")
    deep_mem.observe_provider_use("aws")
    deep_mem.observe_provider_use("azure")
    deep_mem.observe_cost_concern("Multi-cloud cost tracking")
    deep_mem.total_queries += 1
    deep_mem.record_session_end()
    print("   Session 2: Multi-cloud comparison")

    deep_mem.record_session_start()
    deep_mem.observe_query("Forecast EC2 costs next month")
    deep_mem.observe_provider_use("aws")
    deep_mem.total_queries += 1
    deep_mem.record_session_end()
    print("   Session 3: Cost forecast")

    # Show patterns
    print("\n3. Learned Patterns:")
    print(f"   Preferred providers: {deep_mem.get_preferred_providers()}")
    print(f"   Common queries: {deep_mem.get_common_queries()}")
    print(
        f"   Cost concerns: {[p.pattern_value for p in deep_mem.get_common_patterns('cost_concerns')]}"
    )

    # Get context
    print("\n4. User Context Injection:")
    print(deep_mem.get_user_context_injection())

    # Recommendations
    print("\n5. Recommendations:")
    recs = deep_mem.get_recommendations()
    for key, value in recs.items():
        print(f"   {key}: {value}")

    # Stats
    print("\n6. Statistics:")
    print(json.dumps(deep_mem.get_stats(), indent=2, default=str))
