import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { setWorkerUrl } from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import '@fontsource-variable/estedad/wght.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import './index.css'
import './terrain.css'
import './routes.css'
import './maplibre-terrain.css'
import './iranian-design.css'
import App from './App.tsx'

// MapLibre GL JS v6 is ESM-only. With Vite, pass the worker through Vite's
// worker pipeline and register the emitted URL explicitly. This avoids dev
// failures where .vite/deps points at a worker sibling that was never emitted.
setWorkerUrl(maplibreWorkerUrl)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
