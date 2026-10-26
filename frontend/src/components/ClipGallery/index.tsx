import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Clip } from "../../api/client";
import { api } from "../../api/client";
import VideoPlayer from "../VideoPlayer";
import StarRating from "../StarRating";

export default function ClipGallery({ clips }: { clips: Clip[] }) {
  const qc = useQueryClient();
  const ratingMutation = useMutation({
    mutationFn: ({ clipId, rating }: { clipId: string; rating: number | null }) =>
      api.setRating(clipId, rating),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clips"] }),
  });

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
        gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
        gap: "1.5rem",
      }}
    >
      {clips.map((clip) => (
        <div key={clip.id} className="card">
          <VideoPlayer src={api.clipFileUrl(clip.id)} vertical={clip.layout === "vertical"} />
          <h4 style={{ margin: "0.75rem 0 0.25rem", fontSize: "0.95rem" }}>{clip.title}</h4>
          {clip.reason && (
            <p style={{ margin: 0, fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>{clip.reason}</p>
          )}
          <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.6rem", flexWrap: "wrap", alignItems: "center" }}>
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
            {clip.source_clip_id && (
              <span style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.4)" }}>editado</span>
            )}
          </div>
          <div style={{ marginTop: "0.5rem" }}>
            <StarRating
              value={clip.rating}
              onChange={(rating) => ratingMutation.mutate({ clipId: clip.id, rating })}
            />
          </div>
          <div style={{ display: "flex", gap: "1rem", marginTop: "0.6rem" }}>
            <a
              href={api.clipFileUrl(clip.id)}
              download
              style={{ fontSize: "0.85rem", color: "var(--color-asterion-gold-light)" }}
            >
              Descargar .mp4
            </a>
            <Link
              to={`/projects/${clip.project_id}/clips/${clip.id}/edit`}
              style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.7)" }}
            >
              Editar
            </Link>
          </div>
        </div>
      ))}
    </div>
  );
}
