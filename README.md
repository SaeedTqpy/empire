# Iran 3D Peaks

Interactive 3D mountain atlas for Iran, starting with **Mount Damavand**.

The product direction is a real-terrain experience: DEM-derived mountain geometry, satellite imagery, cinematic camera movement, climbing routes, shelters and mountain landmarks.

## Current status — Phase 6 complete + extreme-detail terrain/imagery profile

Damavand now combines real terrain, georeferenced satellite imagery, an interruptible cinematic camera, terrain-aware 3D climbing routes, geo-aware mountain markers, a 4K satellite material, and an extreme close-inspection terrain profile.

### Extreme-detail real terrain

- `Peak` is the product domain model under `src/types/peak.ts`
- Damavand is the only product dataset rendered at runtime
- represented area: **30 × 30 km** around the summit
- source DEM: public Skadi/SRTM, four 3601 × 3601 HGT tiles
- generated terrain: **1025 × 1025 samples / 1,050,625 vertices / 2,097,152 terrain triangles**
- horizontal output spacing: roughly **29.3 m** across the 30 km footprint
- terrain skirt: **8,192 triangles**
- vertical proportion: **1:1 physical scale**, no elevation exaggeration
- sampled elevation inside the current build: roughly **877 m to 5,599 m**

The 1025 grid replaces the earlier 513 grid. This is a real geometry upgrade: the viewer no longer relies on a ~58 m terrain grid when the source DEM contains substantially finer elevation samples.

### Ultra-detail Sentinel-2 material

- true-colour imagery uses Copernicus Sentinel-2 B04/B03/B02
- the image is reprojected to the exact terrain bbox
- source RGB resolution recorded by the pipeline: **10 m**
- authoring texture: **4096 × 4096**, about **7.32 m/output texel** across the 30 km terrain footprint
- authoring master: **lossless PNG**
- browser texture: **4096 × 4096 WebP, quality 95**, encoded once from the lossless master
- valid source coverage in the current composite: **99.9657%** before residual edge repair
- the final GLB uses both `EXT_texture_webp` and `KHR_draco_mesh_compression`
- final `damavand.glb`: about **7.4 MiB** on disk; the embedded WebP texture is about **4.68 MB**
- no AI/synthetic super-resolution is used; the profile is designed to preserve real source detail rather than manufacture extra geographic detail
- viewer sampling uses mipmaps, trilinear filtering and device-aware anisotropy up to 16×
- extreme inspection uses a **0.018** OrbitControls minimum distance, zoom-to-cursor and a **0.002** camera near plane
- the render budget allows up to **3 DPR / 12 million rendered pixels** before adaptive scaling
- imagery attribution is rendered in-view

An 8K or 16K texture generated from the same 10 m source would mostly be an upscale rather than additional observed ground detail. The next genuine imagery-quality jump requires a higher-resolution licensed imagery source rather than more interpolation.

### Cinematic camera

Phase 4 added an explicit camera state machine:

```text
loading → intro → cinematic → manual
                         ↘ focus → manual
```

The first visit flies into Damavand's hero angle and performs a short orbit. Pointer, touch, wheel, keyboard or direct OrbitControls input cancels authored motion immediately. Camera state is synchronized back from OrbitControls so later zoom/focus/reset operations do not snap to stale coordinates. Reduced-motion users skip the intro/orbit.

### Terrain-aware routes

Phase 5 introduced a reusable route layer rather than baking route geometry into the mountain GLB.

The built-in **Damavand South Route** is generated at build time from OpenStreetMap path geometry. Published Damavand GPS landmarks act as corridor controls between Goosfand Sara, Bargah Sevom and the summit. The validated reference contains **167 geographic points**, and all ten landmark-to-landmark segments resolved through the OSM trail graph with **100% OSM corridor coverage** in that build. Its generated geometry is about **7.35 km**; the product card keeps the published reference headline of about **8.0 km / 2,630 m ascent** while DEM-derived metrics are used for terrain sampling.

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

### Geo-aware mountain markers

Phase 6 promotes mountain hotspots from normalized model anchors to WGS84 geographic data.

The first Damavand marker set contains six categories:

- **Summit** — Damavand Summit
- **Shelter** — Bargah Sevom
- **Landmark** — Sang-e Do Shakh
- **Hazard context** — Upper Ridge / high-altitude context marker
- **Water context** — Seasonal Watercourse
- **Route context** — Goosfand Sara

