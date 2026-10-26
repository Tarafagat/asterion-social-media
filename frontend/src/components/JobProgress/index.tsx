import type { Job } from "../../api/client";

const STAGE_LABELS: Record<string, string> = {
  queued: "En cola",
  inspect: "Inspeccionando",
  extract_audio: "Extrayendo audio",
  transcribe: "Transcribiendo",
  analyze: "Analizando",
  select_clips: "Seleccionando",
  plan_edits: "Planificando",
  render: "Renderizando",
  validate: "Validando",
  tts: "Generando voz",
  sadtalker: "Animando el avatar",
  mux: "Reemplazando el audio",
};

export default function JobProgress({ job }: { job: Job }) {
  const failed = job.status === "failed";
  const done = job.status === "done";
  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.6rem" }}>
        <strong>{failed ? "Falló" : done ? "Listo" : STAGE_LABELS[job.stage] ?? job.stage}</strong>
        <span style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.85rem" }}>{job.progress_pct}%</span>
      </div>
      <div
        style={{
          height: 8,
          borderRadius: 999,
          background: "rgba(255,255,255,0.08)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${job.progress_pct}%`,
            background: failed
              ? "var(--color-danger)"
              : "linear-gradient(90deg, var(--color-asterion-gold-dark), var(--color-asterion-gold))",
            transition: "width 0.4s ease",
          }}
        />
      </div>
      {failed && job.error && (
        <p style={{ color: "var(--color-danger)", fontSize: "0.85rem", marginTop: "0.6rem" }}>{job.error}</p>
      )}
    </div>
  );
}
