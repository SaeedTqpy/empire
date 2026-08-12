import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/estedad/wght.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import './index.css'
import './terrain.css'
import './routes.css'
import './maplibre-terrain.css'
import './iranian-design.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
