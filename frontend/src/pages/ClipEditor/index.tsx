import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ClipSegment } from "../../api/client";
import JobProgress from "../../components/JobProgress";

function fmt(ms: number): string {
  const s = ms / 1000;
  return s.toFixed(1);
}

export default function ClipEditorPage() {
  const { id: projectId, clipId } = useParams<{ id: string; clipId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId!),
  });
  const { data: clip } = useQuery({
    queryKey: ["clip", clipId],
    queryFn: () => api.getClip(clipId!),
  });

  const [segments, setSegments] = useState<ClipSegment[] | null>(null);
  const [avatarEnabled, setAvatarEnabled] = useState(false);
  const [savedJobId, setSavedJobId] = useState<string | null>(null);

  // El clip llega async — recién ahí se inicializa el estado editable,
  // una sola vez (si el usuario ya está editando, un refetch de fondo no
  // debe pisarle los cambios a medio hacer).
  if (segments === null && clip) {
    setSegments(clip.segments.map((s) => ({ ...s })));
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

  const saveMutation = useMutation({
    mutationFn: () => api.editClip(clipId!, segments!, avatarEnabled),
    onSuccess: (job) => {
      setSavedJobId(job.id);
      qc.invalidateQueries({ queryKey: ["jobs", projectId] });
    },
  });

  if (!clip || !project || !segments) return <p>Cargando…</p>;

  const durationMs = Math.round((project.duration_s ?? 0) * 1000);

  function updateSegment(i: number, field: "start_ms" | "end_ms", seconds: number) {
    setSegments((prev) => {
      const next = [...prev!];
      const ms = Math.max(0, Math.min(durationMs, Math.round(seconds * 1000)));
      next[i] = { ...next[i], [field]: ms };
      return next;
    });
  }

  function removeSegment(i: number) {
    setSegments((prev) => prev!.filter((_, idx) => idx !== i));
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
      const end = Math.min(durationMs, start + 5000);
      return [...prev!, { start_ms: start, end_ms: Math.max(end, start + 100) }];
    });
  }

  const totalS = segments.reduce((acc, s) => acc + Math.max(0, s.end_ms - s.start_ms), 0) / 1000;

  return (
    <div>
      <Link to={`/projects/${projectId}`} style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.5)" }}>
        ← Volver al proyecto
      </Link>
      <h1 style={{ fontSize: "1.6rem", margin: "0.5rem 0 0.2rem" }}>Editar: {clip.title}</h1>
      <p style={{ color: "rgba(255,255,255,0.5)", marginTop: 0, marginBottom: "1.5rem" }}>
        Guardar crea un clip NUEVO — el original ({fmt(
          clip.segments.reduce((a, s) => a + (s.end_ms - s.start_ms), 0)
        )}s) no se toca ni se pisa.
      </p>

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0, fontSize: "0.9rem", color: "rgba(255,255,255,0.6)" }}>
          Forma de onda del video fuente completo — cada franja de color es un segmento de este clip
        </h3>
        <div style={{ position: "relative", height: 90, borderRadius: "0.5rem", overflow: "hidden", background: "#000" }}>
          <img
            src={api.waveformUrl(projectId!)}
            alt="forma de onda"
            style={{ width: "100%", height: "100%", objectFit: "fill", display: "block", opacity: 0.6 }}
          />
          {segments.map((s, i) => (
            <div
              key={i}
              title={`Segmento ${i + 1}: ${fmt(s.start_ms)}s – ${fmt(s.end_ms)}s`}
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: `${(s.start_ms / durationMs) * 100}%`,
                width: `${Math.max(0.2, ((s.end_ms - s.start_ms) / durationMs) * 100)}%`,
                background: "rgba(240,192,74,0.35)",
                border: "1px solid var(--color-asterion-gold)",
                boxSizing: "border-box",
              }}
            />
          ))}
        </div>
      </div>

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
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.75rem",
              padding: "0.6rem 0",
              borderTop: i > 0 ? "1px solid rgba(255,255,255,0.08)" : undefined,
            }}
          >
            <span style={{ width: "1.5rem", color: "rgba(255,255,255,0.4)", fontSize: "0.85rem" }}>{i + 1}</span>
            <label style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>
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
            <label style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>
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
            <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.4)" }}>
              {fmt(Math.max(0, s.end_ms - s.start_ms))}s
            </span>
            <div style={{ display: "flex", gap: "0.3rem", marginLeft: "auto" }}>
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

      {project.has_avatar && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "0.6rem", fontSize: "0.9rem" }}>
            <input type="checkbox" checked={avatarEnabled} onChange={(e) => setAvatarEnabled(e.target.checked)} />
            Incluir avatar ({project.avatar_mode === "background" ? "de fondo" : "burbuja"}) en esta versión
          </label>
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <button
          className="btn-gold"
          disabled={saveMutation.isPending || (savedJob ? savedJob.status !== "done" && savedJob.status !== "failed" : false)}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending ? "Enviando…" : "Guardar nueva versión"}
        </button>
        {saveMutation.isError && (
          <span style={{ color: "var(--color-danger)", fontSize: "0.85rem" }}>
            {(saveMutation.error as Error).message}
          </span>
        )}
      </div>

      {savedJob && (
        <div style={{ marginTop: "1.5rem" }}>
          <JobProgress job={savedJob} />
          {savedJob.status === "done" && (
            <p style={{ marginTop: "0.8rem" }}>
              <Link to={`/projects/${projectId}`} style={{ color: "var(--color-asterion-gold-light)" }}>
                Ver el clip nuevo en el proyecto →
              </Link>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
