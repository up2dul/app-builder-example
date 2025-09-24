from typing import List, Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database.engine import db_session
from app.database.models import Project
from app.database.models import Session as SessionModel
from app.schema.project_schema import ProjectCreateRequest, ProjectResponse
from app.services.llm.generations.create_app import generate_app_info
from app.services.sandbox.port_manager import generate_available_port
from app.services.sandbox.sandbox_manager import setup_sandbox
from app.services.sandbox.server_manager import stop_server

project_router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


@project_router.get("/", response_model=List[ProjectResponse])
def list_projects(session: Session = Depends(db_session)) -> Sequence[Project]:
    """List all projects"""
    statement = select(Project).where(Project.is_deleted == False)  # noqa: E712
    projects = session.exec(statement).all()
    return projects


@project_router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, session: Session = Depends(db_session)) -> None:
    """Delete a project (soft delete)"""
    statement = select(Project).where(Project.id == project_id, Project.is_deleted == False)  # noqa: E712
    project = session.exec(statement).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Stop the server process if it's running
    if project.server_pid:
        stop_server(project.server_pid)
        project.server_pid = None

    project.is_deleted = True
    session.add(project)
    session.commit()


@project_router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, session: Session = Depends(db_session)) -> Project:
    """Get a specific project by ID"""
    statement = select(Project).where(Project.id == project_id, Project.is_deleted == False)  # noqa: E712
    project = session.exec(statement).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@project_router.post("/", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreateRequest, db_session_dep: Session = Depends(db_session)
) -> Project | None:
    """Create a new project"""
    project_info = generate_app_info(project_data.description)
    project_dict = project_info.model_dump()

    port = generate_available_port()
    if port is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to generate available port"
        )

    existing_project = db_session_dep.exec(
        select(Project).where(Project.port == port, Project.is_deleted == False)  # noqa: E712
    ).first()
    if existing_project:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Port {port} is already in use")

    # Create the project
    project = Project(
        name=project_dict["name"],
        description=project_dict["description"],
        port=port,
        project_metadata={},  # Initialize empty metadata dict
    )
    db_session_dep.add(project)
    db_session_dep.commit()
    db_session_dep.refresh(project)

    # Create the initial session
    initial_session = SessionModel(project_id=project.id, name="Initial Session", messages=[])
    db_session_dep.add(initial_session)
    db_session_dep.commit()
    db_session_dep.refresh(initial_session)

    # Initialize sandbox
    try:
        sandbox_result, server_pid = setup_sandbox(project.id, port)
        if server_pid:
            project.server_pid = server_pid
            if project.project_metadata is None:
                project.project_metadata = {}
            project.project_metadata["sandbox_status"] = "initialized"
            project.project_metadata["sandbox_error"] = sandbox_result
        else:
            if project.project_metadata is None:
                project.project_metadata = {}
            project.project_metadata["sandbox_status"] = "failed"
            project.project_metadata["sandbox_error"] = sandbox_result
    except Exception as e:
        if project.project_metadata is None:
            project.project_metadata = {}
        project.project_metadata["sandbox_status"] = "failed"
        project.project_metadata["sandbox_error"] = str(e)

    # Final commit for sandbox updates
    db_session_dep.add(project)
    db_session_dep.commit()
    db_session_dep.refresh(project)

    return project
