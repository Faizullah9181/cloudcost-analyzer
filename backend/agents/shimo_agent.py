"""Shimo CLI Agent - Cloud Cost Analysis Agent."""

from typing import Optional, List
from backend.config import settings
from backend.models.session import Session
from backend.database import SessionLocal


class ShimoAgent:
    """Shimo Cloud Cost Analysis Agent."""

    def __init__(self, session_id: Optional[str] = None):
        """Initialize Shimo agent with optional session."""
        self.session_id = session_id
        self.db = SessionLocal()
        self.agent = None
        self.session = None

        if session_id:
            self.load_session(session_id)
        else:
            self.session = None

    def load_session(self, session_id: str):
        """Load existing session from database."""
        self.session = self.db.query(Session).filter(Session.id == session_id).first()
        if not self.session:
            raise ValueError(f"Session {session_id} not found")
        return self.session

    def create_session(
        self, name: str, cloud_providers: dict, llm_provider: str = None
    ) -> Session:
        """Create new session."""
        llm = llm_provider or settings.llm_provider

        new_session = Session(
            name=name,
            cloud_providers=cloud_providers,
            llm_provider=llm,
            llm_model=getattr(settings, f"{llm}_model", ""),
        )
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)

        self.session = new_session
        self.session_id = new_session.id
        return new_session

    def list_sessions(self, limit: int = 10) -> List[dict]:
        """List recent sessions."""
        sessions = (
            self.db.query(Session)
            .filter(Session.is_active)
            .order_by(Session.updated_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": s.id,
                "name": s.name,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "message_count": s.message_count,
                "cloud_providers": s.cloud_providers,
                "llm_provider": s.llm_provider,
            }
            for s in sessions
        ]

    def initialize_agent(self):
        """Initialize Strands Agent with selected LLM provider."""
        from backend.agents.cost_analyzer import get_agent

        self.agent = get_agent()
        return self.agent

    def analyze(self, query: str, stream: bool = False):
        """
        Run analysis using Shimo agent.

        Args:
            query: Natural language query
            stream: Whether to stream responses

        Yields or returns analysis result
        """
        if not self.agent:
            self.initialize_agent()

        # Add user message
        self.session.add_message("user", query)
        self.db.commit()

        # Run agent
        try:
            from backend.agents.cost_analyzer import analyze_costs

            response = analyze_costs(query)

            # Add assistant message
            assistant_content = str(response)
            if isinstance(response, dict):
                if response.get("success") and response.get("data"):
                    assistant_content = response["data"].get("summary", assistant_content)
                elif response.get("error"):
                    assistant_content = response["error"]

            self.session.add_message("assistant", assistant_content)

            # Update analysis results
            if isinstance(response, dict):
                self.session.update_analysis(response)

            self.db.commit()

            return response

        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}"
            self.session.add_message("assistant", error_msg)
            self.db.commit()
            return {"error": error_msg}

    def get_context(self) -> str:
        """Get session context for resumption."""
        if not self.session:
            return ""

        messages = self.session.messages[-10:]  # Last 10 messages
        context = f"Session: {self.session.name}\n"
        context += (
            f"Cloud Providers: {', '.join(self.session.cloud_providers.keys())}\n"
        )
        context += f"Messages: {len(self.session.messages)}\n\n"
        context += "Recent conversation:\n"

        for msg in messages:
            role = msg["role"].upper()
            content = (
                msg["content"][:100] + "..."
                if len(msg["content"]) > 100
                else msg["content"]
            )
            context += f"{role}: {content}\n"

        return context

    def compress_context(self) -> str:
        """Compress conversation using LLM for long-running sessions."""
        if len(self.session.messages) < 5:
            return "Not enough messages to compress"

        # Use LLM to summarize recent messages
        messages_text = "\n".join(
            [f"{m['role']}: {m['content']}" for m in self.session.messages[-20:]]
        )

        summary = " ".join(line.strip() for line in messages_text.splitlines()[-6:])
        self.session.add_message("assistant", f"[CONTEXT COMPRESSED]\n{summary}")
        self.db.commit()
        return summary

    def export_session(self) -> dict:
        """Export session to JSON."""
        if not self.session:
            return {}

        return {
            "id": self.session.id,
            "name": self.session.name,
            "created_at": self.session.created_at.isoformat(),
            "updated_at": self.session.updated_at.isoformat(),
            "cloud_providers": self.session.cloud_providers,
            "llm_provider": self.session.llm_provider,
            "message_count": self.session.message_count,
            "messages": self.session.messages,
            "analysis_results": self.session.analysis_results,
        }

    def delete_session(self):
        """Archive session (soft delete)."""
        if self.session:
            self.session.is_active = False
            self.db.commit()

    def close(self):
        """Close database connection."""
        self.db.close()


def create_shimo_agent(session_id: Optional[str] = None) -> ShimoAgent:
    """Factory function to create ShimoAgent."""
    return ShimoAgent(session_id)
