from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from packages.config import Settings
from packages.media import generate_waveform_png
from packages.storage import ProjectLayout
from packages.transcription import Transcript

from .. import services
from ..deps import get_db_path, get_settings_dep
from ..schemas import AvatarModeIn, JobOut, ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, db_path: Path = Depends(get_db_path)):
    row = services.projects.create_project(db_path, body.name)
    return ProjectOut.from_row(row)


@router.get("", response_model=list[ProjectOut])
def list_projects(db_path: Path = Depends(get_db_path)):
    return [ProjectOut.from_row(r) for r in services.projects.list_projects(db_path)]


@router.get("/avatar/voices")
def list_avatar_voices() -> dict:
    from packages.avatar import tts_piper
    return {"voices": [{"id": k, "label": v.label} for k, v in tts_piper.AVAILABLE_VOICES.items()]}


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


@router.post("/{project_id}/transcript", response_model=JobOut, status_code=201)
def extract_transcript(project_id: str, db_path: Path = Depends(get_db_path)):
    """Solo inspect+extract_audio+transcribe (ver
    apps/worker/app/runner.py::_process_transcribe_only_job) — para
    sacar el TEXTO del video sin correr análisis de IA ni generar
    clips, pensado para copiarlo y armar un guion de doblaje/avatar a
    mano (ver get_transcript abajo)."""
    from apps.worker.app.runner import create_transcribe_only_job

    project = services.projects.get_project(db_path, project_id)
    if not project:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")
    if not project.get("source_filename"):
        raise HTTPException(400, "este proyecto todavía no tiene ningún video subido")

    job_id = create_transcribe_only_job(db_path, project_id)
    return services.jobs.get_job(db_path, job_id)


