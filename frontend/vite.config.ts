import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // Built assets are served by FastAPI from src/lectura/api/static.
  build: { outDir: "../src/lectura/api/static", emptyOutDir: true },
  server: {
    proxy: { "/api": "http://localhost:8901" },
  },
});
