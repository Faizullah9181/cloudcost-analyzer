"""
Deep Memory Layer - User Modeling (optional)
============================================
DEEP MEMORY tracks cross-session preferences and behaviour for a user. The
harness persists it to the ``user_profiles`` table via ``to_dict``/``from_dict``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ReportStyle(str, Enum):
    """User report style preference."""

    DETAILED = "detailed"
    SUMMARY = "summary"
    TECHNICAL = "technical"
    EXECUTIVE = "executive"


class ExpertiseLevel(str, Enum):
    """User expertise with cloud platforms."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class UserTrait:
    """A user trait or preference with a confidence score."""

    name: str
    value: Any
    confidence: float = 0.5
    updated_at: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return f"{self.name}={self.value} (confidence: {self.confidence:.1f})"


@dataclass
class UserPattern:
    """A behavioural pattern observed for a user."""

    pattern_type: str
    pattern_value: str
    frequency: int = 1
    confidence: float = 0.5
    last_seen: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return f"{self.pattern_type}:{self.pattern_value} (freq={self.frequency})"


_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cost analysis": ("cost", "spend", "spending", "bill", "charge", "expensive"),
    "forecasting": ("forecast", "predict", "projection", "next month", "estimate"),
    "comparison": ("compare", "comparison", "versus", " vs "),
    "inventory": ("inventory", "resources", "instances", "buckets", "list all"),
    "optimization": ("optimi", "save", "saving", "reduce", "idle", "waste", "cheaper"),
    "trends": ("trend", "daily", "over time", "history", "growth"),
    "tagging": ("tag", "environment", "team", "project"),
}

_PROVIDER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "aws": ("aws", "amazon", "ec2", "s3", "rds", "lambda"),
    "azure": ("azure", "microsoft"),
    "gcp": ("gcp", "google", "bigquery"),
    "digitalocean": ("digitalocean", "digital ocean", "droplet"),
}


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now()


