/// <reference types="vitest/config" />
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// In development the Vite server proxies /api to the backend (`quarry serve` on port 8000). Start the backend with
// QUARRY_BASE_URL=http://localhost:5173 so passkeys are bound to the address the browser actually shows.
export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "script",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "Quarry",
        short_name: "Quarry",
        description: "Capture sparks, keep the bible, write the book.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#121418",
        theme_color: "#1d2128",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/healthz/],
        globPatterns: ["**/*.{js,css,html,svg,png,webmanifest}"],
      },
    }),
  ],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
  },
});
