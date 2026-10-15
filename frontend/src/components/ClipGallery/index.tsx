import type { Clip } from "../../api/client";
import { api } from "../../api/client";
import VideoPlayer from "../VideoPlayer";

export default function ClipGallery({ clips }: { clips: Clip[] }) {
  if (clips.length === 0) {
    return (
      <p style={{ color: "rgba(255,255,255,0.5)" }}>
        Todavía no hay ningún clip — ninguno de los momentos detectados llegó a la duración
        mínima, o el job no terminó todavía.
      </p>
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
        gap: "1.25rem",
      }}
    >
      {clips.map((clip) => (
        <div key={clip.id} className="card">
          <VideoPlayer src={api.clipFileUrl(clip.id)} vertical={clip.layout === "vertical"} />
          <h4 style={{ margin: "0.75rem 0 0.25rem", fontSize: "0.95rem" }}>{clip.title}</h4>
          {clip.reason && (
            <p style={{ margin: 0, fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>{clip.reason}</p>
          )}
          <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.6rem", flexWrap: "wrap" }}>
            <code className="mono">{clip.layout}</code>
            {clip.needs_review && (
              <span
                style={{
                  fontSize: "0.75rem",
                  color: "var(--color-asterion-gold)",
                  border: "1px solid rgba(240,192,74,0.4)",
                  borderRadius: 999,
                  padding: "0.1rem 0.5rem",
                }}
              >
                revisar
              </span>
            )}
          </div>
          <a
            href={api.clipFileUrl(clip.id)}
            download
            style={{ display: "inline-block", marginTop: "0.6rem", fontSize: "0.85rem", color: "var(--color-asterion-gold-light)" }}
          >
            Descargar .mp4
          </a>
        </div>
      ))}
    </div>
  );
}
