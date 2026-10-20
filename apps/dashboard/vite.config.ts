import { configDefaults } from "vitest/config";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  preview: { port: 5173, strictPort: true },
  build: {
    target: "es2022",
    sourcemap: true,
    // maplibre-gl is ~1 MB minified; it is split out and only loaded by map screens.
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        manualChunks: {
          maplibre: ["maplibre-gl"],
          react: ["react", "react-dom", "react-dom/client", "react-router"],
          vendor: ["@tanstack/react-query", "i18next", "react-i18next", "oidc-client-ts"],
          // Phase 8, loaded only by the memory and library screens (lazy routes).
          markdown: ["markdown-it", "dompurify"],
        },
      },
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