@router.get("/{project_id}/transcript")
def get_transcript(
    project_id: str,
    db_path: Path = Depends(get_db_path),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    project = services.projects.get_project(db_path, project_id)
    if not project:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    checkpoint = layout.transcript_json()
    if not checkpoint.exists():
        raise HTTPException(404, "todavía no se extrajo el texto de este video")

    transcript = Transcript.from_dict(json.loads(checkpoint.read_text(encoding="utf-8")))
    return {"text": transcript.full_text(), "language": transcript.language}


@router.get("/{project_id}/waveform.png")
def get_waveform(
    project_id: str,
    db_path: Path = Depends(get_db_path),
    settings: Settings = Depends(get_settings_dep),
):
    """Una sola imagen por proyecto, generada la primera vez que se pide
    y cacheada después — el editor de clips la usa para mostrar/recortar
    sobre la forma de onda del audio fuente completo (ver packages/media/
    waveform.py: los tiempos de un clip son absolutos sobre ESTE audio)."""
    project = services.projects.get_project(db_path, project_id)
    if not project:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")
    if not project.get("duration_s"):
        raise HTTPException(409, "este proyecto todavía no terminó de procesarse — todavía no hay audio extraído")

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    audio_path = layout.extracted_audio()
    if not audio_path.exists():
        raise HTTPException(409, "el audio de este proyecto todavía no se extrajo")

    out_png = layout.audio_dir / "waveform.png"
    if not out_png.exists():
        generate_waveform_png(audio_path, out_png, duration_s=project["duration_s"])
    return FileResponse(out_png, media_type="image/png")


@router.post("/{project_id}/avatar", response_model=ProjectOut)
async def upload_avatar(
    project_id: str,
    file: UploadFile,
    db_path: Path = Depends(get_db_path),
    settings: Settings = Depends(get_settings_dep),
):
    project = services.projects.get_project(db_path, project_id)
    if not project:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    avatar_dir = layout.root / "avatar"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    dest = avatar_dir / f"avatar{Path(file.filename or 'avatar.mp4').suffix or '.mp4'}"
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    services.projects.set_avatar(db_path, project_id, str(dest))
    return ProjectOut.from_row(services.projects.get_project(db_path, project_id))


@router.delete("/{project_id}/avatar", response_model=ProjectOut)
def delete_avatar(project_id: str, db_path: Path = Depends(get_db_path)):
    project = services.projects.get_project(db_path, project_id)
    if not project:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")
    if project.get("avatar_path"):
        path = Path(project["avatar_path"])
        if path.exists():
            path.unlink()
    services.projects.set_avatar(db_path, project_id, None)
    return ProjectOut.from_row(services.projects.get_project(db_path, project_id))


@router.put("/{project_id}/avatar-mode", response_model=ProjectOut)
def set_avatar_mode(project_id: str, body: AvatarModeIn, db_path: Path = Depends(get_db_path)):
    project = services.projects.get_project(db_path, project_id)
    if not project:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")
    services.projects.set_avatar_mode(db_path, project_id, body.avatar_mode)
    return ProjectOut.from_row(services.projects.get_project(db_path, project_id))


@router.post("/{project_id}/avatar/generate", response_model=JobOut, status_code=201)
async def generate_avatar(
    project_id: str,
    image: UploadFile,
    script: str | None = Form(None),
    audio: UploadFile | None = None,
    voice_id: str | None = Form(None),
    db_path: Path = Depends(get_db_path),
    settings: Settings = Depends(get_settings_dep),
):
    """Avatar IA: una foto + (un guion que se convierte a voz con Piper,
    o un audio propio ya grabado) -> SadTalker anima la foto con ese
    audio. El .mp4 resultante queda como el avatar del proyecto, mismo
    lugar que un avatar grabado subido a mano (ver upload_avatar) — todo
    el compositing pip/fondo de abajo es el mismo sin cambios."""
    from packages.avatar import sadtalker_runner
    from apps.worker.app.runner import create_avatar_generate_job

    project = services.projects.get_project(db_path, project_id)
    if not project:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")
    if not sadtalker_runner.is_installed():
        raise HTTPException(503, "SadTalker no está instalado en este servidor — ver vendor/SADTALKER_SETUP.md")
    if not audio and not (script and script.strip()):
        raise HTTPException(400, "mandá un guion (para generar la voz) o un audio propio")

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    layout.ensure()

    image_dest = layout.avatar_source_dir / f"source{Path(image.filename or 'avatar.png').suffix or '.png'}"
    with image_dest.open("wb") as out:
        while chunk := await image.read(1024 * 1024):
            out.write(chunk)

    audio_dest_str = None
    if audio:
        audio_dest = layout.avatar_source_dir / f"source_audio{Path(audio.filename or 'audio.wav').suffix or '.wav'}"
        with audio_dest.open("wb") as out:
            while chunk := await audio.read(1024 * 1024):
                out.write(chunk)
        audio_dest_str = str(audio_dest)

    job_id = create_avatar_generate_job(
        db_path, project_id, str(image_dest),
        script_text=script, audio_path=audio_dest_str, voice_id=voice_id,
    )
    return services.jobs.get_job(db_path, job_id)


@router.post("/{project_id}/dub", response_model=JobOut, status_code=201)
async def dub_video(
    project_id: str,
    script: str = Form(...),
    voice_id: str | None = Form(None),
    avatar_image: UploadFile | None = None,
    avatar_mode: str | None = Form(None),
    db_path: Path = Depends(get_db_path),
    settings: Settings = Depends(get_settings_dep),
):
    """Procesa el video FUENTE completo (no un clip corto) reemplazando
    su audio original por una narración nueva generada del guion con
    Piper TTS — ver apps/worker/app/runner.py::_process_dub_video_job y
    packages/media/dub.py. `avatar_image` es opcional: si se manda, se
    genera un avatar (SadTalker, con el mismo guion) y se monta encima
    del video ya doblado — nunca se reusa el avatar que el proyecto ya
    tenga configurado, porque podría estar sincronizado con otro guion."""
    from packages.avatar import sadtalker_runner
    from apps.worker.app.runner import create_dub_video_job

    project = services.projects.get_project(db_path, project_id)
    if not project:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")
    if not project.get("source_filename"):
        raise HTTPException(400, "este proyecto todavía no tiene ningún video subido")
    if not script.strip():
        raise HTTPException(400, "falta el guion")
    if avatar_image and not sadtalker_runner.is_installed():
        raise HTTPException(503, "SadTalker no está instalado en este servidor — ver vendor/SADTALKER_SETUP.md")

    image_dest_str = None
    if avatar_image:
        layout = ProjectLayout(settings.data_dir_path(), project_id)
        layout.ensure()
        image_dest = layout.avatar_source_dir / f"dub_source{Path(avatar_image.filename or 'avatar.png').suffix or '.png'}"
        with image_dest.open("wb") as out:
            while chunk := await avatar_image.read(1024 * 1024):
                out.write(chunk)
        image_dest_str = str(image_dest)

    job_id = create_dub_video_job(
        db_path, project_id, script,
        voice_id=voice_id, avatar_image_path=image_dest_str, avatar_mode=avatar_mode,
    )
    return services.jobs.get_job(db_path, job_id)


@router.get("/{project_id}/dub/file")
def get_dubbed_video(
    project_id: str,
    db_path: Path = Depends(get_db_path),
):
    project = services.projects.get_project(db_path, project_id)
    if not project:
        raise HTTPException(404, f"no existe el proyecto {project_id!r}")
    dubbed_path = project.get("dubbed_video_path")
    if not dubbed_path or not Path(dubbed_path).exists():
        raise HTTPException(404, "este proyecto todavía no tiene un video con audio reemplazado")
    return FileResponse(dubbed_path, media_type="video/mp4", filename=f"{project['name']}-doblado.mp4")
