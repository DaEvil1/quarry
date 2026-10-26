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
      // a new version waits until the person chooses to reload (UpdateBar), so it never interrupts writing
      registerType: "prompt",
      injectRegister: false,
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "Quarry",
        short_name: "Quarry",
        description: "Capture sparks, keep the bible, write the book.",
        // the installed app opens on Capture; sharing from another app lands there too
        start_url: "/capture",
        scope: "/",
        display: "standalone",
        background_color: "#121418",
        theme_color: "#1d2128",
        share_target: {
          action: "/share",
          method: "GET",
          params: { title: "title", text: "text", url: "url" },
        },
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
        // pictures (docs/SPEC.md §17.5): a view copy or thumb is answered from any cache that has it (the offline
        // copy's, kept by the sync, or the pictures seen lately); else from the network, and kept among the 300 seen
        // most lately. A picture's files never change, so a kept one is never stale.
        runtimeCaching: [
          {
            urlPattern: ({ url }) => /^\/api\/pictures\/[0-9a-f-]{36}\/(view|thumb)$/.test(url.pathname),
            handler: async ({ request }) => {
              const kept = await caches.match(request);
              if (kept) return kept;
              const res = await fetch(request);
              if (res.ok) {
                const seen = await caches.open("quarry-pictures-seen");
                await seen.put(request, res.clone());
                const keys = await seen.keys();
                for (const old of keys.slice(0, Math.max(0, keys.length - 300))) await seen.delete(old);
              }
              return res;
            },
          },
        ],
      },
    }),
  ],
  build: {
    // the chapter page carries the editor (CodeMirror and the Markdown parser, ~560 kB): loaded only when a chapter
    // opens, and cached by the service worker for offline use
    chunkSizeWarningLimit: 700,
  },
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