Marker coordinates reuse the same waypoint dataset that guides the Phase 5 South Route. Reference elevation remains metadata; visual Y is resolved independently from the DEM.

At runtime each marker follows this path:

```text
WGS84 lat/lon
    ↓
same terrain georeference used by routes
    ↓
normalized ViewerEngine model coordinates
    ↓
downward raycast onto the real DEM mesh
    ↓
small physical lift to prevent z-fighting
    ↓
projected HTML marker + occlusion handling
```

Resolved marker positions are cached, so the application does not raycast the terrain again every frame. Clicking a marker uses the Phase 4 camera state system to focus its real terrain location. Active markers also get a terrain highlight.

The viewer now includes:

- category-coded mountain pins
- compact **All / Summit / Shelter / Landmark / Hazard / Water / Route** filtering
- hover labels
- click-to-focus camera behavior
- marker detail cards with reference elevation, WGS84 coordinates, description and source label
- separate safety wording for seasonal water, shelter status and high-altitude hazard context
- removal of the remaining Empire-specific **Artifacts** and **Timeline** toolbar actions from the active mountain viewer

These markers are contextual visualization, not live conditions or navigation. Shelter status, water availability, hazards, weather, access and rescue information must be checked separately before a climb. Source and safety scope are documented in `HOTSPOT_ATTRIBUTION.md`.

## Coordinate contract

```text
+X = east
+Y = elevation
+Z = north
UV  = west→east / south→north
units = metres before ViewerEngine presentation normalization
```

Routes and Phase 6 hotspots preserve this same contract through the ViewerEngine normalization transform, so GPX lines, mountain markers and the generated DEM share one geographic frame.

## Reproducible pipelines

Terrain:

```text
scripts/terrain/damavand.json
scripts/terrain/build_peak_terrain.py
.github/workflows/build-damavand-terrain.yml
```

The standalone terrain workflow is validation-only. It deliberately does not publish the canonical application GLB, preventing a terrain-only build from overwriting the satellite material.

Canonical terrain + satellite build:

```text
scripts/imagery/damavand.json
scripts/imagery/build_sentinel_texture.py
scripts/imagery/embed_texture.py
scripts/imagery/apply_ultra_detail_code.py
scripts/imagery/apply_extreme_detail_code.py
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

Mountain markers:

```text
src/data/peaks/damavand-hotspots.ts
scripts/hotspots/apply_phase6_code.py
.github/workflows/apply-phase6-hotspots.yml
HOTSPOT_ATTRIBUTION.md
```

The canonical imagery workflow now rebuilds the **1025-grid terrain and 4K texture together**, validates both manifests, keeps a lossless imagery master, performs a single high-quality WebP encode, applies Draco geometry compression, then runs the production TypeScript/Vite build and ESLint before publishing the matched model + terrain + imagery assets.

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
2. ✅ **Real Terrain Pipeline** — DEM → validated + compressed Damavand GLB, now at native-detail 1025 grid
3. ✅ **Satellite Material & Lighting** — georeferenced Sentinel-2 texture, PBR terrain material and mountain daylight presentation
4. ✅ **Camera & Cinematic Experience** — intro flight, interruptible cinematic orbit, camera-state synchronization, canonical reset and reduced motion
5. ✅ **Routes & Mountain Intelligence** — generated South Route, real terrain projection, DEM-derived metrics, route focus/layers and local GPX import
6. ✅ **Hotspots & Peak UI** — WGS84 summit/shelter/landmark/hazard/water/route markers, DEM surface projection, filtering, focus and contextual detail UI
7. **Production Hardening** — LOD, GPU texture compression/KTX2, caching, mobile GPU handling, dependency audit and tests

## Attribution

Terrain-source attribution is documented in `TERRAIN_ATTRIBUTION.md`. Satellite-source attribution is documented in `IMAGERY_ATTRIBUTION.md`. Route-source attribution and safety notes are documented in `ROUTE_ATTRIBUTION.md`. Mountain marker source/safety scope is documented in `HOTSPOT_ATTRIBUTION.md`.

## Upstream

This repository began as a fork of `thebuggeddev/empire`, whose Three.js viewer architecture is being adapted for a mountain-specific experience. The upstream repository currently does not declare a license, so reuse/distribution of upstream code should not be assumed to grant commercial rights without permission from the original author.
