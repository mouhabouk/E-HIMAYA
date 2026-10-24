import { configDefaults } from "vitest/config";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const CHUNKS: Record<string, string[]> = {
  maplibre: ["maplibre-gl"],
  react: ["react", "react-dom", "react-router", "scheduler"],
  vendor: ["@tanstack/react-query", "i18next", "react-i18next", "oidc-client-ts"],
  // Phase 8, loaded only by the memory and library screens (lazy routes).
  markdown: ["markdown-it", "dompurify"],
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
  server: { port: 5173, strictPort: true },
  preview: { port: 5173, strictPort: true },
  build: {
    target: "es2022",
    // Fonts stay separate files: the CSP allows `font-src 'self'` only, never `data:` (infra/web/csp.mjs).
    assetsInlineLimit: (file: string) => (/\.woff2?$/.test(file) ? false : undefined),
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
    // Browser tests (Playwright) run with `npm run test:e2e`.
    exclude: [...configDefaults.exclude, "e2e/**"],
    css: false,
    restoreMocks: true,
  },
});
