import { useEffect } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type AuthState } from "./api/client";
import ProjectsPage from "./pages/Projects";
import ProjectPage from "./pages/Project";
import ClipEditorPage from "./pages/ClipEditor";
import SettingsPage from "./pages/Settings";
import Login from "./pages/Login";

function Nav({ auth }: { auth?: AuthState }) {
  const loc = useLocation();
  const qc = useQueryClient();
  const isActive = (p: string) => loc.pathname === p || (p !== "/" && loc.pathname.startsWith(p));

  async function logout() {
    await api.auth.logout().catch(() => {});
    // Quita los datos cacheados del usuario (proyectos, etc.) y re-chequea
    // la sesión — el refetch de "auth-me" devolverá authenticated:false y
    // la app mostrará el login de nuevo, sin recargar la página.
    qc.removeQueries({ queryKey: ["projects"] });
    qc.removeQueries({ queryKey: ["storage"] });
    await qc.invalidateQueries({ queryKey: ["auth-me"] });
  }

  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "1rem 1.5rem",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      <Link to="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "0.6rem" }}>
        <span style={{ fontSize: "1.3rem" }}>🎬</span>
        <strong style={{ letterSpacing: "0.02em" }}>Asterion Social Clips</strong>
      </Link>
      <nav style={{ display: "flex", gap: "1.5rem", fontSize: "0.9rem", alignItems: "center" }}>
        <Link
          to="/"
          style={{ color: isActive("/") && loc.pathname === "/" ? "var(--color-asterion-gold)" : "rgba(255,255,255,0.7)" }}
        >
          Proyectos
        </Link>
        <Link
          to="/settings"
          style={{ color: isActive("/settings") ? "var(--color-asterion-gold)" : "rgba(255,255,255,0.7)" }}
        >
          Ajustes
        </Link>
        {auth?.enabled && auth.authenticated && (
          <button
            onClick={logout}
            className="btn-outline"
            style={{ padding: "0.35rem 0.9rem", fontSize: "0.82rem" }}
            title={auth.username ? `Sesión: ${auth.username}` : undefined}
          >
            Salir
          </button>
        )}
      </nav>
    </header>
  );
}

export default function App() {
  const qc = useQueryClient();
  const { data: auth, isLoading } = useQuery({ queryKey: ["auth-me"], queryFn: () => api.auth.me() });

  // Si una llamada protegida devuelve 401 (sesión vencida), el cliente API
  // dispara "sc-unauthorized" — acá se re-chequea el estado de login, lo
  // que lleva de vuelta a la pantalla de login sin recargar la página.
  useEffect(() => {
    const onUnauthorized = () => qc.invalidateQueries({ queryKey: ["auth-me"] });
    window.addEventListener("sc-unauthorized", onUnauthorized);
    return () => window.removeEventListener("sc-unauthorized", onUnauthorized);
  }, [qc]);

  if (isLoading) {
    return <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", color: "rgba(255,255,255,0.5)" }}>Cargando…</div>;
  }

  if (auth && auth.enabled && !auth.authenticated) {
    return <Login onSuccess={() => qc.invalidateQueries({ queryKey: ["auth-me"] })} />;
  }

  return (
    <div style={{ minHeight: "100vh" }}>
      <Nav auth={auth} />
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "2rem 1.5rem" }}>
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:id" element={<ProjectPage />} />
          <Route path="/projects/:id/editor" element={<ClipEditorPage />} />
          <Route path="/projects/:id/clips/:clipId/edit" element={<ClipEditorPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
