import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import JobProgress from "../../components/JobProgress";
import ClipGallery from "../../components/ClipGallery";

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = id!;
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
  });

  const { data: jobs } = useQuery({
    queryKey: ["jobs", projectId],
    queryFn: () => api.listJobs(projectId),
    refetchInterval: (query) => {
      const latest = query.state.data?.[0];
      return latest && latest.status === "running" ? 1500 : false;
    },
  });
  const latestJob = jobs?.[0];

  const { data: clips } = useQuery({
    queryKey: ["clips", projectId, latestJob?.status],
    queryFn: () => api.listClips(projectId),
  });

  const uploadMutation = useMutation({
    mutationFn: (f: File) => api.uploadSource(projectId, f),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project", projectId] }),
  });

  const createJobMutation = useMutation({
    mutationFn: () => api.createJob(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs", projectId] }),
  });

  if (!project) return <p>Cargando…</p>;

  const jobRunning = latestJob?.status === "running" || latestJob?.status === "queued";

  return (
    <div>
      <h1 style={{ fontSize: "1.6rem", marginBottom: "0.3rem" }}>{project.name}</h1>
      <p style={{ color: "rgba(255,255,255,0.5)", marginTop: 0, marginBottom: "1.5rem" }}>
        {project.source_filename ?? "Sin video subido todavía"}
        {project.duration_s ? ` · ${Math.round(project.duration_s)}s · ${project.width}×${project.height}` : ""}
      </p>

      {!project.source_filename && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <p style={{ marginTop: 0 }}>Subí el video fuente para empezar.</p>
          <input type="file" accept="video/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <div style={{ marginTop: "0.8rem" }}>
            <button
              className="btn-gold"
              disabled={!file || uploadMutation.isPending}
              onClick={() => file && uploadMutation.mutate(file)}
            >
              {uploadMutation.isPending ? "Subiendo…" : "Subir video"}
            </button>
          </div>
        </div>
      )}

      {project.source_filename && (
        <div className="card" style={{ marginBottom: "1.5rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ color: "rgba(255,255,255,0.7)" }}>
            {clips && clips.length > 0 ? `${clips.length} clip(s) generado(s)` : "Listo para procesar"}
          </span>
          <button className="btn-gold" disabled={jobRunning} onClick={() => createJobMutation.mutate()}>
            {jobRunning ? "Procesando…" : "Crear clips"}
          </button>
        </div>
      )}

      {latestJob && (latestJob.status === "running" || latestJob.status === "queued" || latestJob.status === "failed") && (
        <div style={{ marginBottom: "1.5rem" }}>
          <JobProgress job={latestJob} />
        </div>
      )}

      {clips && (
        <>
          <h2 style={{ fontSize: "1.1rem" }}>Clips</h2>
          <ClipGallery clips={clips} />
        </>
      )}
    </div>
  );
}
