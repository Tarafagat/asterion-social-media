"""El 'worker' no es un proceso aparte — ver el comentario de paquete en
`app.asterion`. Es un hilo de Python nativo (no una tarea `asyncio`)
corriendo adentro del mismo proceso que FastAPI, porque las etapas
pesadas (`ffmpeg`, `faster-whisper`) son llamadas BLOQUEANTES — meterlas
en una tarea async bloquearía el event loop entero, y la API dejaría de
responder mientras un job procesa. Un hilo aparte deja que la API siga
atendiendo requests (incluido '¿cómo va este job?') mientras el trabajo
pesado corre en paralelo.

Cola: la tabla `jobs` de SQLite, con `status='queued'` — no hace falta
Redis ni una librería de colas para un worker que procesa de a uno.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path

from packages.config import Settings
from packages.storage import ProjectLayout, get_connection

from packages.avatar import sadtalker_runner, tts_piper
from packages.editorial import PlannedClip
from packages.media import replace_audio
from packages.transcription import Transcript

from .pipeline import analyze, extract_audio, inspect, plan_edits, render, select_clips, transcribe, validate

logger = logging.getLogger("worker")

POLL_INTERVAL_S = 2.0


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _set_job(db_path: Path, job_id: str, **fields) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    with get_connection(db_path) as conn:
        conn.execute(
            f"UPDATE jobs SET {sets}, updated_at = ? WHERE id = ?",
            (*fields.values(), _now_iso(), job_id),
        )


def _set_project(db_path: Path, project_id: str, **fields) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    with get_connection(db_path) as conn:
        conn.execute(
            f"UPDATE projects SET {sets}, updated_at = ? WHERE id = ?",
            (*fields.values(), _now_iso(), project_id),
        )


def reconcile_orphaned_jobs(db_path: Path) -> int:
    """Al arrancar, cualquier job en 'running' es de un proceso anterior
    que murió a mitad de camino — un reinicio del plugin mata el hilo del
    worker sin pasar por el `except` de `process_job`, así que ese job
    nunca se marca 'failed' y queda trabado para siempre en el % de la
    etapa en la que estaba. Se marca 'failed' acá para que la UI lo
    muestre claro y el usuario pueda reintentar con 'Crear clips' en vez
    de ver una barra de progreso congelada sin explicación.
    """
    now = _now_iso()
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT id, project_id FROM jobs WHERE status = 'running'").fetchall()
        for row in rows:
            conn.execute(
                "UPDATE jobs SET status = 'failed', error = ?, finished_at = ?, updated_at = ? WHERE id = ?",
                ("Interrumpido por un reinicio del servidor. Crea los clips de nuevo para reintentar.", now, now, row["id"]),
            )
            conn.execute(
                "UPDATE projects SET status = 'failed', updated_at = ? WHERE id = ?",
                (now, row["project_id"]),
            )
    return len(rows)


def _next_queued_job(db_path: Path) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def _avatar_kwargs(project: dict) -> dict:
    """El avatar es config de PROYECTO (un video grabado, subido una vez
    — ver routes/projects.py) que se aplica a cualquier render de sus
    clips, tanto los del pipeline completo como los de una edición
    manual. Sin avatar subido, `render_clip` recibe `avatar_path=None` y
    no cambia nada de su comportamiento de hoy."""
    avatar_path = project.get("avatar_path")
    return {
        "avatar_path": Path(avatar_path) if avatar_path else None,
        "avatar_mode": project.get("avatar_mode") or "pip",
    }


def _process_pipeline_job(db_path: Path, settings: Settings, job: dict) -> None:
    job_id, project_id = job["id"], job["project_id"]

    with get_connection(db_path) as conn:
        project = dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    layout.ensure()
    source_path = layout.source_video(project["source_filename"])

    try:
        _set_job(db_path, job_id, stage="inspect", status="running", started_at=_now_iso())
        info = inspect.run(source_path)
        _set_project(
            db_path, project_id,
            duration_s=info.duration_s, width=info.width, height=info.height,
            has_audio=1 if info.has_audio else 0,
        )

        _set_job(db_path, job_id, stage="extract_audio")
        audio_path = extract_audio.run(layout, source_path)

        _set_job(db_path, job_id, stage="transcribe")
        transcript = transcribe.run(
            layout, audio_path,
            model_size=settings.transcription_model,
            language=settings.content_language,
        )

        _set_job(db_path, job_id, stage="analyze")
        block_plans = analyze.run(layout, project_id, transcript, settings)

        _set_job(db_path, job_id, stage="select_clips")
        merged = select_clips.run(project_id, block_plans)

        _set_job(db_path, job_id, stage="plan_edits")
        planned = plan_edits.run(layout, merged, settings.edit_formats_list, duration_s=info.duration_s)

        _set_job(db_path, job_id, stage="render")
        avatar_kwargs = _avatar_kwargs(project)
        for clip in planned:
            export_path, subtitle_path = render.run(layout, source_path, clip, transcript, **avatar_kwargs)
            result = validate.run(clip, export_path)
            with get_connection(db_path) as conn:
                conn.execute(
                    """INSERT INTO clips
                       (id, project_id, job_id, title, reason, layout, subtitle_style,
                        needs_review, segments_json, export_path, subtitle_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        clip.id, project_id, job_id, clip.title, clip.reason, clip.layout,
                        clip.subtitle_style, 1 if (clip.needs_review or not result.ok) else 0,
                        json.dumps(clip.segments),
                        str(export_path), str(subtitle_path) if subtitle_path else None,
                    ),
                )
            if not result.ok:
                logger.warning("clip %s con problemas de validación: %s", clip.id, result.issues)

        _set_job(db_path, job_id, stage="validate", status="done", finished_at=_now_iso())
        _set_project(db_path, project_id, status="done")

    except Exception as exc:  # cualquier etapa puede fallar — se registra, nunca se silencia
        logger.exception("job %s falló", job_id)
        _set_job(db_path, job_id, status="failed", error=str(exc), finished_at=_now_iso())
        _set_project(db_path, project_id, status="failed")


