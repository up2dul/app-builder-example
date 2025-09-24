from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schema.session_schema import SessionResponse


class ProjectCreateRequest(BaseModel):
    description: str


class ProjectInfo(BaseModel):
    id: str
    name: str
    description: Optional[str]
    port: int
    server_pid: Optional[int]
    project_metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    port: int
    server_pid: Optional[int]
    project_metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    sessions: Optional[list[SessionResponse]] = None

    class Config:
        from_attributes = True
