"""Session management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as SQLSession
from typing import List, Optional

try:
    from backend.database import get_db, init_db
    from backend.models.session import Session
except ImportError:
    from database import get_db, init_db
    from models.session import Session
from pydantic import BaseModel


# Initialize database on import
init_db()

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# Request/Response models
class SessionCreate(BaseModel):
    """Create session request."""

    name: str
    cloud_providers: dict
    llm_provider: Optional[str] = "bedrock"


class SessionResponse(BaseModel):
    """Session response."""

    id: str
    name: str
    created_at: str
    updated_at: str
    message_count: int
    cloud_providers: dict
    llm_provider: str
    is_active: bool

    class Config:
        from_attributes = True


class MessageAdd(BaseModel):
    """Add message request."""

    role: str  # "user" or "assistant"
    content: str


class SessionAnalysisUpdate(BaseModel):
    """Update analysis result."""

    analysis: dict


# Routes
@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(req: SessionCreate, db: SQLSession = Depends(get_db)):
    """Create new session."""
    new_session = Session(
        name=req.name,
        cloud_providers=req.cloud_providers,
        llm_provider=req.llm_provider,
        llm_model="",
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return new_session


@router.get("", response_model=List[SessionResponse])
def list_sessions(limit: int = 10, skip: int = 0, db: SQLSession = Depends(get_db)):
    """List active sessions."""
    sessions = (
        db.query(Session)
        .filter(Session.is_active)
        .order_by(Session.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return sessions


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: SQLSession = Depends(get_db)):
    """Get session by ID."""
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    return session


@router.post("/{session_id}/messages")
def add_message(session_id: str, req: MessageAdd, db: SQLSession = Depends(get_db)):
    """Add message to session."""
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    session.add_message(req.role, req.content)
    db.commit()

    return {"status": "ok", "message_count": session.message_count}


@router.get("/{session_id}/messages")
def get_messages(session_id: str, limit: int = 50, db: SQLSession = Depends(get_db)):
    """Get session messages."""
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    messages = session.messages[-limit:]

    return {
        "session_id": session_id,
        "message_count": len(messages),
        "messages": messages,
    }


@router.post("/{session_id}/analysis")
def update_analysis(
    session_id: str, req: SessionAnalysisUpdate, db: SQLSession = Depends(get_db)
):
    """Update session analysis results."""
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    session.update_analysis(req.analysis)
    db.commit()

    return {"status": "ok", "updated_at": session.updated_at.isoformat()}


@router.get("/{session_id}/analysis")
def get_analysis(session_id: str, db: SQLSession = Depends(get_db)):
    """Get session analysis results."""
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    return {"session_id": session_id, "analysis": session.analysis_results}


@router.post("/{session_id}/export")
def export_session(session_id: str, db: SQLSession = Depends(get_db)):
    """Export session to JSON."""
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    return {
        "id": session.id,
        "name": session.name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "cloud_providers": session.cloud_providers,
        "llm_provider": session.llm_provider,
        "message_count": session.message_count,
        "messages": session.messages,
        "analysis_results": session.analysis_results,
    }


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, db: SQLSession = Depends(get_db)):
    """Archive session (soft delete)."""
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    session.is_active = False
    db.commit()

    return None