def _process_clip_edit_job(db_path: Path, settings: Settings, job: dict) -> None:
    """Re-renderiza UN clip ya existente con una lista de segmentos
    editada a mano (el editor del frontend) — nunca pisa el clip
    original, siempre inserta uno nuevo con `source_clip_id` apuntando
    al que se editó, para poder comparar/deshacer. Reusa exactamente el
    mismo `render.run()`/`validate.run()` que el pipeline completo, solo
    que arranca del transcript YA cacheado (sin re-transcribir) y de los
    segmentos que mandó el usuario en vez de los que propuso la IA."""
    job_id, project_id = job["id"], job["project_id"]
    payload = json.loads(job["payload"])
    source_clip_id = payload["clip_id"]
    new_segments = payload["segments"]
    use_avatar = bool(payload.get("avatar_enabled"))

    with get_connection(db_path) as conn:
        project = dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
        source_clip = dict(conn.execute("SELECT * FROM clips WHERE id = ?", (source_clip_id,)).fetchone())

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    source_path = layout.source_video(project["source_filename"])

    try:
        _set_job(db_path, job_id, stage="render", status="running", started_at=_now_iso())
        transcript = Transcript.from_dict(json.loads(layout.transcript_json().read_text(encoding="utf-8")))

        new_clip = PlannedClip(
            id=str(uuid.uuid4()),
            title=source_clip["title"],
            segments=new_segments,
            reason=source_clip["reason"] or "",
            layout=source_clip["layout"],
            subtitle_style=source_clip["subtitle_style"],
            needs_review=False,  # es una edición deliberada, no una propuesta de IA sin revisar
        )
        avatar_kwargs = _avatar_kwargs(project) if use_avatar else {"avatar_path": None, "avatar_mode": "pip"}
        export_path, subtitle_path = render.run(layout, source_path, new_clip, transcript, **avatar_kwargs)

        _set_job(db_path, job_id, stage="validate")
        result = validate.run(new_clip, export_path)
        with get_connection(db_path) as conn:
            conn.execute(
                """INSERT INTO clips
                   (id, project_id, job_id, title, reason, layout, subtitle_style,
                    needs_review, segments_json, export_path, subtitle_path, source_clip_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_clip.id, project_id, job_id, new_clip.title, new_clip.reason, new_clip.layout,
                    new_clip.subtitle_style, 0 if result.ok else 1,
                    json.dumps(new_clip.segments),
                    str(export_path), str(subtitle_path) if subtitle_path else None,
                    source_clip_id,
                ),
            )
        if not result.ok:
            logger.warning("clip editado %s con problemas de validación: %s", new_clip.id, result.issues)

        _set_job(db_path, job_id, status="done", finished_at=_now_iso())

    except Exception as exc:
        logger.exception("job de edición %s falló", job_id)
        _set_job(db_path, job_id, status="failed", error=str(exc), finished_at=_now_iso())


def _process_avatar_generate_job(db_path: Path, settings: Settings, job: dict) -> None:
    """Guion (+ opcionalmente un audio propio) + foto -> video de la cara
    hablando, vía Piper (TTS local) + SadTalker (aislado, ver
    packages/avatar/sadtalker_runner.py). El resultado se guarda como el
    avatar DEL PROYECTO (projects.avatar_path) — desde ahí reusa, sin
    cambios, el mismo compositing pip/fondo que ya usa un avatar grabado
    a mano (ver _avatar_kwargs/render.run)."""
    job_id, project_id = job["id"], job["project_id"]
    payload = json.loads(job["payload"])
    image_path = Path(payload["image_path"])
    script_text = payload.get("script_text")
    uploaded_audio_path = payload.get("audio_path")
    voice_id = payload.get("voice_id") or tts_piper.DEFAULT_VOICE

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    layout.ensure()

    try:
        _set_job(db_path, job_id, stage="tts", status="running", started_at=_now_iso())
        if uploaded_audio_path:
            audio_path = Path(uploaded_audio_path)
        else:
            if not script_text or not script_text.strip():
                raise ValueError("falta el guion (o un audio propio) para generar la voz")
            audio_path = tts_piper.synthesize(
                script_text, layout.avatar_source_dir / f"{job_id}.wav", voice_id=voice_id
            )

        _set_job(db_path, job_id, stage="sadtalker", progress_pct=67)
        out_video = layout.avatar_source_dir / f"{job_id}.mp4"

        def _on_sadtalker_progress(pct: int) -> None:
            # 'sadtalker' ocupa el tramo 67-100% del job (ver
            # STAGE_ORDER_BY_KIND en apps/api/app/services/jobs.py:
            # ["queued","tts","sadtalker","done"], 4 etapas) — el % que
            # reporta SadTalker puertas adentro (0-100 de SU propia
            # corrida, casi siempre de la etapa 'Face Renderer', la que
            # domina el tiempo real) se reescala a ese tramo.
            _set_job(db_path, job_id, progress_pct=67 + round(pct * 0.33))

        sadtalker_runner.generate_talking_head(image_path, audio_path, out_video, on_progress=_on_sadtalker_progress)

        _set_project(db_path, project_id, avatar_path=str(out_video))
        _set_job(db_path, job_id, stage="done", status="done", progress_pct=None, finished_at=_now_iso())

    except Exception as exc:
        logger.exception("avatar IA del proyecto %s falló", project_id)
        _set_job(db_path, job_id, status="failed", error=str(exc), finished_at=_now_iso())


def _process_transcribe_only_job(db_path: Path, settings: Settings, job: dict) -> None:
    """Solo las primeras 3 etapas del pipeline completo (inspect ->
    extract_audio -> transcribe), sin análisis con IA ni generación de
    clips — para cuando lo único que hace falta es EL TEXTO del video
    (para copiarlo y armar un guion para doblaje/avatar a mano, ver
    routes/projects.py::get_transcript). `transcribe.run()` ya cachea en
    transcripts/transcript.json (ver pipeline/transcribe.py) — si el
    proyecto ya corrió 'Crear clips' antes, esto es casi instantáneo."""
    job_id, project_id = job["id"], job["project_id"]

    with get_connection(db_path) as conn:
        project = dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    layout.ensure()
    source_path = layout.source_video(project["source_filename"])

    try:
        _set_job(db_path, job_id, stage="inspect", status="running", started_at=_now_iso())
        info = inspect.run(source_path)
        _set_project(
            db_path, project_id,
            duration_s=info.duration_s, width=info.width, height=info.height,
            has_audio=1 if info.has_audio else 0,
        )

        _set_job(db_path, job_id, stage="extract_audio")
        audio_path = extract_audio.run(layout, source_path)

        _set_job(db_path, job_id, stage="transcribe")
        transcribe.run(
            layout, audio_path,
            model_size=settings.transcription_model,
            language=settings.content_language,
        )

        _set_job(db_path, job_id, stage="done", status="done", finished_at=_now_iso())

    except Exception as exc:
        logger.exception("extraer texto del proyecto %s falló", project_id)
        _set_job(db_path, job_id, status="failed", error=str(exc), finished_at=_now_iso())


def _process_dub_video_job(db_path: Path, settings: Settings, job: dict) -> None:
    """Video FUENTE completo (nada recortado) con el audio original
    reemplazado por una narración nueva — guion -> voz con Piper ->
    ffmpeg reemplaza la pista de audio (ver packages/media/dub.py), que
    además ajusta la duración del video si la narración nueva no dura lo
    mismo que la original. Si el payload trae una foto, además se genera
    un avatar (SadTalker, con la MISMA voz) y se monta encima — nunca se
    reusa un avatar ya existente del proyecto, porque ese podría estar
    sincronizado con un guion distinto."""
    job_id, project_id = job["id"], job["project_id"]
    payload = json.loads(job["payload"])
    script_text = payload["script_text"]
    voice_id = payload.get("voice_id") or tts_piper.DEFAULT_VOICE
    avatar_image_path = payload.get("avatar_image_path")
    avatar_mode = payload.get("avatar_mode") or "pip"

    with get_connection(db_path) as conn:
        project = dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    layout.ensure()
    source_path = layout.source_video(project["source_filename"])

    try:
        _set_job(db_path, job_id, stage="tts", status="running", started_at=_now_iso())
        audio_path = tts_piper.synthesize(
            script_text, layout.avatar_source_dir / f"{job_id}_dub.wav", voice_id=voice_id
        )

        dub_avatar_path = None
        if avatar_image_path:
            _set_job(db_path, job_id, stage="sadtalker", progress_pct=40)

            def _on_sadtalker_progress(pct: int) -> None:
                # 'sadtalker' ocupa el tramo 40-75% acá (dub_video_avatar
                # tiene 5 etapas: queued/tts/sadtalker/mux/done) — 'mux'
                # es rápido en comparación, así que se le deja poco tramo.
                _set_job(db_path, job_id, progress_pct=40 + round(pct * 0.35))

            dub_avatar_path = layout.avatar_source_dir / f"{job_id}_dub_avatar.mp4"
            sadtalker_runner.generate_talking_head(
                Path(avatar_image_path), audio_path, dub_avatar_path, on_progress=_on_sadtalker_progress
            )

        _set_job(db_path, job_id, stage="mux", progress_pct=None)
        out_video = layout.exports_dir / f"{job_id}_dub.mp4"
        replace_audio(source_path, audio_path, out_video, avatar_path=dub_avatar_path, avatar_mode=avatar_mode)

        _set_project(db_path, project_id, dubbed_video_path=str(out_video))
        _set_job(db_path, job_id, stage="done", status="done", progress_pct=None, finished_at=_now_iso())

    except Exception as exc:
        logger.exception("dub de video del proyecto %s falló", project_id)
        _set_job(db_path, job_id, status="failed", error=str(exc), finished_at=_now_iso())


def process_job(db_path: Path, settings: Settings, job: dict) -> None:
    kind = job.get("kind")
    if kind == "clip_edit":
        _process_clip_edit_job(db_path, settings, job)
    elif kind == "avatar_generate":
        _process_avatar_generate_job(db_path, settings, job)
    elif kind in ("dub_video", "dub_video_avatar"):
        _process_dub_video_job(db_path, settings, job)
    elif kind == "transcribe_only":
        _process_transcribe_only_job(db_path, settings, job)
    else:
        _process_pipeline_job(db_path, settings, job)


def create_job(db_path: Path, project_id: str) -> str:
    job_id = str(uuid.uuid4())
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO jobs (id, project_id, kind, stage, status) VALUES (?, ?, 'pipeline', 'queued', 'queued')",
            (job_id, project_id),
        )
    _set_project(db_path, project_id, status="processing")
    return job_id


def create_clip_edit_job(db_path: Path, project_id: str, clip_id: str, segments: list[dict], *, avatar_enabled: bool = False) -> str:
    job_id = str(uuid.uuid4())
    payload = json.dumps({"clip_id": clip_id, "segments": segments, "avatar_enabled": avatar_enabled})
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO jobs (id, project_id, kind, payload, stage, status) VALUES (?, ?, 'clip_edit', ?, 'render', 'queued')",
            (job_id, project_id, payload),
        )
    return job_id


def create_avatar_generate_job(
    db_path: Path,
    project_id: str,
    image_path: str,
    *,
    script_text: str | None = None,
    audio_path: str | None = None,
    voice_id: str | None = None,
) -> str:
    job_id = str(uuid.uuid4())
    payload = json.dumps({
        "image_path": image_path, "script_text": script_text,
        "audio_path": audio_path, "voice_id": voice_id,
    })
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO jobs (id, project_id, kind, payload, stage, status) VALUES (?, ?, 'avatar_generate', ?, 'queued', 'queued')",
            (job_id, project_id, payload),
        )
    return job_id


def create_dub_video_job(
    db_path: Path,
    project_id: str,
    script_text: str,
    *,
    voice_id: str | None = None,
    avatar_image_path: str | None = None,
    avatar_mode: str | None = None,
) -> str:
    job_id = str(uuid.uuid4())
    payload = json.dumps({
        "script_text": script_text, "voice_id": voice_id,
        "avatar_image_path": avatar_image_path, "avatar_mode": avatar_mode,
    })
    # Dos 'kind' distintos (no un flag en el payload) para que el % de
    # progreso tenga la cantidad correcta de etapas en cada caso — ver
    # STAGE_ORDER_BY_KIND en apps/api/app/services/jobs.py. El worker
    # despacha los dos al mismo _process_dub_video_job (ver abajo).
    kind = "dub_video_avatar" if avatar_image_path else "dub_video"
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO jobs (id, project_id, kind, payload, stage, status) VALUES (?, ?, ?, ?, 'queued', 'queued')",
            (job_id, project_id, kind, payload),
        )
    return job_id


def create_transcribe_only_job(db_path: Path, project_id: str) -> str:
    job_id = str(uuid.uuid4())
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO jobs (id, project_id, kind, stage, status) VALUES (?, ?, 'transcribe_only', 'queued', 'queued')",
            (job_id, project_id),
        )
    return job_id


def worker_loop(db_path: Path, settings: Settings, stop_event: threading.Event) -> None:
    logger.info("worker: loop arrancado, sondeando cada %.0fs", POLL_INTERVAL_S)
    while not stop_event.is_set():
        job = _next_queued_job(db_path)
        if job is None:
            stop_event.wait(POLL_INTERVAL_S)
            continue
        process_job(db_path, settings, job)


def start_worker_thread(db_path: Path, settings: Settings) -> tuple[threading.Thread, threading.Event]:
    stop_event = threading.Event()
    thread = threading.Thread(
        target=worker_loop, args=(db_path, settings, stop_event), daemon=True, name="asm-worker"
    )
    thread.start()
    return thread, stop_event
