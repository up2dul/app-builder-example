import json
from typing import List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.database.engine import db_session
from app.database.models import Project
from app.database.models import Session as SessionModel
from app.schema.session_schema import SessionCreateRequest, SessionResponse, SessionUpdateRequest
from app.services.llm.dataclasses.project_info import ProjectInfo
from app.services.llm.llm_agents import running_agent

session_router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
)


@session_router.get("/", response_model=List[SessionResponse])
def list_sessions(
    project_id: Optional[str] = Query(None, description="Filter sessions by project ID"),
    session: Session = Depends(db_session),
) -> Sequence[SessionModel]:
    """List all sessions, optionally filtered by project ID"""
    statement = select(SessionModel).where(not SessionModel.is_deleted)

    if project_id:
        statement = statement.where(SessionModel.project_id == project_id)

    sessions = session.exec(statement).all()
    return sessions


@session_router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, session: Session = Depends(db_session)) -> SessionModel:
    """Get a specific session by ID"""
    statement = select(SessionModel).where(SessionModel.id == session_id, not SessionModel.is_deleted)
    session_obj = session.exec(statement).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_obj


@session_router.post("/", response_model=SessionResponse)
def create_session(session_data: SessionCreateRequest, session: Session = Depends(db_session)) -> SessionModel:
    """Create a new session"""
    project_statement = select(Project).where(Project.id == session_data.project_id, not Project.is_deleted)
    project = session.exec(project_statement).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    session_obj = SessionModel(
        project_id=session_data.project_id,
        name=session_data.name,
        messages=session_data.messages or [],
    )
    session.add(session_obj)
    session.commit()
    session.refresh(session_obj)

    return session_obj


@session_router.put("/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str, session_data: SessionUpdateRequest, session: Session = Depends(db_session)
) -> SessionModel:
    """Update a specific session by ID"""
    statement = select(SessionModel).where(SessionModel.id == session_id, not SessionModel.is_deleted)
    session_obj = session.exec(statement).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_data.name is not None:
        session_obj.name = session_data.name
    if session_data.messages is not None:
        session_obj.messages = session_data.messages
    session.add(session_obj)
    session.commit()
    session.refresh(session_obj)

    return session_obj


@session_router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, session: Session = Depends(db_session)) -> None:
    """Delete a session (soft delete)"""
    statement = select(SessionModel).where(SessionModel.id == session_id, not SessionModel.is_deleted)
    session_obj = session.exec(statement).first()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    session_obj.is_deleted = True
    session.add(session_obj)
    session.commit()


@session_router.post("/{session_id}/query", response_model=List[dict])
async def query_session(
    session_id: str,
    query_data: SessionCreateRequest,
    session: Session = Depends(db_session),
):
    """Query a specific session by ID using LLM agent with streaming response"""
    statement = (
        select(SessionModel, Project)
        .join(Project, SessionModel.project_id == Project.id)
        .where(SessionModel.id == session_id, not SessionModel.is_deleted)
    )
    result = session.exec(statement).first()
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    session_obj, project_obj = result
    project_info = ProjectInfo(id=project_obj.id, name=project_obj.name, port=project_obj.port)

    # Get existing messages from session or initialize with empty list
    existing_messages = session_obj.messages or []

    # Add user message to the conversation
    user_message = {"role": "user", "content": query_data.input}
    message_for_agent = existing_messages + [user_message]

    # Store assistant response content
    assistant_content = ""

    async def generate_stream():
        nonlocal assistant_content
        async for chunk in running_agent(message_for_agent, project_info):
            # Collect assistant message response content
            if chunk.get("type") == "message_output":
                assistant_content = chunk.get("output", "")
            yield json.dumps(chunk) + "\n"

        # After streaming is complete, update session with both messages
        assistant_message = {"role": "assistant", "content": assistant_content}
        updated_messages = message_for_agent + [assistant_message]

        # Update session in database
        session_obj.messages = updated_messages
        session.add(session_obj)
        session.commit()

    return StreamingResponse(
        generate_stream(),
        media_type="application/json",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
