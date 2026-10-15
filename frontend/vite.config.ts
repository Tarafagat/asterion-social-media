import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, pnpm dev corre en su propio puerto y proxea /api hacia
// la API de FastAPI (que Asterion ya tiene corriendo en su propio puerto
// efímero) — en producción, 'plugin build' deja todo compilado en
// frontend/dist y es FastAPI quien lo sirve directo (ver apps/api/app/
// main.py), sin este proxy de por medio.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8899",
    },
  },
});
