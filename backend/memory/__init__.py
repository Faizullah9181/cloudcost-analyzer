"""
Memory Layer Module - Shimo 4-Layer Memory System
===========================================================

Shimo Memory Architecture:
1. HOT MEMORY (Prompt Layer) - In-memory, always injected
2. COLD MEMORY (Episodic Recall) - SQLite history, retrieved on-demand
3. PROCEDURAL MEMORY (Skills) - How-to knowledge, loaded on-demand
4. DEEP MEMORY (User Modeling) - Cross-session preferences (optional)

Usage:
    from backend.memory import MemoryManager

    mgr = MemoryManager(session_id="sess_123", user_id="user_456")
    mgr.initialize_session("My Analysis", [CloudProvider.AWS], "bedrock")

    prompt, context = mgr.process_query("What are my AWS costs?")
    mgr.record_response("Your costs are...", tokens_used=150)
"""

from .hot_memory import (
    HotMemory,
    CloudProvider,
    ProviderContext,
    RecentInteraction,
)

from .cold_memory import (
    ColdMemory,
    MessageRole,
    StoredMessage,
    AnalysisResult,
    SearchResult,
)

from .procedural_memory import (
    ProceduralMemory,
    Skill,
    SkillCategory,
)

from .deep_memory import (
    DeepMemory,
    ReportStyle,
    ExpertiseLevel,
    UserTrait,
    UserPattern,
)

from .memory_manager import (
    MemoryManager,
    MemoryMetrics,
)

__all__ = [
    # Hot Memory
    "HotMemory",
    "CloudProvider",
    "ProviderContext",
    "RecentInteraction",
    # Cold Memory
    "ColdMemory",
    "MessageRole",
    "StoredMessage",
    "AnalysisResult",
    "SearchResult",
    # Procedural Memory
    "ProceduralMemory",
    "Skill",
    "SkillCategory",
    # Deep Memory
    "DeepMemory",
    "ReportStyle",
    "ExpertiseLevel",
    "UserTrait",
    "UserPattern",
    # Manager
    "MemoryManager",
    "MemoryMetrics",
]

__version__ = "2.0.0"
__description__ = (
    "Shimo's 4-layer memory system for long-running cloud analytics sessions"
)
