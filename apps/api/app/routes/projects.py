from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from packages.config import Settings
from packages.storage import ProjectLayout

from .. import services
from ..deps import get_db_path, get_settings_dep
from ..schemas import ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, db_path: Path = Depends(get_db_path)):
    row = services.projects.create_project(db_path, body.name)
    return ProjectOut.from_row(row)


@router.get("", response_model=list[ProjectOut])
def list_projects(db_path: Path = Depends(get_db_path)):
    return [ProjectOut.from_row(r) for r in services.projects.list_projects(db_path)]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db_path: Path = Depends(get_db_path)):
    row = services.projects.get_project(db_path, project_id)
    if not row:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")
    return ProjectOut.from_row(row)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db_path: Path = Depends(get_db_path)):
    services.projects.delete_project(db_path, project_id)


@router.post("/{project_id}/source", response_model=ProjectOut)
async def upload_source(
    project_id: str,
    file: UploadFile,
    db_path: Path = Depends(get_db_path),
    settings: Settings = Depends(get_settings_dep),
):
    row = services.projects.get_project(db_path, project_id)
    if not row:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    layout.ensure()
    dest = layout.source_video(file.filename)
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    services.projects.set_source_filename(db_path, project_id, file.filename)
    return ProjectOut.from_row(services.projects.get_project(db_path, project_id))
