"""
Memory Layer Module - Shimo 4-Layer Memory System
=================================================

1. HOT MEMORY (prompt layer)        - always injected, tiny
2. COLD MEMORY (episodic recall)    - session history, searchable, compressible
3. PROCEDURAL MEMORY (skills)       - how-to knowledge loaded on demand
4. DEEP MEMORY (user modelling)     - optional cross-session preferences

Usage::

    from backend.memory import MemoryManager, CloudProvider

    mgr = MemoryManager(session_id="sess_123", user_id="user_456", enable_deep_memory=True)
    mgr.initialize_session("My Analysis", [CloudProvider.AWS], "bedrock")
    prompt, context = mgr.process_query("What are my AWS costs?")
    mgr.record_response("Your costs are...", tokens_used=150)
"""

from .cold_memory import AnalysisResult, ColdMemory, MessageRole, SearchResult, StoredMessage
from .deep_memory import DeepMemory, ExpertiseLevel, ReportStyle, UserPattern, UserTrait
from .hot_memory import CloudProvider, HotMemory, ProviderContext, RecentInteraction
from .memory_manager import MemoryManager, MemoryMetrics, detect_query_type, query_tags
from .procedural_memory import ProceduralMemory, Skill, SkillCategory

__all__ = [
    "HotMemory",
    "CloudProvider",
    "ProviderContext",
    "RecentInteraction",
    "ColdMemory",
    "MessageRole",
    "StoredMessage",
    "AnalysisResult",
    "SearchResult",
    "ProceduralMemory",
    "Skill",
    "SkillCategory",
    "DeepMemory",
    "ReportStyle",
    "ExpertiseLevel",
    "UserTrait",
    "UserPattern",
    "MemoryManager",
    "MemoryMetrics",
    "detect_query_type",
    "query_tags",
]

__version__ = "2.1.0"