class DeepMemory:
    """Cross-session user model."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.preferred_llm: str = ""
        self.report_style: ReportStyle = ReportStyle.DETAILED
        self.preferred_providers: list[str] = []
        self.timezone: str = "UTC"
        self.language: str = "en"
        self.traits: dict[str, UserTrait] = {}
        self.patterns: dict[str, list[UserPattern]] = {
            "common_topics": [],
            "preferred_providers": [],
            "cost_concerns": [],
        }
        self.total_sessions: int = 0
        self.total_queries: int = 0
        self.created_at: datetime = datetime.now()
        self.last_active: datetime = datetime.now()

    # ----- preferences ------------------------------------------------------------

    def set_preferred_llm(self, llm: str) -> None:
        """Remember the LLM the user likes."""
        self.preferred_llm = llm
        self._add_trait("preferred_llm", llm)

    def set_report_style(self, style: ReportStyle | str) -> None:
        """Remember the report style."""
        self.report_style = ReportStyle(style)
        self._add_trait("report_style", self.report_style.value)

    def set_timezone(self, timezone: str) -> None:
        """Remember the user's timezone."""
        self.timezone = timezone
        self._add_trait("timezone", timezone)

    def set_preferred_providers(self, providers: list[str]) -> None:
        """Remember preferred providers explicitly."""
        self.preferred_providers = list(providers)
        self._add_trait("preferred_providers", ",".join(providers))

    def set_expertise_level(self, level: ExpertiseLevel | str) -> None:
        """Remember the expertise level."""
        self._add_trait("expertise_level", ExpertiseLevel(level).value)

    # ----- traits -----------------------------------------------------------------------

    def _add_trait(self, name: str, value: Any, confidence: float = 0.8) -> None:
        if name in self.traits:
            old = self.traits[name]
            confidence = min(1.0, old.confidence + 0.1) if old.value == value else 0.5
        self.traits[name] = UserTrait(name=name, value=value, confidence=confidence)

    def get_trait(self, name: str) -> UserTrait | None:
        """Look up a trait."""
        return self.traits.get(name)

    def get_all_traits(self) -> dict[str, UserTrait]:
        """All traits."""
        return dict(self.traits)

    def get_high_confidence_traits(self, min_confidence: float = 0.7) -> dict[str, Any]:
        """Traits we are reasonably sure about."""
        return {name: t.value for name, t in self.traits.items() if t.confidence >= min_confidence}

    # ----- patterns ------------------------------------------------------------------------

    def observe_pattern(self, pattern_type: str, pattern_value: str, confidence: float = 0.6) -> None:
        """Record (or reinforce) an observed pattern."""
        bucket = self.patterns.setdefault(pattern_type, [])
        for pattern in bucket:
            if pattern.pattern_value == pattern_value:
                pattern.frequency += 1
                pattern.last_seen = datetime.now()
                pattern.confidence = min(1.0, pattern.confidence + 0.1)
                return
        bucket.append(UserPattern(pattern_type=pattern_type, pattern_value=pattern_value, confidence=confidence))

    def observe_query(self, query: str) -> None:
        """Learn topics and providers from a natural-language query."""
        self.total_queries += 1
        self.last_active = datetime.now()
        lowered = f" {query.lower()} "
        for topic, keywords in _TOPIC_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                self.observe_pattern("common_topics", topic, confidence=0.5)
        for provider, keywords in _PROVIDER_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                self.observe_provider_use(provider)

    def observe_provider_use(self, provider: str) -> None:
        """Record that the user worked with a provider."""
        self.observe_pattern("preferred_providers", provider, confidence=0.7)

    def observe_cost_concern(self, concern: str) -> None:
        """Record a cost concern."""
        self.observe_pattern("cost_concerns", concern, confidence=0.6)

    def get_common_patterns(self, pattern_type: str, limit: int = 5) -> list[UserPattern]:
        """Most frequent patterns of a type."""
        patterns = self.patterns.get(pattern_type, [])
        return sorted(patterns, key=lambda p: (p.frequency, p.confidence), reverse=True)[:limit]

    def get_common_topics(self) -> list[str]:
        """Most common topics."""
        return [p.pattern_value for p in self.get_common_patterns("common_topics", limit=5)]

    def get_common_queries(self) -> list[str]:
        """Alias kept for compatibility."""
        return self.get_common_topics()

    def get_preferred_providers(self) -> list[str]:
        """Providers the user works with most."""
        if self.preferred_providers:
            return list(self.preferred_providers)
        return [p.pattern_value for p in self.get_common_patterns("preferred_providers", limit=3)]

    # ----- prompt injection -------------------------------------------------------------------

    def get_user_context_injection(self) -> str:
        """User profile block for the prompt, or empty when nothing useful is known."""
        lines: list[str] = []
        if self.report_style != ReportStyle.DETAILED:
            lines.append(f"Preferred report style: {self.report_style.value}")
        for name, value in self.get_high_confidence_traits().items():
            if name not in ("preferred_llm", "report_style"):
                lines.append(f"{name.replace('_', ' ').title()}: {value}")
        topics = self.get_common_topics()[:3]
        if topics:
            lines.append("Frequent topics: " + ", ".join(topics))
        providers = self.get_preferred_providers()
        if providers:
            lines.append("Frequently analysed providers: " + ", ".join(providers))
        if self.total_sessions > 1:
            lines.append(f"Returning user ({self.total_sessions} sessions, {self.total_queries} queries)")
        if not lines:
            return ""
        return "### User Profile:\n" + "\n".join(lines)

    # ----- sessions ---------------------------------------------------------------------------

    def record_session_start(self) -> None:
        """Count a new session."""
        self.total_sessions += 1
        self.last_active = datetime.now()

    def record_session_end(self) -> None:
        """Mark activity at session end."""
        self.last_active = datetime.now()

    def infer_preferences_from_session(self, session_data: dict[str, Any]) -> None:
        """Learn from a finished session's metadata."""
        if session_data.get("llm_provider"):
            self.set_preferred_llm(session_data["llm_provider"])
        for provider in session_data.get("providers_used", []):
            self.observe_provider_use(provider)
        for query in session_data.get("queries", []):
            self.observe_query(query)
        for concern in session_data.get("cost_concerns", []):
            self.observe_cost_concern(concern)

    def get_recommendations(self) -> dict[str, Any]:
        """Suggestions derived from patterns."""
        recommendations: dict[str, Any] = {}
        topics = self.get_common_topics()
        if self.total_queries > 5 and topics:
            recommendations["suggested_analysis"] = topics[0]
        providers = self.get_preferred_providers()
        if providers:
            recommendations["suggested_providers"] = providers
        concerns = self.get_common_patterns("cost_concerns", limit=2)
        if concerns:
            recommendations["focus_areas"] = [p.pattern_value for p in concerns]
        return recommendations

    # ----- persistence ----------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialisable snapshot for the ``user_profiles`` table."""
        return {
            "user_id": self.user_id,
            "preferred_llm": self.preferred_llm,
            "report_style": self.report_style.value,
            "preferred_providers": list(self.preferred_providers),
            "timezone": self.timezone,
            "language": self.language,
            "traits": {
                name: {"value": t.value, "confidence": t.confidence, "updated_at": t.updated_at.isoformat()}
                for name, t in self.traits.items()
            },
            "patterns": {
                ptype: [
                    {
                        "value": p.pattern_value,
                        "frequency": p.frequency,
                        "confidence": p.confidence,
                        "last_seen": p.last_seen.isoformat(),
                    }
                    for p in plist
                ]
                for ptype, plist in self.patterns.items()
            },
            "total_sessions": self.total_sessions,
            "total_queries": self.total_queries,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
        }

    @classmethod
    def from_dict(cls, user_id: str, data: dict[str, Any] | None) -> "DeepMemory":
        """Rebuild from a persisted snapshot (tolerates missing keys)."""
        memory = cls(user_id)
        if not data:
            return memory
        memory.preferred_llm = str(data.get("preferred_llm") or "")
        try:
            memory.report_style = ReportStyle(data.get("report_style") or "detailed")
        except ValueError:
            memory.report_style = ReportStyle.DETAILED
        memory.preferred_providers = list(data.get("preferred_providers") or [])
        memory.timezone = str(data.get("timezone") or "UTC")
        memory.language = str(data.get("language") or "en")
        for name, trait in (data.get("traits") or {}).items():
            memory.traits[name] = UserTrait(
                name=name,
                value=trait.get("value"),
                confidence=float(trait.get("confidence", 0.5)),
                updated_at=_parse_dt(trait.get("updated_at")),
            )
        for ptype, plist in (data.get("patterns") or {}).items():
            memory.patterns[ptype] = [
                UserPattern(
                    pattern_type=ptype,
                    pattern_value=str(p.get("value", "")),
                    frequency=int(p.get("frequency", 1)),
                    confidence=float(p.get("confidence", 0.5)),
                    last_seen=_parse_dt(p.get("last_seen")),
                )
                for p in plist
            ]
        memory.total_sessions = int(data.get("total_sessions") or 0)
        memory.total_queries = int(data.get("total_queries") or 0)
        memory.created_at = _parse_dt(data.get("created_at"))
        memory.last_active = _parse_dt(data.get("last_active"))
        return memory

    # ----- stats -------------------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Statistics for status displays."""
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
        """One-line profile description."""
        parts = [f"User: {self.user_id}", f"Sessions: {self.total_sessions}", f"Queries: {self.total_queries}"]
        if self.get_preferred_providers():
            parts.append("Providers: " + ", ".join(self.get_preferred_providers()))
        if self.get_common_topics():
            parts.append("Topics: " + ", ".join(self.get_common_topics()[:2]))
        return " | ".join(parts)

    def __repr__(self) -> str:
        return f"<DeepMemory user={self.user_id} sessions={self.total_sessions} queries={self.total_queries}>"
