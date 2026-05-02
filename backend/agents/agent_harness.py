"""
Agent Harness - Memory-Aware Agent Wrapper
===========================================
Updated ShimoAgentHarness that integrates the 4-layer memory system.

This harness:
1. Manages memory through MemoryManager
2. Integrates with Strands Agent for LLM + tools
3. Handles long-running sessions with automatic compression
4. Manages cloud provider credentials
5. Supports multi-user with optional deep memory
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
import uuid

from backend.memory import (
    MemoryManager,
    CloudProvider,
)


class AgentHarness:
    """
    Memory-Aware Agent Harness for Shimo.

    Integration Points:
    - MemoryManager: All 4 memory layers
    - Strands Agent: LLM + tool orchestration
    - Database: Persistence layer
    - CLI/API: User interfaces
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        enable_deep_memory: bool = False,
    ):
        """
        Initialize agent harness.

        Args:
            session_id: Session ID (generate if None)
            user_id: User ID (for analytics)
            enable_deep_memory: Enable user modeling
        """
        self.session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        self.user_id = user_id

        # Initialize memory manager (4-layer system)
        self.memory_manager = MemoryManager(
            session_id=self.session_id,
            user_id=user_id,
            enable_deep_memory=enable_deep_memory,
        )

        # Session metadata
        self.session_name: Optional[str] = None
        self.active_providers: List[CloudProvider] = []
        self.llm_provider: str = "bedrock"
        self.credentials: Dict[str, Dict] = {}  # Per-provider credentials

        # Agent state
        self.is_active: bool = False
        self.created_at: datetime = datetime.now()
        self.last_activity: datetime = datetime.now()
        self.query_count: int = 0
        self.tool_calls: List[Dict] = []

        # Strands Agent (will be initialized on first query)
        self.strands_agent = None

    # ========== SESSION INITIALIZATION ==========

    def create_session(
        self,
        session_name: str,
        providers: List[CloudProvider],
        llm_provider: str,
        credentials: Dict[str, Dict],
    ) -> str:
        """
        Create a new session with configuration.

        Args:
            session_name: Human-readable session name
            providers: Cloud providers to analyze
            llm_provider: LLM provider to use
            credentials: Provider credentials

        Returns:
            Session ID
        """
        self.session_name = session_name
        self.active_providers = providers
        self.llm_provider = llm_provider
        self.credentials = credentials
        self.is_active = True

        # Initialize memory manager
        self.memory_manager.initialize_session(
            session_name=session_name, providers=providers, llm_provider=llm_provider
        )

        # Initialize Strands Agent (stub - real implementation uses strands SDK)
        self._initialize_strands_agent()

        return self.session_id

    def load_session(self, session_id: str) -> bool:
        """
        Load existing session from database.

        Args:
            session_id: Session to load

        Returns:
            Success status
        """
        # In production: load from database
        self.session_id = session_id
        self.is_active = True
        self.last_activity = datetime.now()

        return True

    def _initialize_strands_agent(self) -> None:
        """Initialize Strands Agent with current settings"""
        # This is a stub - actual implementation uses Strands SDK
        # In real code:
        # from strands import Agent
        # self.strands_agent = Agent(
        #     llm_provider=self.llm_provider,
        #     tools=self._get_available_tools(),
        #     system_prompt=self.memory_manager.hot_memory.get_system_prompt()
        # )
        pass

    # ========== QUERY PROCESSING ==========

    def analyze(self, query: str, stream: bool = False) -> Tuple[str, Dict]:
        """
        Process a user query through memory + LLM + tools.

        Args:
            query: User query
            stream: Enable streaming response (bool)

        Returns:
            (response_text, analysis_data)
        """
        if not self.is_active:
            raise RuntimeError("Session not active")

        self.query_count += 1
        self.last_activity = datetime.now()

        # ========== STEP 1: RETRIEVE & ASSEMBLE MEMORY ==========

        # Process query through memory manager
        assembled_prompt, memory_context = self.memory_manager.process_query(
            query, user_id=self.user_id
        )

        print(f"\n[MEMORY] Retrieved {memory_context['retrieved_messages']} messages")
        print(f"[MEMORY] Loaded {len(memory_context['loaded_skills'])} skills")

        # ========== STEP 2: CALL LLM WITH FULL CONTEXT ==========

        # In production: use Strands Agent
        # response = self.strands_agent.query(
        #     query=query,
        #     system_prompt=assembled_prompt,
        #     streaming=stream
        # )

        # For now: mock response
        response = self._mock_llm_call(query)

        # ========== STEP 3: PARSE & ANALYZE RESPONSE ==========

        analysis_data = self._parse_analysis(response)

        # ========== STEP 4: RECORD TO MEMORY ==========

        self.memory_manager.record_response(
            response=response,
            tokens_used=len(response.split()) * 1.3,  # Rough estimate
            analysis_data=analysis_data,
        )

        # ========== STEP 5: RETURN RESULTS ==========

        return response, analysis_data

    def _mock_llm_call(self, query: str) -> str:
        """
        Mock LLM call (for demonstration).
        In production, this uses actual Strands Agent.
        """
        provider = self.memory_manager.hot_memory.current_provider
        provider_str = provider.value.upper() if provider else "UNKNOWN"

        # Simulate analysis based on query
        if "cost" in query.lower():
            return (
                f"Based on your {provider_str} infrastructure, here's the cost analysis:\n"
                f"- Compute: $2,341 (45%)\n"
                f"- Storage: $1,234 (24%)\n"
                f"- Network: $890 (17%)\n"
                f"- Other: $685 (14%)\n\n"
                f"Total: $5,150 for this month"
            )
        elif "forecast" in query.lower():
            return (
                f"Cost forecast for next month ({provider_str}):\n"
                f"Expected total: $5,450 (+5.8% vs this month)\n"
                f"Factors: 12% growth in compute, storage optimization -2%"
            )
        elif "compare" in query.lower():
            return (
                "Multi-cloud comparison:\n"
                "AWS: $5,150\nAzure: $3,200 (-37.9%)\n"
                "AWS appears more expensive due to compute-intensive workloads"
            )
        else:
            return "Analysis complete. Results available in dashboard."

    def _parse_analysis(self, response: str) -> Dict:
        """
        Parse LLM response into structured analysis data.

        Returns:
            Analysis dictionary
        """
        provider = (
            self.memory_manager.hot_memory.current_provider.value
            if self.memory_manager.hot_memory.current_provider
            else "unknown"
        )

        return {
            "provider": provider,
            "query_type": self._detect_query_type(response),
            "summary": response[:200],
            "timestamp": datetime.now().isoformat(),
        }

    def _detect_query_type(self, response: str) -> str:
        """Detect type of query from response"""
        response_lower = response.lower()
        if "forecast" in response_lower:
            return "forecast"
        elif "comparison" in response_lower:
            return "comparison"
        elif "optimization" in response_lower:
            return "optimization"
        else:
            return "analysis"

    # ========== LONG-SESSION MANAGEMENT ==========

    def compress_context(self) -> Dict:
        """
        Manually compress session context.

        Returns:
            Compression results
        """
        return self.memory_manager.force_compression()

    def check_compression_needed(self) -> bool:
        """Check if automatic compression is needed"""
        return (
            self.query_count > 0
            and self.query_count % self.memory_manager.compression_threshold == 0
        )

    # ========== SESSION MANAGEMENT ==========

    def get_session_info(self) -> Dict:
        """Get current session information"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "session_name": self.session_name,
            "providers": [p.value for p in self.active_providers],
            "llm_provider": self.llm_provider,
            "query_count": self.query_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }

    def get_memory_status(self) -> Dict:
        """Get all memory layer status"""
        return self.memory_manager.get_memory_status()

    def export_session(self) -> Dict:
        """Export session for archival"""
        export = self.memory_manager.export_session()
        export.update(
            {
                "query_count": self.query_count,
                "compression_count": self.memory_manager.metrics.compression_count,
            }
        )
        return export

    # ========== CREDENTIAL MANAGEMENT ==========

    def set_provider_credentials(
        self, provider: CloudProvider, credentials: Dict
    ) -> None:
        """
        Set credentials for a provider.

        Args:
            provider: Cloud provider
            credentials: Provider-specific credentials
        """
        self.credentials[provider.value] = credentials
        # Update hot memory
        if provider in self.memory_manager.hot_memory.active_providers:
            ctx = self.memory_manager.hot_memory.provider_contexts[provider]
            if "account_id" in credentials:
                ctx.account_id = credentials["account_id"]

    def get_provider_credentials(self, provider: CloudProvider) -> Optional[Dict]:
        """Get credentials for a provider"""
        return self.credentials.get(provider.value)

    # ========== DIAGNOSTICS & MONITORING ==========

    def get_health_status(self) -> Dict:
        """Get agent health status"""
        return {
            "session_active": self.is_active,
            "memory_layers": {
                "hot": len(self.memory_manager.hot_memory.recent_interactions),
                "cold": self.memory_manager.cold_memory.get_stats()["total_messages"],
                "procedural": self.memory_manager.procedural_memory.get_stats()[
                    "total_skills"
                ],
                "deep": "enabled" if self.memory_manager.deep_memory else "disabled",
            },
            "compression_status": {
                "compressions": self.memory_manager.metrics.compression_count,
                "last_compression": self.memory_manager.metrics.last_compression_time.isoformat()
                if self.memory_manager.metrics.last_compression_time
                else None,
            },
            "query_stats": {
                "total_queries": self.query_count,
                "queries_since_compression": self.query_count
                % self.memory_manager.compression_threshold,
            },
        }

    def end_session(self) -> Dict:
        """End session and return summary"""
        if self.memory_manager.deep_memory:
            self.memory_manager.deep_memory.record_session_end()

        self.is_active = False

        return {
            "session_id": self.session_id,
            "duration_minutes": (datetime.now() - self.created_at).total_seconds() / 60,
            "query_count": self.query_count,
            "memory_export": self.memory_manager.export_session(),
        }

    def __repr__(self) -> str:
        return (
            f"<AgentHarness session={self.session_id} "
            f"queries={self.query_count} "
            f"providers={len(self.active_providers)}>"
        )


# ========== EXAMPLE USAGE ==========

if __name__ == "__main__":
    import json

    print("=" * 70)
    print("AGENT HARNESS TESTS (Memory-Aware Agent)")
    print("=" * 70)

    # Create harness
    harness = AgentHarness(user_id="user_johndoe", enable_deep_memory=True)

    print("\n1. Create Session:")
    session_id = harness.create_session(
        session_name="Multi-Cloud Q2 Analysis",
        providers=[CloudProvider.AWS, CloudProvider.AZURE],
        llm_provider="bedrock",
        credentials={
            "aws": {"account_id": "123456789012"},
            "azure": {"account_id": "sub-abc123"},
        },
    )
    print(f"   ✓ Session created: {session_id}")

    print("\n2. Query 1: AWS Cost Analysis")
    response1, data1 = harness.analyze("What are my AWS costs this month?")
    print(f"   Response: {response1[:100]}...")
    print(f"   Analysis: {data1}")

    print("\n3. Query 2: Cost Comparison")
    response2, data2 = harness.analyze("Compare AWS and Azure costs")
    print(f"   Response: {response2[:100]}...")

    print("\n4. Memory Status:")
    status = harness.get_memory_status()
    print(f"   Hot Memory messages: {status['hot_memory']['total_messages']}")
    print(f"   Cold Memory stored: {status['cold_memory']['total_messages']}")
    print(f"   Procedural skills: {status['procedural_memory']['total_skills']}")

    print("\n5. Session Info:")
    info = harness.get_session_info()
    print(json.dumps(info, indent=2, default=str))

    print("\n6. Health Status:")
    health = harness.get_health_status()
    print(json.dumps(health, indent=2, default=str))

    print("\n7. Force Compression:")
    compression = harness.compress_context()
    print(f"   Compressed: {compression['compressed_messages']} messages")
    print(f"   Pruned: {compression['pruned_messages']} messages")

    print("\n8. End Session:")
    summary = harness.end_session()
    print(json.dumps(summary, indent=2, default=str))
