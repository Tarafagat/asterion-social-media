import { useState } from "react";
import { api } from "../../api/client";

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      await api.auth.login(username, password);
      onSuccess();
    } catch (err) {
      setError((err as Error).message || "No se pudo iniciar sesión.");
      setPending(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "1.5rem" }}>
      <form className="card" onSubmit={submit} style={{ width: "100%", maxWidth: 360 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.3rem" }}>
          <span style={{ fontSize: "1.3rem" }}>🎬</span>
          <strong style={{ letterSpacing: "0.02em" }}>Asterion Social Clips</strong>
        </div>
        <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.85rem", marginTop: 0, marginBottom: "1.2rem" }}>
          Inicia sesión para entrar al editor.
        </p>

        <label style={{ display: "block", fontSize: "0.8rem", color: "rgba(255,255,255,0.5)", marginBottom: "0.8rem" }}>
          Usuario
          <input
            className="input-field"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
            style={{ display: "block", marginTop: "0.3rem" }}
          />
        </label>
        <label style={{ display: "block", fontSize: "0.8rem", color: "rgba(255,255,255,0.5)", marginBottom: "1rem" }}>
          Clave
          <input
            className="input-field"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            style={{ display: "block", marginTop: "0.3rem" }}
          />
        </label>

        {error && (
          <p style={{ color: "var(--color-danger)", fontSize: "0.85rem", marginTop: 0, marginBottom: "0.8rem" }}>{error}</p>
        )}

        <button type="submit" className="btn-gold" disabled={pending || !username || !password} style={{ width: "100%" }}>
          {pending ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
