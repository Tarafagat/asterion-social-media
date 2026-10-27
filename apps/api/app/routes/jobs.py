from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .. import services
from ..deps import get_db_path
from ..schemas import JobOut

router = APIRouter(tags=["jobs"])


@router.post("/projects/{project_id}/jobs", response_model=JobOut, status_code=201)
def create_job(project_id: str, db_path: Path = Depends(get_db_path)):
    # Import diferido (no al tope del módulo): apps.worker importa
    # faster_whisper en cascada, que tarda un instante en inicializar —
    # no vale la pena pagarlo en el arranque de cada módulo de rutas,
    # solo cuando de verdad se crea un job.
    from apps.worker.app.runner import create_job as _create_job

    project = services.projects.get_project(db_path, project_id)
    if not project:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")
    if not project.get("source_filename"):
        raise HTTPException(400, "este proyecto todavía no tiene ningún video subido")

    job_id = _create_job(db_path, project_id)
    return services.jobs.get_job(db_path, job_id)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db_path: Path = Depends(get_db_path)):
    job = services.jobs.get_job(db_path, job_id)
    if not job:
        raise HTTPException(404, f"no existe el job {job_id!r}")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, db_path: Path = Depends(get_db_path)):
    from apps.worker.app.runner import JobNotCancellableError, cancel_job as _cancel_job

    job = services.jobs.get_job(db_path, job_id)
    if not job:
        raise HTTPException(404, f"no existe el job {job_id!r}")
    try:
        _cancel_job(db_path, job_id)
    except JobNotCancellableError as exc:
        raise HTTPException(409, str(exc)) from exc
    return services.jobs.get_job(db_path, job_id)


@router.get("/projects/{project_id}/jobs", response_model=list[JobOut])
def list_jobs(project_id: str, db_path: Path = Depends(get_db_path)):
    return services.jobs.list_jobs_for_project(db_path, project_id)
