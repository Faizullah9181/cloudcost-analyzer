"""
Memory Manager - Orchestration Layer
============================================
The Memory Manager coordinates all 4 memory layers:
- HOT MEMORY (prompt layer)
- COLD MEMORY (session history)
- PROCEDURAL MEMORY (skills)
- DEEP MEMORY (user modeling)

It handles:
1. Memory assembly for prompt injection
2. Retrieval orchestration
3. Long-session optimization
4. Memory lifecycle management
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

from .hot_memory import HotMemory, CloudProvider
from .cold_memory import ColdMemory, MessageRole, StoredMessage
from .procedural_memory import ProceduralMemory
from .deep_memory import DeepMemory


@dataclass
class MemoryMetrics:
    """Memory usage and performance metrics"""

    hot_memory_tokens: int = 0
    cold_memory_tokens: int = 0
    procedural_memory_tokens: int = 0
    deep_memory_tokens: int = 0
    total_tokens: int = 0

    compression_count: int = 0
    last_compression_time: Optional[datetime] = None

    total_messages: int = 0
    total_retrievals: int = 0


class MemoryManager:
    """
    MEMORY MANAGER - Orchestrates all 4 memory layers.

    Responsibilities:
    1. Coordinate memory layers for query processing
    2. Assemble complete prompt injection
    3. Manage long-running sessions
    4. Handle memory cleanup and compression
    5. Provide metrics and monitoring
    """

    def __init__(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        enable_deep_memory: bool = False,
    ):
        """
        Initialize memory manager.

        Args:
            session_id: Session identifier
            user_id: User identifier (optional)
            enable_deep_memory: Enable user modeling layer
        """
        self.session_id = session_id
        self.user_id = user_id

        # Initialize all 4 layers
        self.hot_memory = HotMemory(session_id, session_name=session_id)
        self.cold_memory = ColdMemory(session_id)
        self.procedural_memory = ProceduralMemory()
        self.deep_memory = DeepMemory(user_id) if enable_deep_memory else None

        # Metrics
        self.metrics = MemoryMetrics()

        # Configuration
        self.compression_threshold = 20  # Compress after N messages
        self.context_window_limit = 8000  # Max tokens in assembled prompt
        self.enable_deep_memory = enable_deep_memory

    # ========== SESSION SETUP ==========

    def initialize_session(
        self, session_name: str, providers: List[CloudProvider], llm_provider: str
    ) -> None:
        """
        Initialize a new session with settings.

        Args:
            session_name: Human-readable session name
            providers: Cloud providers to analyze
            llm_provider: LLM to use
        """
        self.hot_memory.session_name = session_name
        self.hot_memory.llm_provider = llm_provider

        # Add providers
        for provider in providers:
            # In real usage, account_id comes from credentials
            account_id = f"account_{provider.value}"
            self.hot_memory.add_provider(provider, account_id)

        # Set first provider as current
        if providers:
            self.hot_memory.set_current_provider(providers[0])

        # Record session start if deep memory enabled
        if self.deep_memory:
            self.deep_memory.record_session_start()

    # ========== QUERY PROCESSING ==========

    def process_query(
        self, query: str, user_id: Optional[str] = None
    ) -> Tuple[str, Dict]:
        """
        Process a user query through all memory layers.

        Returns:
            (assembled_prompt, context_data)
        """
        # 1. RETRIEVE - Search COLD MEMORY for relevant history
        cold_results = self.cold_memory.search_by_content(query, limit=3)
        cold_summary = (
            self.cold_memory.summarize_messages([r.message for r in cold_results])
            if cold_results
            else ""
        )

        # 2. LOAD - Identify relevant PROCEDURAL MEMORY (skills)
        relevant_skills = self.procedural_memory.get_relevant_skills(query, limit=3)

        # 3. RECORD - Add query to COLD MEMORY
        self._add_message_to_cold(MessageRole.USER, query)

        # 4. LEARN - Update patterns in DEEP MEMORY
        if self.deep_memory:
            self.deep_memory.observe_query(query)

        # 5. ASSEMBLE - Build complete prompt
        assembled = self._assemble_complete_prompt(cold_summary, relevant_skills)

        # 6. COMPILE - Context data
        context_data = {
            "retrieved_messages": len(cold_results),
            "loaded_skills": [s.id for s in relevant_skills],
            "cold_summary": cold_summary[:200] if cold_summary else "",
            "metrics": self._get_memory_metrics_dict(),
        }

        return assembled, context_data

    def record_response(
        self, response: str, tokens_used: int = 0, analysis_data: Optional[Dict] = None
    ) -> None:
        """
        Record LLM response and any analysis results.

        Args:
            response: LLM response text
            tokens_used: Tokens consumed
            analysis_data: Structured analysis results
        """
        # Add to COLD MEMORY
        self._add_message_to_cold(MessageRole.ASSISTANT, response, tokens=tokens_used)

        # Store analysis if provided
        if analysis_data:
            provider = (
                self.hot_memory.current_provider.value
                if self.hot_memory.current_provider
                else "unknown"
            )
            self.cold_memory.add_analysis(
                analysis_id=f"ana_{self.metrics.total_messages}",
                query=response[:100],
                provider=provider,
                query_type="analysis",
                result=analysis_data,
                tokens_used=tokens_used,
            )

        # Update HOT MEMORY
        self.hot_memory.add_interaction("assistant", response, tokens=tokens_used)
        self.hot_memory.increment_message_count()

        # Check if compression needed
        if self.hot_memory.total_messages % self.compression_threshold == 0:
            self._compress_session()

    # ========== MEMORY ASSEMBLY ==========

    def _assemble_complete_prompt(self, cold_summary: str, skills: List) -> str:
        """
        Assemble complete prompt from all 4 memory layers.

        Order:
        1. SYSTEM PROMPT (HOT)
        2. SESSION METADATA (HOT)
        3. USER CONTEXT (DEEP - optional)
        4. COLD SUMMARY (COLD)
        5. SKILLS (PROCEDURAL)
        6. RECENT CONTEXT (HOT)

        Returns:
            Complete prompt for injection
        """
        sections = []

        # 1. Core system prompt + metadata (HOT)
        sections.append(self.hot_memory.assemble_prompt_injection())

        # 2. User context (DEEP - optional)
        if self.deep_memory:
            user_context = self.deep_memory.get_user_context_injection()
            if user_context:
                sections.append("")
                sections.append(user_context)

        # 3. Cold memory summary
        if cold_summary:
            sections.append("")
            sections.append("### Session History Summary:")
            sections.append(cold_summary)

        # 4. Skills (PROCEDURAL)
        if skills:
            sections.append("")
            skills_injection = self.procedural_memory.assemble_skills_injection()
            if skills_injection:
                sections.append(skills_injection)

        # 5. Assemble and trim
        complete = "\n".join(sections)

        # Truncate if too large
        words = complete.split()
        if len(words) > self.context_window_limit:
            complete = (
                " ".join(words[: self.context_window_limit]) + "\n...(context trimmed)"
            )

        return complete

    # ========== LONG-SESSION OPTIMIZATION ==========

    def _compress_session(self) -> None:
        """
        Compress long sessions to maintain context window.

        Strategy:
        - Summarize old COLD MEMORY messages
        - Clear PROCEDURAL MEMORY
        - Update DEEP MEMORY with patterns
        """
        old_count, summary = self.cold_memory.compress_old_messages(days=7)

        if old_count > 0:
            self.hot_memory.increment_compression_count()
            self.metrics.compression_count += 1
            self.metrics.last_compression_time = datetime.now()

            # Store summary
            if summary:
                self._add_message_to_cold(
                    MessageRole.SYSTEM, f"[Compression: {summary}]"
                )

    def force_compression(self) -> Dict:
        """
        Force immediate compression of session.

        Returns:
            Compression results
        """
        old_count, summary = self.cold_memory.compress_old_messages(days=1)
        pruned = self.cold_memory.prune_retention_window()

        self.procedural_memory.clear_loaded_skills()
        self.hot_memory.clear_interactions()

        return {
            "compressed_messages": old_count,
            "pruned_messages": pruned,
            "summary": summary[:200] if summary else "",
        }

    # ========== UTILITY METHODS ==========

    def _add_message_to_cold(
        self,
        role: MessageRole,
        content: str,
        tokens: int = 0,
        provider: Optional[str] = None,
    ) -> StoredMessage:
        """Add message to COLD MEMORY"""
        msg_id = f"msg_{self.metrics.total_messages}_{role.value}"
        if provider is None and self.hot_memory.current_provider:
            provider = self.hot_memory.current_provider.value

        return self.cold_memory.add_message(
            msg_id=msg_id,
            role=role,
            content=content,
            provider=provider,
            tokens=tokens,
            tags=[],
        )

    def get_memory_status(self) -> Dict:
        """
        Get current status of all memory layers.

        Returns:
            Status dictionary
        """
        return {
            "hot_memory": self.hot_memory.get_session_stats(),
            "cold_memory": self.cold_memory.get_stats(),
            "procedural_memory": {
                "total_skills": len(self.procedural_memory.skills),
                "loaded_skills": len(self.procedural_memory.loaded_skills),
            },
            "deep_memory": self.deep_memory.get_stats() if self.deep_memory else None,
            "metrics": self._get_memory_metrics_dict(),
        }

    def _get_memory_metrics_dict(self) -> Dict:
        """Get metrics as dictionary"""
        return {
            "total_messages": self.metrics.total_messages,
            "compression_count": self.metrics.compression_count,
            "last_compression": self.metrics.last_compression_time.isoformat()
            if self.metrics.last_compression_time
            else None,
        }

    def export_session(self) -> Dict:
        """
        Export complete session for archival.

        Returns:
            Session data dictionary
        """
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "hot_memory": self.hot_memory.to_dict(),
            "cold_memory_stats": self.cold_memory.get_stats(),
            "message_count": len(self.cold_memory.messages),
            "analysis_count": len(self.cold_memory.analyses),
            "exported_at": datetime.now().isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<MemoryManager session={self.session_id} "
            f"msgs={self.metrics.total_messages} "
            f"compressions={self.metrics.compression_count}>"
        )


# ========== EXAMPLE USAGE ==========

if __name__ == "__main__":
    import json

    print("=" * 70)
    print("MEMORY MANAGER TESTS (Full 4-Layer System)")
    print("=" * 70)

    # Create manager
    mgr = MemoryManager(
        session_id="sess_example_123", user_id="user_johndoe", enable_deep_memory=True
    )

    print("\n1. Initialize session:")
    mgr.initialize_session(
        session_name="Multi-Cloud Q2 Analysis",
        providers=[CloudProvider.AWS, CloudProvider.AZURE],
        llm_provider="bedrock",
    )
    print("   ✓ Session initialized")
    print("   Providers: AWS, Azure")
    print("   LLM: bedrock")

    print("\n2. Process first query:")
    prompt, context = mgr.process_query("What are my AWS costs this month?")
    print(f"   ✓ Prompt assembled ({len(prompt.split())} words)")
    print(f"   Retrieved: {context['retrieved_messages']} messages")
    print(f"   Loaded skills: {len(context['loaded_skills'])}")

    print("\n3. Record response:")
    mgr.record_response(
        "Your AWS costs: EC2 $2,341...",
        tokens_used=150,
        analysis_data={"service": "EC2", "cost": 2341},
    )
    print("   ✓ Response recorded")

    print("\n4. Process second query:")
    prompt2, context2 = mgr.process_query("Compare with Azure")
    mgr.record_response(
        "Azure costs are lower: $1,500...",
        tokens_used=120,
        analysis_data={"service": "Azure", "cost": 1500},
    )
    print("   ✓ Second query processed")

    print("\n5. Memory Status:")
    status = mgr.get_memory_status()
    print("   Hot Memory:")
    print(f"     - Total messages: {status['hot_memory']['total_messages']}")
    print("   Cold Memory:")
    print(f"     - Stored messages: {status['cold_memory']['total_messages']}")
    print("   Procedural Memory:")
    print(f"     - Total skills: {status['procedural_memory']['total_skills']}")
    print(f"     - Loaded: {status['procedural_memory']['loaded_skills']}")

    print("\n6. Force Compression:")
    compression_result = mgr.force_compression()
    print(f"   Compressed: {compression_result['compressed_messages']} messages")
    print(f"   Pruned: {compression_result['pruned_messages']} messages")

    print("\n7. Export Session:")
    export = mgr.export_session()
    print(f"   Session ID: {export['session_id']}")
    print(f"   User ID: {export['user_id']}")
    print(f"   Message count: {export['message_count']}")
    print(f"   Analysis count: {export['analysis_count']}")

    print("\n8. Full Status Report:")
    print(json.dumps(mgr.get_memory_status(), indent=2, default=str))
