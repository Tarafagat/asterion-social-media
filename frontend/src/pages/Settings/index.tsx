import { useQuery } from "@tanstack/react-query";
import { api, type SettingsField } from "../../api/client";

function Section({ title, fields }: { title: string; fields: SettingsField[] }) {
  return (
    <div className="card" style={{ marginBottom: "1.25rem" }}>
      <h3 style={{ marginTop: 0, fontSize: "1rem", color: "var(--color-asterion-gold)" }}>{title}</h3>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
        <tbody>
          {fields.map((f) => (
            <tr key={f.key} style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
              <td style={{ padding: "0.5rem 0.5rem 0.5rem 0", color: "rgba(255,255,255,0.6)", whiteSpace: "nowrap" }}>
                {f.label}
              </td>
              <td style={{ padding: "0.5rem", fontFamily: "ui-monospace, monospace" }}>{f.value || "—"}</td>
              <td style={{ padding: "0.5rem 0 0.5rem 0.5rem", textAlign: "right" }}>
                <code className="mono" style={{ color: "rgba(255,255,255,0.4)" }}>
                  {f.set_command}
                </code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SettingsPage() {
  const { data } = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });

  return (
    <div>
      <h1 style={{ fontSize: "1.6rem" }}>Ajustes</h1>
      <p style={{ color: "rgba(255,255,255,0.5)", marginBottom: "1.5rem" }}>
        Solo lectura: Asterion inyecta esta configuración al arrancar el plugin, así que
        cambiarla se hace con el comando de la derecha (y después{" "}
        <code className="mono">asterion plugin restart social-clips</code>) — no hay un botón
        "Guardar" acá que pueda fingir un cambio en caliente que en realidad no aplica hasta
        reiniciar.
      </p>
      {data && (
        <>
          <Section title="Proveedor de IA" fields={data.provider} />
          <Section title="Contenido" fields={data.content} />
          <Section title="Edición" fields={data.editing} />
          <Section title="Límites" fields={data.limits} />
        </>
      )}
    </div>
  );
}
