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
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [showAvatarIA, setShowAvatarIA] = useState(false);
  const [avatarImage, setAvatarImage] = useState<File | null>(null);
  const [avatarScript, setAvatarScript] = useState("");
  const [avatarAudio, setAvatarAudio] = useState<File | null>(null);
  const [avatarVoiceId, setAvatarVoiceId] = useState("es-femenina");
  const [showDub, setShowDub] = useState(false);
  const [dubScript, setDubScript] = useState("");
  const [dubVoiceId, setDubVoiceId] = useState("es-femenina");
  const [dubUseAvatar, setDubUseAvatar] = useState(false);
  const [dubAvatarImage, setDubAvatarImage] = useState<File | null>(null);
  const [dubAvatarMode, setDubAvatarMode] = useState<"pip" | "background">("pip");

  const { data: voicesData } = useQuery({ queryKey: ["voices"], queryFn: () => api.listVoices() });
  const voices = voicesData?.voices ?? [];

  const { data: jobs } = useQuery({
    queryKey: ["jobs", projectId],
    queryFn: () => api.listJobs(projectId),
    refetchInterval: (query) => {
      const latest = query.state.data?.[0];
      // Sigue sondeando mientras NO esté en un estado final — "queued"
      // cuenta: un job puede quedarse ahí un buen rato si el worker (uno
      // solo, procesa de a uno) todavía está ocupado con otro proyecto.
      // Antes solo sondeaba en "running", así que un job en cola se veía
      // "trabado" sin nunca refrescarse solo.
      const isFinal = latest?.status === "done" || latest?.status === "failed";
      return latest && !isFinal ? 1500 : false;
    },
  });
  const latestJob = jobs?.[0];

  const { data: project } = useQuery({
    // Incluye latestJob?.status para que termine refrescando el proyecto
    // cuando un job de avatar_generate pasa a "done" — ahí es cuando
    // project.avatar_path/has_avatar cambia del lado del servidor.
    queryKey: ["project", projectId, latestJob?.status],
    queryFn: () => api.getProject(projectId),
  });

  const { data: clips } = useQuery({
    queryKey: ["clips", projectId, latestJob?.status],
    queryFn: () => api.listClips(projectId),
  });

  const { data: transcript } = useQuery({
    // Igual truco que "project": reacciona cuando un job 'transcribe_only'
    // (o 'Crear clips', que también transcribe) pasa a "done".
    queryKey: ["transcript", projectId, latestJob?.status],
    queryFn: () => api.getTranscript(projectId),
  });
  const [copiedTranscript, setCopiedTranscript] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: (f: File) => api.uploadSource(projectId, f),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project", projectId] }),
  });

  const extractTranscriptMutation = useMutation({
    mutationFn: () => api.extractTranscript(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs", projectId] }),
  });

  const createJobMutation = useMutation({
    mutationFn: () => api.createJob(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs", projectId] }),
  });

  const uploadAvatarMutation = useMutation({
    mutationFn: (f: File) => api.uploadAvatar(projectId, f),
    onSuccess: () => {
      setAvatarFile(null);
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
  const deleteAvatarMutation = useMutation({
    mutationFn: () => api.deleteAvatar(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project", projectId] }),
  });
  const avatarModeMutation = useMutation({
    mutationFn: (mode: "pip" | "background") => api.setAvatarMode(projectId, mode),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project", projectId] }),
  });

  const generateAvatarMutation = useMutation({
    mutationFn: () =>
      api.generateAvatar(projectId, avatarImage!, avatarScript, avatarVoiceId, avatarAudio ?? undefined),
    onSuccess: () => {
      setShowAvatarIA(false);
      setAvatarImage(null);
      setAvatarScript("");
      setAvatarAudio(null);
      qc.invalidateQueries({ queryKey: ["jobs", projectId] });
    },
  });

  const cancelJobMutation = useMutation({
    mutationFn: (jobId: string) => api.cancelJob(jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs", projectId] }),
  });

  const dubVideoMutation = useMutation({
    mutationFn: () =>
      api.dubVideo(
        projectId, dubScript, dubVoiceId,
        dubUseAvatar ? dubAvatarImage ?? undefined : undefined,
        dubUseAvatar ? dubAvatarMode : undefined,
      ),
    onSuccess: () => {
      setShowDub(false);
      setDubScript("");
      setDubUseAvatar(false);
      setDubAvatarImage(null);
      qc.invalidateQueries({ queryKey: ["jobs", projectId] });
    },
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

      {project.source_filename && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
            <span style={{ color: "rgba(255,255,255,0.7)" }}>
              {transcript ? "Texto extraído del video" : "Extraé el texto hablado del video para copiarlo y armar un guion"}
            </span>
            <button
              className="btn-outline"
              disabled={jobRunning || extractTranscriptMutation.isPending}
              onClick={() => extractTranscriptMutation.mutate()}
            >
              {extractTranscriptMutation.isPending || jobRunning
                ? "Procesando…"
                : transcript
                ? "Extraer de nuevo"
                : "Extraer texto del video"}
            </button>
          </div>
          {transcript && (
            <div style={{ marginTop: "0.8rem" }}>
              <textarea
                className="input-field"
                value={transcript.text}
                readOnly
                rows={5}
                style={{ width: "100%", resize: "vertical" }}
              />
              <div style={{ display: "flex", gap: "0.6rem", marginTop: "0.6rem", flexWrap: "wrap" }}>
                <button
                  className="btn-outline"
                  onClick={() => {
                    navigator.clipboard.writeText(transcript.text).then(() => {
                      setCopiedTranscript(true);
                      setTimeout(() => setCopiedTranscript(false), 2000);
                    });
                  }}
                >
                  {copiedTranscript ? "Copiado ✓" : "Copiar texto"}
                </button>
                <button
                  className="btn-outline"
                  onClick={() => {
                    setDubScript(transcript.text);
                    setShowDub(true);
                  }}
                >
                  Usar en "Procesar video completo"
                </button>
                <button
                  className="btn-outline"
                  onClick={() => {
                    setAvatarScript(transcript.text);
                    setShowAvatarIA(true);
                  }}
                >
                  Usar en "Avatar IA"
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {project.source_filename && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
            <span style={{ color: "rgba(255,255,255,0.7)" }}>
              {project.has_dubbed_video
                ? "Video completo con audio reemplazado, listo"
                : "Video completo (sin recortar) con el audio original reemplazado por una narración nueva"}
            </span>
            <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
              {project.has_dubbed_video && (
                <a
                  href={api.dubbedVideoUrl(projectId)}
                  download
                  style={{ fontSize: "0.85rem", color: "var(--color-asterion-gold-light)" }}
                >
                  Descargar video doblado
                </a>
              )}
              <button className="btn-outline" onClick={() => setShowDub((v) => !v)}>
                {showDub ? "Cancelar" : project.has_dubbed_video ? "Generar de nuevo" : "Procesar video completo"}
              </button>
            </div>
          </div>

          {showDub && (
            <div style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
              <p style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.6)", marginTop: 0 }}>
                Se lee este guion con voz en español (Piper TTS) y reemplaza el audio del video completo. Si el
                guion dura menos que el video, el video se recorta a esa duración; si dura más, el video se repite
                en loop hasta cubrirlo.
              </p>
              <textarea
                className="input-field"
                value={dubScript}
                onChange={(e) => setDubScript(e.target.value)}
                rows={4}
                style={{ width: "100%", resize: "vertical" }}
                placeholder="Hola, bienvenidos a este video..."
              />
              <label style={{ display: "block", fontSize: "0.8rem", color: "rgba(255,255,255,0.5)", marginTop: "0.6rem" }}>
                Voz
                <select
                  className="input-field"
                  value={dubVoiceId}
                  onChange={(e) => setDubVoiceId(e.target.value)}
                  style={{ display: "block", marginTop: "0.3rem", width: "auto" }}
                >
                  {voices.map((v) => (
                    <option key={v.id} value={v.id}>{v.label}</option>
                  ))}
                </select>
              </label>

              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.85rem", marginTop: "0.8rem" }}>
                <input type="checkbox" checked={dubUseAvatar} onChange={(e) => setDubUseAvatar(e.target.checked)} />
                Montar un avatar hablando encima (con este mismo guion)
              </label>
              {dubUseAvatar && (
                <div style={{ marginTop: "0.6rem", display: "flex", gap: "0.6rem", alignItems: "center", flexWrap: "wrap" }}>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setDubAvatarImage(e.target.files?.[0] ?? null)}
                  />
                  <select
                    className="input-field"
                    value={dubAvatarMode}
                    onChange={(e) => setDubAvatarMode(e.target.value as "pip" | "background")}
                    style={{ width: "auto" }}
                  >
                    <option value="pip">Burbuja (esquina)</option>
                    <option value="background">De fondo</option>
                  </select>
                </div>
              )}

              <div style={{ marginTop: "0.8rem" }}>
                <button
                  className="btn-gold"
                  disabled={
                    !dubScript.trim() ||
                    (dubUseAvatar && !dubAvatarImage) ||
                    dubVideoMutation.isPending
                  }
                  onClick={() => dubVideoMutation.mutate()}
                >
                  {dubVideoMutation.isPending ? "Enviando…" : "Reemplazar audio"}
                </button>
              </div>
              {dubVideoMutation.isError && (
                <p style={{ color: "var(--color-danger)", fontSize: "0.85rem", marginTop: "0.5rem" }}>
                  {(dubVideoMutation.error as Error).message}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {project.source_filename && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
            <span style={{ color: "rgba(255,255,255,0.7)" }}>
              {project.has_avatar
                ? `Avatar configurado (modo: ${project.avatar_mode === "background" ? "de fondo" : "burbuja"})`
                : "Sin avatar — opcional, un video grabado (sin IA) que se monta sobre los clips"}
            </span>
            {project.has_avatar ? (
              <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
                <select
                  className="input-field"
                  value={project.avatar_mode}
                  onChange={(e) => avatarModeMutation.mutate(e.target.value as "pip" | "background")}
                  style={{ width: "auto" }}
                >
                  <option value="pip">Burbuja (esquina)</option>
                  <option value="background">De fondo</option>
                </select>
                <button className="btn-outline" onClick={() => deleteAvatarMutation.mutate()}>
                  Quitar avatar
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", gap: "0.6rem", alignItems: "center", flexWrap: "wrap" }}>
                <button className="btn-gold" onClick={() => setShowAvatarIA((v) => !v)}>
                  {showAvatarIA ? "Cancelar" : "Generar desde una foto (IA)"}
                </button>
                <span style={{ color: "rgba(255,255,255,0.3)", fontSize: "0.8rem" }}>o</span>
                <input type="file" accept="video/*" onChange={(e) => setAvatarFile(e.target.files?.[0] ?? null)} />
                <button
                  className="btn-outline"
                  disabled={!avatarFile || uploadAvatarMutation.isPending}
                  onClick={() => avatarFile && uploadAvatarMutation.mutate(avatarFile)}
                >
                  {uploadAvatarMutation.isPending ? "Subiendo…" : "Subir video ya grabado"}
                </button>
              </div>
            )}
          </div>
          <p style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.4)", marginTop: "0.6rem", marginBottom: 0 }}>
            "Subir video ya grabado" es un video tal cual, sin animar (se activa por clip desde "Editar"). "Generar
            desde una foto" pide una imagen y la anima con IA (abajo).
          </p>

          {showAvatarIA && !project.has_avatar && (
            <div style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
              <p style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.6)", marginTop: 0 }}>
                Una foto del presentador + un guion (se convierte a voz en español automáticamente) o un audio
                propio — SadTalker anima la foto con ese audio. Tarda bastante (varios minutos por CPU).
              </p>
              <label style={{ display: "block", fontSize: "0.8rem", color: "rgba(255,255,255,0.5)", marginBottom: "0.8rem" }}>
                Foto del presentador (imagen, no video)
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setAvatarImage(e.target.files?.[0] ?? null)}
                  style={{ display: "block", marginTop: "0.3rem" }}
                />
              </label>
              <label style={{ display: "block", fontSize: "0.8rem", color: "rgba(255,255,255,0.5)", marginBottom: "0.8rem" }}>
                Guion (se lee con voz en español) — opcional si subís un audio propio
                <textarea
                  className="input-field"
                  value={avatarScript}
                  onChange={(e) => setAvatarScript(e.target.value)}
                  rows={3}
                  style={{ width: "100%", marginTop: "0.3rem", resize: "vertical" }}
                  placeholder="Hola, bienvenidos a este video..."
                />
              </label>
              <label style={{ display: "block", fontSize: "0.8rem", color: "rgba(255,255,255,0.5)", marginBottom: "0.8rem" }}>
                Voz
                <select
                  className="input-field"
                  value={avatarVoiceId}
                  onChange={(e) => setAvatarVoiceId(e.target.value)}
                  style={{ display: "block", marginTop: "0.3rem", width: "auto" }}
                >
                  {voices.map((v) => (
                    <option key={v.id} value={v.id}>{v.label}</option>
                  ))}
                </select>
              </label>
              <label style={{ display: "block", fontSize: "0.8rem", color: "rgba(255,255,255,0.5)", marginBottom: "0.8rem" }}>
                O un audio propio (en vez del guion)
                <input
                  type="file"
                  accept="audio/*"
                  onChange={(e) => setAvatarAudio(e.target.files?.[0] ?? null)}
                  style={{ display: "block", marginTop: "0.3rem" }}
                />
              </label>
              <button
                className="btn-gold"
                disabled={!avatarImage || (!avatarScript.trim() && !avatarAudio) || generateAvatarMutation.isPending}
                onClick={() => generateAvatarMutation.mutate()}
              >
                {generateAvatarMutation.isPending ? "Enviando…" : "Generar avatar"}
              </button>
              {generateAvatarMutation.isError && (
                <p style={{ color: "var(--color-danger)", fontSize: "0.85rem", marginTop: "0.5rem" }}>
                  {(generateAvatarMutation.error as Error).message}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {latestJob && (latestJob.status === "running" || latestJob.status === "queued" || latestJob.status === "failed") && (
        <div style={{ marginBottom: "1.5rem" }}>
          <JobProgress
            job={latestJob}
            onCancel={
              latestJob.status === "running" || latestJob.status === "queued"
                ? () => cancelJobMutation.mutate(latestJob.id)
                : undefined
            }
            cancelling={cancelJobMutation.isPending}
          />
          {cancelJobMutation.isError && (
            <p style={{ color: "var(--color-danger)", fontSize: "0.85rem", marginTop: "0.5rem" }}>
              {(cancelJobMutation.error as Error).message}
            </p>
          )}
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
