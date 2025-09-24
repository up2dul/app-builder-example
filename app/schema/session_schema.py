from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    project_id: str
    name: str = "App Session"
    messages: Optional[List[dict]] = None


class SessionUpdateRequest(BaseModel):
    name: Optional[str] = None
    messages: Optional[List[dict]] = None


class SessionQueryRequest(BaseModel):
    input: str


class SessionResponse(BaseModel):
    id: str
    project_id: str
    name: str
    messages: Optional[List[dict]]
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True
