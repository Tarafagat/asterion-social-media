import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

const STATUS_LABELS: Record<string, string> = {
  new: "Nuevo, sin video",
  ready: "Listo para procesar",
  processing: "Procesando",
  done: "Listo",
  failed: "Falló",
};

function fmtBytes(n: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let x = n;
  let i = 0;
  while (x >= 1024 && i < units.length - 1) {
    x /= 1024;
    i++;
  }
  return `${x.toFixed(x < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

export default function ProjectsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data: projects, isLoading } = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const { data: storage } = useQuery({ queryKey: ["storage"], queryFn: api.getStorage });

  const createMutation = useMutation({
    mutationFn: api.createProject,
    onSuccess: () => {
      setName("");
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => {
      setDeletingId(null);
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["storage"] });
    },
    onError: () => setDeletingId(null),
  });

  const usedPct = storage && storage.disk_total_bytes > 0 ? (storage.disk_used_bytes / storage.disk_total_bytes) * 100 : 0;

  return (
    <div>
      <h1 style={{ fontSize: "1.6rem", marginBottom: "1.5rem" }}>Proyectos</h1>

      {storage && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.6rem" }}>
            <strong style={{ fontSize: "0.9rem" }}>Disco</strong>
            <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.85rem" }}>
              {fmtBytes(storage.disk_free_bytes)} libres de {fmtBytes(storage.disk_total_bytes)}
            </span>
          </div>
          <div style={{ height: 8, borderRadius: 999, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${Math.min(100, usedPct).toFixed(1)}%`,
                background:
                  usedPct > 90
                    ? "var(--color-danger)"
                    : "linear-gradient(90deg, var(--color-asterion-gold-dark), var(--color-asterion-gold))",
                transition: "width 0.4s ease",
              }}
            />
          </div>
          <p style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.45)", margin: "0.6rem 0 0" }}>
            {storage.project_count} proyecto(s) ocupan <strong>{fmtBytes(storage.data_used_bytes)}</strong> · límite sugerido{" "}
            {storage.limit_max_storage_gb} GB
            {usedPct > 90 && <span style={{ color: "var(--color-danger)" }}> · ¡disco casi lleno!</span>}
          </p>
        </div>
      )}

      <form
        className="card"
        style={{ display: "flex", gap: "0.75rem", marginBottom: "2rem" }}
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) createMutation.mutate(name.trim());
        }}
      >
        <input
          className="input-field"
          placeholder="Nombre del proyecto (ej. Charla de FastAPI, episodio 12)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button type="submit" className="btn-gold" disabled={createMutation.isPending}>
          {createMutation.isPending ? "Creando…" : "Nuevo proyecto"}
        </button>
      </form>

      {isLoading && <p>Cargando…</p>}
      {projects && projects.length === 0 && (
        <p style={{ color: "rgba(255,255,255,0.5)" }}>
          Todavía no hay ningún proyecto — crea uno con el formulario de arriba.
        </p>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "1rem" }}>
        {projects?.map((p) => (
          <div key={p.id} className="card" style={{ height: "100%", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
            <Link to={`/projects/${p.id}`} style={{ textDecoration: "none", color: "inherit" }}>
              <h3 style={{ margin: "0 0 0.3rem", fontSize: "1.05rem" }}>{p.name}</h3>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "rgba(255,255,255,0.5)" }}>
                {STATUS_LABELS[p.status] ?? p.status}
                {p.duration_s ? ` · ${Math.round(p.duration_s)}s` : ""}
              </p>
            </Link>
            <div
              style={{
                marginTop: "auto",
                paddingTop: "0.6rem",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <Link to={`/projects/${p.id}`} style={{ fontSize: "0.82rem", color: "var(--color-asterion-gold-light)" }}>
                Abrir →
              </Link>
              <button
                className="btn-outline"
                style={{ padding: "0.3rem 0.8rem", fontSize: "0.8rem", color: "var(--color-danger)", borderColor: "rgba(229,72,77,0.4)" }}
                disabled={deletingId === p.id}
                onClick={() => {
                  if (
                    window.confirm(
                      `¿Borrar el proyecto "${p.name}"? Se eliminan del disco su video y todos sus clips. No se puede deshacer.`,
                    )
                  ) {
                    setDeletingId(p.id);
                    deleteMutation.mutate(p.id);
                  }
                }}
              >
                {deletingId === p.id ? "Borrando…" : "Borrar"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
