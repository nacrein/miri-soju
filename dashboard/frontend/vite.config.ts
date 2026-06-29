import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev the app runs on :5173 and proxies /api to the FastAPI backend on :8000,
// so the browser only ever sees one origin (cookies + OAuth redirect "just work").
// In prod the backend serves the built dist/ itself, so no proxy is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: true },
});
