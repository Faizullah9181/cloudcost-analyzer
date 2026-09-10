"""Session management and session-scoped chat endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session as DBSession

from backend.agents.agent_harness import AgentHarness
from backend.database import get_db
from backend.models import ChatSession
from backend.schemas import (
    ChatRequest,
    ChatResponse,
    CompressResponse,
    MessageAdd,
    MessagesResponse,
    SessionAnalysisUpdate,
    SessionCreate,
    SessionResponse,
    SessionUpdate,
)
from backend.services.session_store import SessionNotFound, SessionStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _require(store: SessionStore, session_id: str) -> ChatSession:
    try:
        return store.require_session(session_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(req: SessionCreate, db: DBSession = Depends(get_db)):
    """Create a new session."""
    store = SessionStore(db)
    return store.create_session(
        name=req.name,
        providers=req.cloud_providers,
        llm_provider=req.llm_provider,
        connection_context=req.connection_context,
        user_id=req.user_id,
        tags=req.tags,
    )


@router.get("", response_model=list[SessionResponse])
def list_sessions(
    limit: int = Query(10, ge=1, le=200),
    skip: int = Query(0, ge=0),
    include_archived: bool = False,
    user_id: str | None = None,
    db: DBSession = Depends(get_db),
):
    """List sessions, most recently updated first."""
    return SessionStore(db).list_sessions(limit=limit, skip=skip, include_archived=include_archived, user_id=user_id)


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    """Get a session by id (a unique id prefix of 6+ characters also works)."""
    return _require(SessionStore(db), session_id)


@router.patch("/{session_id}", response_model=SessionResponse)
def update_session(session_id: str, req: SessionUpdate, db: DBSession = Depends(get_db)):
    """Rename a session or update its connection context / tags."""
    store = SessionStore(db)
    session = _require(store, session_id)
    return store.update_session(session, name=req.name, connection_context=req.connection_context, tags=req.tags)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, hard: bool = False, db: DBSession = Depends(get_db)):
    """Archive a session (soft delete). Pass ``hard=true`` to delete permanently."""
    store = SessionStore(db)
    _require(store, session_id)
    if hard:
        store.delete_session(session_id)
    else:
        store.archive_session(session_id)


def _run_chat(session_id: str, query: str) -> ChatResponse:
    with SessionStore() as store:
        harness = AgentHarness(store=store)
        try:
            harness.load_session(session_id)
        except SessionNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        turn = harness.analyze(query)
        return ChatResponse(
            success=turn.success,
            session_id=harness.session_id or session_id,
            message=turn.response,
            data=turn.analysis,
            error=turn.error,
            memory={
                **turn.memory_context,
                "compression": turn.compression,
                "usage": turn.usage,
                "duration_seconds": round(turn.duration_seconds, 3),
            },
            tool_calls=turn.tool_calls,
        )


@router.post("/{session_id}/chat", response_model=ChatResponse)
async def chat(session_id: str, req: ChatRequest):
    """Run the agent for one turn inside the session (memory-aware, persisted)."""
    return await run_in_threadpool(_run_chat, session_id, req.query)


@router.get("/{session_id}/messages", response_model=MessagesResponse)
def get_messages(session_id: str, limit: int = Query(50, ge=1, le=1000), db: DBSession = Depends(get_db)):
    """Most recent messages of a session."""
    store = SessionStore(db)
    session = _require(store, session_id)
    messages = store.get_messages(session.id, limit=limit)
    return MessagesResponse(
        session_id=session.id,
        message_count=int(session.message_count or 0),
        messages=[m.to_dict() for m in messages],
    )


@router.post("/{session_id}/messages", status_code=status.HTTP_201_CREATED)
def add_message(session_id: str, req: MessageAdd, db: DBSession = Depends(get_db)):
    """Append a message manually (for imports or annotations)."""
    store = SessionStore(db)
    session = _require(store, session_id)
    message = store.add_message(session, req.role, req.content, commit=True)
    return {"status": "ok", "message_count": session.message_count, "message": message.to_dict()}


@router.post("/{session_id}/analysis")
def update_analysis(session_id: str, req: SessionAnalysisUpdate, db: DBSession = Depends(get_db)):
    """Replace the cached analysis result."""
    store = SessionStore(db)
    session = _require(store, session_id)
    store.update_analysis(session, req.analysis, commit=True)
    return {"status": "ok", "updated_at": session.updated_at.isoformat()}


@router.get("/{session_id}/analysis")
def get_analysis(session_id: str, db: DBSession = Depends(get_db)):
    """Latest cached analysis result."""
    session = _require(SessionStore(db), session_id)
    return {"session_id": session.id, "analysis": session.get_last_analysis()}


def _compress(session_id: str) -> CompressResponse:
    with SessionStore() as store:
        harness = AgentHarness(store=store)
        try:
            harness.load_session(session_id)
        except SessionNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        result = harness.compress_context()
        return CompressResponse(
            session_id=harness.session_id or session_id,
            compressed_messages=int(result.get("compressed_messages", 0)),
            pruned_messages=int(result.get("pruned_messages", 0)),
            summary=str(result.get("summary", "")),
            compression_count=int(result.get("compression_count", 0)),
        )


@router.post("/{session_id}/compress", response_model=CompressResponse)
async def compress_session(session_id: str):
    """Compress the session history into a summary."""
    return await run_in_threadpool(_compress, session_id)


@router.get("/{session_id}/export")
@router.post("/{session_id}/export")
def export_session(session_id: str, db: DBSession = Depends(get_db)):
    """Export the session, including full message history and the latest analysis."""
    session = _require(SessionStore(db), session_id)
    return session.to_export()


@router.get("/{session_id}/memory")
def get_memory_status(session_id: str):
    """Memory-layer status for a session (hydrated from persisted history)."""
    with SessionStore() as store:
        harness = AgentHarness(store=store)
        try:
            harness.load_session(session_id)
        except SessionNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        return {"session_id": harness.session_id, "memory": harness.get_memory_status(), "health": harness.get_health_status()}
