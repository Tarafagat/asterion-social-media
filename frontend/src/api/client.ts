// base_path es /api/v1 (ver Contract.api(base_path="/api/v1") en
// app.asterion) — en dev, vite.config.ts proxea /api hacia la API real;
// en producción, FastAPI sirve este mismo build y sus propias rutas
// desde el mismo origen, así que una ruta relativa alcanza en los dos
// casos sin configurar nada aparte.
const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...init?.headers },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, detail.detail ?? res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface Project {
  id: string;
  name: string;
  source_filename: string | null;
  status: string;
  duration_s: number | null;
  width: number | null;
  height: number | null;
  has_audio: boolean | null;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: string;
  project_id: string;
  stage: string;
  status: string;
  progress_pct: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Clip {
  id: string;
  project_id: string;
  job_id: string;
  title: string;
  reason: string | null;
  layout: string;
  subtitle_style: string;
  needs_review: boolean;
  segments: { start_ms: number; end_ms: number }[];
  export_path: string | null;
  subtitle_path: string | null;
  created_at: string;
}

export interface SettingsField {
  key: string;
  label: string;
  value: string;
  is_secret: boolean;
  set_command: string;
}

export interface SettingsOut {
  provider: SettingsField[];
  content: SettingsField[];
  editing: SettingsField[];
  limits: SettingsField[];
}

export const api = {
  listProjects: () => request<Project[]>("/projects"),
  createProject: (name: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  uploadSource: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Project>(`/projects/${id}/source`, { method: "POST", body: form });
  },

  createJob: (projectId: string) => request<Job>(`/projects/${projectId}/jobs`, { method: "POST" }),
  getJob: (jobId: string) => request<Job>(`/jobs/${jobId}`),
  listJobs: (projectId: string) => request<Job[]>(`/projects/${projectId}/jobs`),

  listClips: (projectId: string) => request<Clip[]>(`/projects/${projectId}/clips`),
  clipFileUrl: (clipId: string) => `${BASE}/clips/${clipId}/file`,
  clipSubtitleUrl: (clipId: string) => `${BASE}/clips/${clipId}/subtitle`,

  getSettings: () => request<SettingsOut>("/settings"),
};
