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

export default function ProjectsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");

  const { data: projects, isLoading } = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });

  const createMutation = useMutation({
    mutationFn: api.createProject,
    onSuccess: () => {
      setName("");
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  return (
    <div>
      <h1 style={{ fontSize: "1.6rem", marginBottom: "1.5rem" }}>Proyectos</h1>

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
          Todavía no creaste ningún proyecto — empezá con uno de arriba.
        </p>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "1rem" }}>
        {projects?.map((p) => (
          <Link key={p.id} to={`/projects/${p.id}`} style={{ textDecoration: "none", color: "inherit" }}>
            <div className="card" style={{ height: "100%" }}>
              <h3 style={{ margin: "0 0 0.4rem", fontSize: "1.05rem" }}>{p.name}</h3>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "rgba(255,255,255,0.5)" }}>
                {STATUS_LABELS[p.status] ?? p.status}
                {p.duration_s ? ` · ${Math.round(p.duration_s)}s` : ""}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
