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
  has_avatar: boolean;
  avatar_mode: "pip" | "background";
  has_dubbed_video: boolean;
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

export interface ClipSegment {
  start_ms: number;
  end_ms: number;
}

export interface Voice {
  id: string;
  label: string;
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
  segments: ClipSegment[];
  export_path: string | null;
  subtitle_path: string | null;
  rating: number | null;
  source_clip_id: string | null;
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
  getClip: (clipId: string) => request<Clip>(`/clips/${clipId}`),
  clipFileUrl: (clipId: string) => `${BASE}/clips/${clipId}/file`,
  clipSubtitleUrl: (clipId: string) => `${BASE}/clips/${clipId}/subtitle`,
  setRating: (clipId: string, rating: number | null) =>
    request<Clip>(`/clips/${clipId}/rating`, { method: "PATCH", body: JSON.stringify({ rating }) }),
  editClip: (clipId: string, segments: ClipSegment[], avatarEnabled: boolean) =>
    request<Job>(`/clips/${clipId}/edit`, {
      method: "POST",
      body: JSON.stringify({ segments, avatar_enabled: avatarEnabled }),
    }),

  waveformUrl: (projectId: string) => `${BASE}/projects/${projectId}/waveform.png`,
  uploadAvatar: (projectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Project>(`/projects/${projectId}/avatar`, { method: "POST", body: form });
  },
  deleteAvatar: (projectId: string) =>
    request<Project>(`/projects/${projectId}/avatar`, { method: "DELETE" }),
  setAvatarMode: (projectId: string, mode: "pip" | "background") =>
    request<Project>(`/projects/${projectId}/avatar-mode`, {
      method: "PUT",
      body: JSON.stringify({ avatar_mode: mode }),
    }),
  generateAvatar: (projectId: string, image: File, script: string, voiceId: string, audio?: File) => {
    const form = new FormData();
    form.append("image", image);
    form.append("script", script);
    form.append("voice_id", voiceId);
    if (audio) form.append("audio", audio);
    return request<Job>(`/projects/${projectId}/avatar/generate`, { method: "POST", body: form });
  },
  listVoices: () => request<{ voices: Voice[] }>("/projects/avatar/voices"),
  dubVideo: (
    projectId: string,
    script: string,
    voiceId: string,
    avatarImage?: File,
    avatarMode?: "pip" | "background",
  ) => {
    const form = new FormData();
    form.append("script", script);
    form.append("voice_id", voiceId);
    if (avatarImage) form.append("avatar_image", avatarImage);
    if (avatarMode) form.append("avatar_mode", avatarMode);
    return request<Job>(`/projects/${projectId}/dub`, { method: "POST", body: form });
  },
  dubbedVideoUrl: (projectId: string) => `${BASE}/projects/${projectId}/dub/file`,
  extractTranscript: (projectId: string) => request<Job>(`/projects/${projectId}/transcript`, { method: "POST" }),
  getTranscript: async (projectId: string): Promise<{ text: string; language: string } | null> => {
    try {
      return await request(`/projects/${projectId}/transcript`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }
  },

  getSettings: () => request<SettingsOut>("/settings"),
};
