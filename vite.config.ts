import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { inspectAttr } from 'kimi-plugin-inspect-react'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [inspectAttr(), react()],
  server: {
    port: 3000,
    host: true,
  },
  optimizeDeps: {
    // MapLibre GL JS v6 ships an ESM worker as a sibling module. Let Vite's
    // worker pipeline handle it explicitly instead of pre-bundling the
    // package into .vite/deps, where the worker sibling can go missing.
    exclude: ["maplibre-gl"],
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ["three", "three/webgpu", "three/tsl", "three-mesh-bvh"],
          gsap: ["gsap"],
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
