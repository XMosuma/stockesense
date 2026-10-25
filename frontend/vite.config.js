import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In Docker the API is at http://api:8000; locally it is http://localhost:8000.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: { "/api": process.env.API_URL || "http://localhost:8000" },
  },
});
