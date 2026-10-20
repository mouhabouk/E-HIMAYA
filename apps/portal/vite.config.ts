/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const CHUNKS: Record<string, string[]> = {
  maplibre: ["maplibre-gl"],
  react: ["react", "react-dom", "react-router", "scheduler"],
  vendor: ["@tanstack/react-query", "i18next", "react-i18next", "oidc-client-ts"],
};

// Vite 8 (Rolldown) only takes the function form of manualChunks.
function manualChunks(id: string): string | undefined {
  for (const [chunk, packages] of Object.entries(CHUNKS)) {
    if (packages.some((name) => id.includes(`/node_modules/${name}/`))) return chunk;
  }
  return undefined;
}

export default defineConfig({
  plugins: [react()],
  server: { port: 5174, strictPort: true },
  preview: { port: 5174, strictPort: true },
  build: {
    target: "es2022",
    sourcemap: true,
    // maplibre-gl is ~1 MB minified; it is split out and only loaded by map screens.
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: { manualChunks },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
