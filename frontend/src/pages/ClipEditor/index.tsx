import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ClipSegment } from "../../api/client";
import JobProgress from "../../components/JobProgress";

// Los tres formatos que sabe renderizar el backend (ver
// packages/media/render.py::LAYOUT_DIMENSIONS). El ratio es solo para el
// marco de previsualización de acá.
const LAYOUTS: { id: string; label: string; ratio: string; size: string }[] = [
  { id: "vertical", label: "Vertical · 9:16 (Shorts / Reels / TikTok)", ratio: "9 / 16", size: "1080×1920" },
  { id: "horizontal", label: "Horizontal · 16:9 (YouTube)", ratio: "16 / 9", size: "1920×1080" },
  { id: "square", label: "Cuadrado · 1:1 (feed)", ratio: "1 / 1", size: "1080×1080" },
];

function fmt(ms: number): string {
  return (ms / 1000).toFixed(1);
}

function clock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function ClipEditorPage() {
  const { id: projectId, clipId } = useParams<{ id: string; clipId?: string }>();
  const isNew = !clipId;
  const qc = useQueryClient();

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId!),
  });
  const { data: clip } = useQuery({
    queryKey: ["clip", clipId],
    queryFn: () => api.getClip(clipId!),
    enabled: !!clipId,
  });
  // Para habilitar/deshabilitar la opción de subtítulos: quemarlos
  // necesita el texto del video (transcript.json), que se extrae aparte
  // desde el proyecto ("Extraer texto del video"). Sin eso, no se ofrece.
  const { data: transcript } = useQuery({
    queryKey: ["transcript", projectId],
    queryFn: () => api.getTranscript(projectId!),
  });
  const hasTranscript = !!transcript;

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [segments, setSegments] = useState<ClipSegment[] | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const [currentMs, setCurrentMs] = useState(0);
  const [metaMs, setMetaMs] = useState(0);
  const [title, setTitle] = useState("");
  const [layout, setLayout] = useState("vertical");
  const [subtitles, setSubtitles] = useState(false);
  const [avatarEnabled, setAvatarEnabled] = useState(false);
  const [playingSegment, setPlayingSegment] = useState<number | null>(null);
  const [savedJobId, setSavedJobId] = useState<string | null>(null);

  // Duración de referencia: la que ffprobe guardó al subir el video; si
  // por algún motivo no está (0), se cae a la que reporte el propio
  // <video> al cargar sus metadatos.
  const durationMs = Math.round((project?.duration_s ?? 0) * 1000) || metaMs;

  // Estado editable inicializado UNA sola vez (el mismo patrón que tenía
  // el editor antes): un clip existente arranca de sus segmentos/formato,
  // uno nuevo arranca con un segmento por defecto (los primeros 15s).
  if (segments === null) {
    if (clip) {
      setSegments(clip.segments.map((s) => ({ ...s })));
      setLayout(clip.layout);
      setTitle(clip.title);
    } else if (isNew && project) {
      const end = durationMs > 0 ? Math.min(durationMs, 15000) : 15000;
      setSegments([{ start_ms: 0, end_ms: end }]);
    }
  }

  const { data: jobs } = useQuery({
    queryKey: ["jobs", projectId],
    queryFn: () => api.listJobs(projectId!),
    enabled: !!savedJobId,
    refetchInterval: (query) => {
      const job = query.state.data?.find((j) => j.id === savedJobId);
      const isFinal = job?.status === "done" || job?.status === "failed";
      return job && !isFinal ? 1500 : false;
    },
  });
  const savedJob = jobs?.find((j) => j.id === savedJobId) ?? null;

  const createMutation = useMutation({
    mutationFn: () =>
      api.createClip(projectId!, {
        segments: segments!,
        layout,
        subtitles: subtitles && hasTranscript,
        title: title.trim() || null,
        avatar_enabled: avatarEnabled,
      }),
    onSuccess: (job) => {
      setSavedJobId(job.id);
      qc.invalidateQueries({ queryKey: ["jobs", projectId] });
    },
  });
  const saveMutation = useMutation({
    mutationFn: () => api.editClip(clipId!, segments!, avatarEnabled),
    onSuccess: (job) => {
      setSavedJobId(job.id);
      qc.invalidateQueries({ queryKey: ["jobs", projectId] });
    },
  });
  const mutation = isNew ? createMutation : saveMutation;

  if (!project || segments === null || (!isNew && !clip)) return <p>Cargando…</p>;

  if (!project.source_filename) {
    return (
      <div>
        <Link to={`/projects/${projectId}`} style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.5)" }}>
          ← Volver al proyecto
        </Link>
        <p style={{ marginTop: "1rem" }}>Este proyecto todavía no tiene un video subido. Súbelo primero.</p>
      </div>
    );
  }

  const pct = (ms: number) => (durationMs > 0 ? Math.min(100, Math.max(0, (ms / durationMs) * 100)) : 0);
  const active = segments[activeIdx] ?? segments[0];
  const totalS = segments.reduce((acc, s) => acc + Math.max(0, s.end_ms - s.start_ms), 0) / 1000;
  const selectedLayout = LAYOUTS.find((l) => l.id === layout) ?? LAYOUTS[0];

  function seek(ms: number) {
    const v = videoRef.current;
    if (v && durationMs > 0) v.currentTime = Math.min(durationMs, Math.max(0, ms)) / 1000;
  }

  function seekFromTrack(e: React.MouseEvent<HTMLDivElement>) {
    if (durationMs <= 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    seek(frac * durationMs);
  }

  function patchActive(field: "start_ms" | "end_ms", ms: number) {
    setSegments((prev) => {
      const next = [...prev!];
      const seg = { ...next[activeIdx] };
      const clamped = Math.max(0, Math.min(durationMs || ms, Math.round(ms)));
      if (field === "start_ms") seg.start_ms = Math.min(clamped, seg.end_ms - 100);
      else seg.end_ms = Math.max(clamped, seg.start_ms + 100);
      next[activeIdx] = seg;
      return next;
    });
  }

  function updateSegment(i: number, field: "start_ms" | "end_ms", seconds: number) {
    setSegments((prev) => {
      const next = [...prev!];
      const ms = Math.max(0, Math.min(durationMs || Math.round(seconds * 1000), Math.round(seconds * 1000)));
      next[i] = { ...next[i], [field]: ms };
      return next;
    });
  }

  function removeSegment(i: number) {
    setSegments((prev) => prev!.filter((_, idx) => idx !== i));
    setActiveIdx((idx) => (idx >= i && idx > 0 ? idx - 1 : idx));
  }

  function moveSegment(i: number, dir: -1 | 1) {
    setSegments((prev) => {
      const next = [...prev!];
      const j = i + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  }

  function addSegment() {
    setSegments((prev) => {
      const last = prev![prev!.length - 1];
      const start = last ? last.end_ms : 0;
      const end = Math.min(durationMs || start + 5000, start + 5000);
      const next = [...prev!, { start_ms: start, end_ms: Math.max(end, start + 100) }];
      setActiveIdx(next.length - 1);
      return next;
    });
  }

  function previewSegment(i: number) {
    const v = videoRef.current;
    const seg = segments![i];
    if (!v || !seg) return;
    v.currentTime = seg.start_ms / 1000;
    void v.play();
    setPlayingSegment(i);
  }

  return (
    <div>
      <Link to={`/projects/${projectId}`} style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.5)" }}>
        ← Volver al proyecto
      </Link>
      <h1 style={{ fontSize: "1.6rem", margin: "0.5rem 0 0.2rem" }}>
        {isNew ? "Editor de video" : `Editar: ${clip!.title}`}
      </h1>
      <p style={{ color: "rgba(255,255,255,0.5)", marginTop: 0, marginBottom: "1.5rem" }}>
        {isNew
          ? "Reproduce el video, marca el inicio y el fin de cada corte y crea el clip. Puedes juntar varios tramos en un mismo clip."
          : "Guardar crea un clip NUEVO — el original no se toca ni se pisa."}
      </p>

      {/* Reproductor + línea de tiempo */}
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <video
          ref={videoRef}
          src={api.sourceFileUrl(projectId!)}
          controls
          preload="metadata"
          onLoadedMetadata={(e) => {
            if (!project.duration_s) setMetaMs(Math.round(e.currentTarget.duration * 1000));
          }}
          onTimeUpdate={(e) => {
            const t = Math.round(e.currentTarget.currentTime * 1000);
            setCurrentMs(t);
            if (playingSegment !== null) {
              const seg = segments[playingSegment];
              if (seg && t >= seg.end_ms) {
                e.currentTarget.pause();
                setPlayingSegment(null);
              }
            }
          }}
          style={{
            display: "block",
            width: "100%",
            maxHeight: "48vh",
            background: "#000",
            borderRadius: "0.6rem",
            objectFit: "contain",
          }}
        />

        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap", marginTop: "0.8rem" }}>
          <code className="mono">
            {clock(currentMs)} / {clock(durationMs)}
          </code>
          <button className="btn-outline" onClick={() => patchActive("start_ms", currentMs)}>
            ⇤ Marcar inicio (seg. {activeIdx + 1})
          </button>
          <button className="btn-outline" onClick={() => patchActive("end_ms", currentMs)}>
            Marcar fin ⇥ (seg. {activeIdx + 1})
          </button>
          <button className="btn-outline" onClick={() => previewSegment(activeIdx)}>
            ▶ Previsualizar segmento
          </button>
        </div>

        <div
          onClick={seekFromTrack}
          style={{
            position: "relative",
            height: 56,
            marginTop: "0.8rem",
            borderRadius: "0.5rem",
            overflow: "hidden",
            background: "#000",
            cursor: "pointer",
          }}
        >
          <img
            src={api.waveformUrl(projectId!)}
            alt=""
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
            style={{ width: "100%", height: "100%", objectFit: "fill", opacity: 0.5, display: "block" }}
          />
          {segments.map((s, i) => (
            <div
              key={i}
              onClick={(ev) => {
                ev.stopPropagation();
                setActiveIdx(i);
                seek(s.start_ms);
              }}
              title={`Segmento ${i + 1}: ${fmt(s.start_ms)}s – ${fmt(s.end_ms)}s`}
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: `${pct(s.start_ms)}%`,
                width: `${Math.max(0.4, pct(s.end_ms - s.start_ms))}%`,
                background: i === activeIdx ? "rgba(240,192,74,0.45)" : "rgba(240,192,74,0.18)",
                border: `1px solid ${i === activeIdx ? "var(--color-asterion-gold)" : "rgba(240,192,74,0.5)"}`,
                boxSizing: "border-box",
              }}
            />
          ))}
          <div style={{ position: "absolute", top: 0, bottom: 0, left: `${pct(currentMs)}%`, width: 2, background: "#fff" }} />
        </div>
        <p style={{ fontSize: "0.78rem", color: "rgba(255,255,255,0.4)", margin: "0.5rem 0 0" }}>
          Haz clic en la barra para saltar a ese punto. Los bloques dorados son los segmentos del clip; el borde más
          brillante es el segmento activo (sobre el que actúan "Marcar inicio/fin").
        </p>
      </div>

      {/* Segmentos */}
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
          <h3 style={{ margin: 0, fontSize: "0.9rem", color: "rgba(255,255,255,0.6)" }}>
            Segmentos ({totalS.toFixed(1)}s en total)
          </h3>
          <button className="btn-outline" onClick={addSegment}>
            + Agregar segmento
          </button>
        </div>

        {segments.map((s, i) => (
          <div
            key={i}
            onClick={() => setActiveIdx(i)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.75rem",
              padding: "0.6rem 0.5rem",
              borderRadius: "0.5rem",
              background: i === activeIdx ? "rgba(240,192,74,0.08)" : "transparent",
              borderTop: i > 0 ? "1px solid rgba(255,255,255,0.08)" : undefined,
              cursor: "pointer",
            }}
          >
            <span style={{ width: "1.5rem", color: i === activeIdx ? "var(--color-asterion-gold)" : "rgba(255,255,255,0.4)", fontSize: "0.85rem" }}>
              {i + 1}
            </span>
            <label style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }} onClick={(e) => e.stopPropagation()}>
              inicio (s)
              <input
                className="input-field"
                type="number"
                step={0.1}
                value={fmt(s.start_ms)}
                onChange={(e) => updateSegment(i, "start_ms", Number(e.target.value))}
                style={{ width: "5.5rem", marginLeft: "0.4rem" }}
              />
            </label>
            <label style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }} onClick={(e) => e.stopPropagation()}>
              fin (s)
              <input
                className="input-field"
                type="number"
                step={0.1}
                value={fmt(s.end_ms)}
                onChange={(e) => updateSegment(i, "end_ms", Number(e.target.value))}
                style={{ width: "5.5rem", marginLeft: "0.4rem" }}
              />
            </label>
            <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.4)" }}>{fmt(Math.max(0, s.end_ms - s.start_ms))}s</span>
            <div style={{ display: "flex", gap: "0.3rem", marginLeft: "auto" }} onClick={(e) => e.stopPropagation()}>
              <button className="btn-outline" disabled={i === 0} onClick={() => moveSegment(i, -1)}>
                ↑
              </button>
              <button className="btn-outline" disabled={i === segments.length - 1} onClick={() => moveSegment(i, 1)}>
                ↓
              </button>
              <button
                className="btn-outline"
                disabled={segments.length <= 1}
                onClick={() => removeSegment(i)}
                style={{ color: "var(--color-danger)" }}
              >
                Eliminar
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Opciones de salida */}
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        {isNew && (
          <label style={{ display: "block", fontSize: "0.8rem", color: "rgba(255,255,255,0.5)", marginBottom: "0.9rem" }}>
            Título del clip
            <input
              className="input-field"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Mi clip"
              style={{ display: "block", marginTop: "0.3rem", maxWidth: "24rem" }}
            />
          </label>
        )}

        <div style={{ display: "flex", gap: "1.2rem", alignItems: "flex-end", flexWrap: "wrap" }}>
          <label style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>
            Formato
            <select
              className="input-field"
              value={layout}
              disabled={!isNew}
              onChange={(e) => setLayout(e.target.value)}
              style={{ display: "block", marginTop: "0.3rem", width: "auto", minWidth: "20rem", opacity: isNew ? 1 : 0.6 }}
            >
              {LAYOUTS.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
          <div
            title={selectedLayout.label}
            style={{
              width: 42,
              aspectRatio: selectedLayout.ratio,
              maxHeight: 74,
              border: "1px solid var(--color-asterion-gold)",
              borderRadius: 4,
              background: "rgba(240,192,74,0.12)",
            }}
          />
          <span style={{ fontSize: "0.78rem", color: "rgba(255,255,255,0.4)" }}>{selectedLayout.size}</span>
        </div>
        {!isNew && (
          <p style={{ fontSize: "0.78rem", color: "rgba(255,255,255,0.4)", margin: "0.5rem 0 0" }}>
            Al editar un clip existente se conserva su formato original.
          </p>
        )}

        {isNew && (
          <label
            style={{ display: "flex", alignItems: "center", gap: "0.6rem", fontSize: "0.9rem", marginTop: "1rem", opacity: hasTranscript ? 1 : 0.6 }}
          >
            <input
              type="checkbox"
              checked={subtitles && hasTranscript}
              disabled={!hasTranscript}
              onChange={(e) => setSubtitles(e.target.checked)}
            />
            Quemar subtítulos en el clip
          </label>
        )}
        {isNew && !hasTranscript && (
          <p style={{ fontSize: "0.78rem", color: "rgba(255,255,255,0.4)", margin: "0.4rem 0 0" }}>
            Para quemar subtítulos, primero usa "Extraer texto del video" en el{" "}
            <Link to={`/projects/${projectId}`} style={{ color: "var(--color-asterion-gold-light)" }}>
              proyecto
            </Link>
            . Sin eso, el clip se genera igual pero sin subtítulos (y más rápido).
          </p>
        )}

        {project.has_avatar && (
          <label style={{ display: "flex", alignItems: "center", gap: "0.6rem", fontSize: "0.9rem", marginTop: "1rem" }}>
            <input type="checkbox" checked={avatarEnabled} onChange={(e) => setAvatarEnabled(e.target.checked)} />
            Incluir avatar ({project.avatar_mode === "background" ? "de fondo" : "burbuja"}) en el clip
          </label>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <button
          className="btn-gold"
          disabled={mutation.isPending || (savedJob ? savedJob.status !== "done" && savedJob.status !== "failed" : false)}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? "Enviando…" : isNew ? "Crear clip" : "Guardar nueva versión"}
        </button>
        {mutation.isError && (
          <span style={{ color: "var(--color-danger)", fontSize: "0.85rem" }}>{(mutation.error as Error).message}</span>
        )}
      </div>

      {savedJob && (
        <div style={{ marginTop: "1.5rem" }}>
          <JobProgress job={savedJob} />
          {savedJob.status === "done" && (
            <p style={{ marginTop: "0.8rem" }}>
              <Link to={`/projects/${projectId}`} style={{ color: "var(--color-asterion-gold-light)" }}>
                Ver el clip en el proyecto →
              </Link>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
