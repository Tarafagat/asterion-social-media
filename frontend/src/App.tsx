import { Link, Route, Routes, useLocation } from "react-router-dom";
import ProjectsPage from "./pages/Projects";
import ProjectPage from "./pages/Project";
import ClipEditorPage from "./pages/ClipEditor";
import SettingsPage from "./pages/Settings";

function Nav() {
  const loc = useLocation();
  const isActive = (p: string) => loc.pathname === p || (p !== "/" && loc.pathname.startsWith(p));
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
      <nav style={{ display: "flex", gap: "1.5rem", fontSize: "0.9rem" }}>
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
      </nav>
    </header>
  );
}

export default function App() {
  return (
    <div style={{ minHeight: "100vh" }}>
      <Nav />
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "2rem 1.5rem" }}>
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:id" element={<ProjectPage />} />
          <Route path="/projects/:id/clips/:clipId/edit" element={<ClipEditorPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
