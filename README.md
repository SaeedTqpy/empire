# Iran 3D Peaks

Interactive 3D mountain atlas for Iran, starting with **Mount Damavand**.

The product direction is a real-terrain experience: DEM-derived mountain geometry, satellite imagery, cinematic camera movement, climbing routes, shelters and mountain landmarks.

## Current status — Phase 5 complete

Damavand now combines real terrain, georeferenced satellite imagery, an interruptible cinematic camera, and terrain-aware 3D climbing routes.

### Real terrain

- `Peak` is the product domain model under `src/types/peak.ts`
- Damavand is the only product dataset rendered at runtime
- represented area: **30 × 30 km** around the summit
- source DEM: public Skadi/SRTM, four 3601 × 3601 HGT tiles
- generated terrain: **513 × 513 samples / 263,169 vertices / 524,288 terrain triangles**
- terrain skirt: **4,096 triangles**
- vertical proportion: **1:1 physical scale**, no elevation exaggeration
- sampled elevation inside the model: roughly **880 m to 5,595 m**

### Sentinel-2 material

- true-colour imagery uses Copernicus Sentinel-2 B04/B03/B02
- the image is reprojected to the exact Phase 2 terrain bbox
- texture: **2048 × 2048 WebP**
- valid source coverage in the current composite: **99.9655%** before residual edge repair
- the final GLB uses both `EXT_texture_webp` and `KHR_draco_mesh_compression`
- final `damavand.glb`: about **1.51 MiB**
- imagery attribution is rendered in-view

### Cinematic camera

Phase 4 added an explicit camera state machine:

```text
loading → intro → cinematic → manual
                         ↘ focus → manual
```

The first visit flies into Damavand's hero angle and performs a short orbit. Pointer, touch, wheel, keyboard or direct OrbitControls input cancels authored motion immediately. Camera state is synchronized back from OrbitControls so later zoom/focus/reset operations do not snap to stale coordinates. Reduced-motion users skip the intro/orbit.

### Terrain-aware routes

Phase 5 introduces a reusable route layer rather than baking route geometry into the mountain GLB.

The built-in **Damavand South Route** is generated at build time from OpenStreetMap path geometry. Published Damavand GPS landmarks act as corridor controls between Goosfand Sara, Bargah Sevom and the summit. The current generated reference contains **167 geographic points**, and all ten landmark-to-landmark segments resolved through the OSM trail graph with **100% OSM corridor coverage** in the validated build. Its generated geometry is about **7.35 km**; the product card keeps the familiar published reference headline of about **8.0 km / 2,630 m ascent** while DEM-derived metrics are used for terrain sampling.

At runtime:

- lat/lon is transformed with the same geographic coordinate contract used by the terrain builder
- route points are densified and raycast downward onto the real Damavand mesh
- the rendered tube is lifted by a tiny physical offset to avoid z-fighting
- distance, DEM-sampled min/max elevation, ascent and descent are computed from the projected route
- **Focus route** frames the route bounds with the Phase 4 camera system
- the route can be shown/hidden from the route card or Layers menu
- users can **Import GPX** directly in the browser; the file is parsed locally and is not uploaded by this implementation
- imported GPX tracks use their own computed distance/ascent metrics and can be replaced with the built-in South Route at any time

The built-in line is a reference visualization, **not turn-by-turn navigation**. Route source, licensing and safety notes are documented in `ROUTE_ATTRIBUTION.md`.

## Coordinate contract

```text
+X = east
+Y = elevation
+Z = north
UV  = west→east / south→north
units = metres before ViewerEngine presentation normalization
```

Phase 5 preserves that contract through the ViewerEngine normalization transform, which is why a GPX route and the generated DEM land on the same surface without a second coordinate system.

## Reproducible pipelines

Terrain:

```text
scripts/terrain/damavand.json
scripts/terrain/build_peak_terrain.py
.github/workflows/build-damavand-terrain.yml
```

Satellite imagery:

```text
scripts/imagery/damavand.json
scripts/imagery/build_sentinel_texture.py
scripts/imagery/embed_texture.py
.github/workflows/build-damavand-imagery.yml
```

Cinematic camera:

```text
scripts/camera/apply_phase4_code.py
.github/workflows/apply-phase4-camera.yml
```

Routes:

```text
scripts/routes/damavand-south.json
scripts/routes/build_reference_route.py
scripts/routes/apply_phase5_engine.py
.github/workflows/apply-phase5-routes.yml
```

The Phase 5 workflow rebuilds the South reference route, applies the terrain-aware ViewerEngine migration, runs the production TypeScript/Vite build, runs ESLint, validates generated route density/source metadata, and publishes the generated route data + engine migration back to `iran-peaks`.

## Development

Use a current Node.js LTS release.

```bash
npm install
npm run dev
```

Quality gates:

```bash
npm run build
npm run lint
```

## Seven-phase roadmap

1. ✅ **Foundation** — peak domain, Damavand-only runtime, stable viewer boundary
2. ✅ **Real Terrain Pipeline** — production-density DEM → terrain mesh → validated + compressed Damavand GLB
3. ✅ **Satellite Material & Lighting** — georeferenced Sentinel-2 texture, PBR terrain material and mountain daylight presentation
4. ✅ **Camera & Cinematic Experience** — intro flight, interruptible cinematic orbit, camera-state synchronization, canonical reset and reduced motion
5. ✅ **Routes & Mountain Intelligence** — generated South Route, real terrain projection, DEM-derived metrics, route focus/layers and local GPX import
6. **Hotspots & Peak UI** — summit, shelters, landmarks, hazards and final product UI
7. **Production Hardening** — LOD, GPU texture compression/KTX2, caching, mobile GPU handling, dependency audit and tests

## Attribution

Terrain-source attribution is documented in `TERRAIN_ATTRIBUTION.md`. Satellite-source attribution is documented in `IMAGERY_ATTRIBUTION.md`. Route-source attribution and safety notes are documented in `ROUTE_ATTRIBUTION.md`.

## Upstream

This repository began as a fork of `thebuggeddev/empire`, whose Three.js viewer architecture is being adapted for a mountain-specific experience. The upstream repository currently does not declare a license, so reuse/distribution of upstream code should not be assumed to grant commercial rights without permission from the original author.
