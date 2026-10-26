from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from .. import services
from ..deps import get_db_path
from ..schemas import ClipOut, EditClipIn, JobOut, RatingIn

router = APIRouter(tags=["clips"])


@router.get("/projects/{project_id}/clips", response_model=list[ClipOut])
def list_clips(project_id: str, db_path: Path = Depends(get_db_path)):
    return [ClipOut.from_row(r) for r in services.clips.list_clips_for_project(db_path, project_id)]


@router.get("/clips/{clip_id}", response_model=ClipOut)
def get_clip(clip_id: str, db_path: Path = Depends(get_db_path)):
    clip = services.clips.get_clip(db_path, clip_id)
    if not clip:
        raise HTTPException(404, f"no existe el clip {clip_id!r}")
    return ClipOut.from_row(clip)


@router.patch("/clips/{clip_id}/rating", response_model=ClipOut)
def set_rating(clip_id: str, body: RatingIn, db_path: Path = Depends(get_db_path)):
    clip = services.clips.get_clip(db_path, clip_id)
    if not clip:
        raise HTTPException(404, f"no existe el clip {clip_id!r}")
    services.clips.set_rating(db_path, clip_id, body.rating)
    return ClipOut.from_row(services.clips.get_clip(db_path, clip_id))


@router.post("/clips/{clip_id}/edit", response_model=JobOut, status_code=201)
def edit_clip(clip_id: str, body: EditClipIn, db_path: Path = Depends(get_db_path)):
    # Import diferido — mismo motivo que en routes/jobs.py: evita pagar
    # el costo de cargar faster_whisper en cascada en cada arranque de
    # rutas si nunca se crea/edita ningún job.
    from apps.worker.app.runner import create_clip_edit_job

    clip = services.clips.get_clip(db_path, clip_id)
    if not clip:
        raise HTTPException(404, f"no existe el clip {clip_id!r}")
    if not body.segments:
        raise HTTPException(400, "el clip editado necesita al menos un segmento")

    segments = [{"start_ms": s.start_ms, "end_ms": s.end_ms} for s in body.segments]
    job_id = create_clip_edit_job(
        db_path, clip["project_id"], clip_id, segments, avatar_enabled=body.avatar_enabled
    )
    return services.jobs.get_job(db_path, job_id)


@router.get("/clips/{clip_id}/file")
def get_clip_file(clip_id: str, db_path: Path = Depends(get_db_path)):
    clip = services.clips.get_clip(db_path, clip_id)
    if not clip or not clip.get("export_path"):
        raise HTTPException(404, f"no existe el clip {clip_id!r}, o todavía no se renderizó")
    path = Path(clip["export_path"])
    if not path.exists():
        raise HTTPException(404, f"el archivo exportado de {clip_id!r} ya no está en disco")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@router.get("/clips/{clip_id}/subtitle")
def get_clip_subtitle(clip_id: str, db_path: Path = Depends(get_db_path)):
    clip = services.clips.get_clip(db_path, clip_id)
    if not clip or not clip.get("subtitle_path"):
        raise HTTPException(404, f"{clip_id!r} no tiene subtítulos generados")
    path = Path(clip["subtitle_path"])
    if not path.exists():
        raise HTTPException(404, f"el archivo de subtítulos de {clip_id!r} ya no está en disco")
    return FileResponse(path, media_type="text/plain", filename=path.name)
