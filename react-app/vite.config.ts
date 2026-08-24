import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://py-app:5000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
