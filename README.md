# Iran 3D Peaks

Interactive 3D mountain atlas for Iran, starting with **Mount Damavand**.

The product direction is a real-terrain experience: DEM-derived mountain geometry, satellite imagery, cinematic camera movement, climbing routes, shelters and mountain landmarks — now backed by camera-driven spatial LOD streaming.

## Current status — Phase 7 complete

Damavand now combines real terrain, georeferenced satellite imagery, an interruptible cinematic camera, terrain-aware 3D climbing routes, geo-aware mountain markers, extreme close inspection, and a **3D Tiles 1.1 spatial streaming foundation**.

### Extreme-detail real terrain

- `Peak` is the product domain model under `src/types/peak.ts`
- Damavand is the only product dataset rendered at runtime
- represented area: **30 × 30 km** around the summit
- source DEM: public Skadi/SRTM, four 3601 × 3601 HGT tiles
- canonical source grid: **1025 × 1025 samples / 1,050,625 vertices / 2,097,152 terrain triangles**
- horizontal source-grid spacing: roughly **29.3 m** across the 30 km footprint
- vertical proportion: **1:1 physical scale**, no elevation exaggeration
- sampled elevation inside the current build: roughly **877 m to 5,599 m**

The 1025 source grid is now the common high-detail terrain source for both the canonical fallback model and the Phase 7 tiled hierarchy.

### Ultra-detail Sentinel-2 material

- true-colour imagery uses Copernicus Sentinel-2 B04/B03/B02
- imagery is reprojected to the exact terrain bbox
- source RGB resolution recorded by the pipeline: **10 m**
- authoring master: **4096 × 4096 lossless PNG**, about **7.32 m/output texel** across the 30 km footprint
- browser delivery uses high-quality WebP and Draco-compressed geometry
- current composite valid source coverage: **99.9657%** before residual edge repair
- no AI/synthetic super-resolution is used in the accurate source profile
- viewer sampling uses mipmaps, trilinear filtering and device-aware anisotropy up to 16×
- extreme inspection uses a **0.018** OrbitControls minimum distance, zoom-to-cursor and a **0.002** camera near plane
- the render budget allows up to **3 DPR / 12 million rendered pixels** before adaptive scaling
- imagery attribution is rendered in-view

An 8K or 16K upscale of the same 10 m source would not add observed ground detail. The next genuine quality jump belongs to Phase 8: higher-resolution real-world source data.

### Spatial 3D Tiles streaming

Phase 7 removes the monolithic visual-model bottleneck. The default Damavand presentation is now a **3D Tiles 1.1 `REPLACE` quadtree** selected from camera screen-space error.

```text
ViewerEngine
├── hidden interaction proxy
│   ├── GPX / route terrain projection
│   ├── geo-hotspot terrain projection
│   └── visual fallback if streaming cannot start
└── TerrainTilesStreamer
    └── 3D Tiles hierarchy
        ├── L0: 1 whole-mountain tile
        ├── L1: 4 quadrant tiles
        └── L2: 16 near-field tiles
```

The validated starter dataset contains **21 visual tiles** plus one lightweight interaction proxy and is about **9.36 MiB** in total generated tile assets.

| LOD | Visual tiles | Terrain grid / tile | Texture / tile | Approx terrain spacing | Approx imagery texel |
| --- | ---: | ---: | ---: | ---: | ---: |
| L0 | 1 | 129 × 129 | 512 × 512 | 234.4 m | 58.6 m |
| L1 | 4 | 129 × 129 | 512 × 512 | 117.2 m | 29.3 m |
| L2 | 16 | 257 × 257 | 1024 × 1024 | 29.3 m | 7.3 m |

The L2 leaves preserve the useful detail of the previous 1025-grid / 4K monolithic build, but the detail is spatially partitioned. Moving closer causes higher-detail child tiles to replace their ancestors instead of keeping the maximum-detail mountain permanently resident.

Runtime behavior:

- `3d-tiles-renderer` performs camera-driven screen-space-error selection
- ancestors remain available while higher-detail descendants load
- request concurrency and LRU memory budgets adapt to `navigator.deviceMemory` when available
- render resolution changes are propagated to the tile selector
- loaded tile textures receive the viewer's mipmap / trilinear / anisotropic sampling policy
- wireframe and x-ray modes are forwarded to streamed terrain
- a compact viewer badge reports active LOD / visible-tile state
- the full canonical `damavand.glb` remains an explicit fallback
- `?streaming=0` forces the canonical single-GLB path for debugging/comparison

The visual hierarchy and interaction proxy share the exact same metric coordinate contract and ViewerEngine normalization. Existing routes, imported GPX tracks, hotspots and camera focus behavior therefore do not depend on which visual tile happens to be resident.

**Phase 7 is an architecture upgrade, not a claim of new observed terrain resolution.** Phase 8 can replace or deepen leaf content with commercial 30 cm imagery, sub-meter elevation, photogrammetry or LiDAR without changing the product boundary.

### Cinematic camera

Phase 4 added an explicit camera state machine:

```text
loading → intro → cinematic → manual
                         ↘ focus → manual
```

The first visit flies into Damavand's hero angle and performs a short orbit. Pointer, touch, wheel, keyboard or direct OrbitControls input cancels authored motion immediately. Camera state is synchronized back from OrbitControls so later zoom/focus/reset operations do not snap to stale coordinates. Reduced-motion users skip the intro/orbit.

### Terrain-aware routes

Phase 5 introduced a reusable route layer rather than baking route geometry into terrain assets.

The built-in **Damavand South Route** is generated at build time from OpenStreetMap path geometry. Published Damavand GPS landmarks act as corridor controls between Goosfand Sara, Bargah Sevom and the summit. The validated reference contains **167 geographic points**, and all ten landmark-to-landmark segments resolved through the OSM trail graph with **100% OSM corridor coverage** in that build. Its generated geometry is about **7.35 km**; the product card keeps the published reference headline of about **8.0 km / 2,630 m ascent** while DEM-derived metrics are used for terrain sampling.

At runtime:

- lat/lon is transformed with the same geographic coordinate contract used by the terrain builder
- route points are densified and raycast downward onto the interaction terrain
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

Marker coordinates reuse the same waypoint dataset that guides the Phase 5 South Route. Reference elevation remains metadata; visual Y is resolved independently from the interaction terrain.

```text
WGS84 lat/lon
    ↓
same terrain georeference used by routes
    ↓
normalized ViewerEngine coordinates
    ↓
downward raycast onto interaction DEM
    ↓
small physical lift
    ↓
projected HTML marker + occlusion handling
```

Resolved marker positions are cached. Clicking a marker uses the Phase 4 camera state system to focus its real terrain location. Active markers also get a terrain highlight.

These markers are contextual visualization, not live conditions or navigation. Shelter status, water availability, hazards, weather, access and rescue information must be checked separately before a climb. Source and safety scope are documented in `HOTSPOT_ATTRIBUTION.md`.

## Coordinate contract

```text
+X = east
+Y = elevation above the shared build base
+Z = north
UV  = west→east / south→north
units = metres before ViewerEngine presentation normalization
```

The canonical model, interaction proxy, streamed visual tiles, routes and geo hotspots preserve this same frame.

## Reproducible pipelines

Terrain source validation:

```text
scripts/terrain/damavand.json
scripts/terrain/build_peak_terrain.py
.github/workflows/build-damavand-terrain.yml
```

Canonical terrain + satellite fallback:

```text
scripts/imagery/damavand.json
scripts/imagery/build_sentinel_texture.py
scripts/imagery/embed_texture.py
scripts/imagery/apply_ultra_detail_code.py
scripts/imagery/apply_extreme_detail_code.py
.github/workflows/build-damavand-imagery.yml
```

Spatial streaming:

```text
scripts/streaming/build_damavand_quadtree.py
scripts/streaming/validate_streaming.py
scripts/streaming/apply_phase7_code.py
.github/workflows/apply-phase7-streaming.yml
STREAMING_ARCHITECTURE.md
```

The Phase 7 build samples the canonical 1025 DEM once, derives every LOD from that grid, crops imagery from the same georeferenced 4K lossless master, WebP-compresses textures, Draco-compresses geometry, validates the complete 1/4/16 hierarchy, then runs the TypeScript/Vite production build and ESLint before publishing.

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

## Roadmap

1. ✅ **Foundation** — peak domain, Damavand-only runtime, stable viewer boundary
2. ✅ **Real Terrain Pipeline** — DEM → validated + compressed Damavand terrain
3. ✅ **Satellite Material & Lighting** — georeferenced Sentinel-2 texture and mountain daylight presentation
4. ✅ **Camera & Cinematic Experience** — intro flight, interruptible orbit, canonical reset and reduced motion
5. ✅ **Routes & Mountain Intelligence** — South Route, terrain projection, metrics, route focus/layers and local GPX import
6. ✅ **Hotspots & Peak UI** — WGS84 summit/shelter/landmark/hazard/water/route markers, filtering and focus
7. ✅ **3D Tiles + LOD + High-Res Streaming Foundation** — spatial 1/4/16 hierarchy, screen-space-error selection, adaptive cache policy, interaction proxy and canonical fallback
8. ⏭ **Damavand Digital Twin / Maximum Detail** — plug genuinely higher-resolution imagery/elevation and targeted photogrammetry/LiDAR into the streaming hierarchy
9. **Production Hardening** — GPU-native texture compression/KTX2, deeper cache/offline policy, mobile GPU profiling, dependency/security audit and automated runtime tests

## Attribution

Terrain-source attribution is documented in `TERRAIN_ATTRIBUTION.md`. Satellite-source attribution is documented in `IMAGERY_ATTRIBUTION.md`. Route-source attribution and safety notes are documented in `ROUTE_ATTRIBUTION.md`. Mountain marker source/safety scope is documented in `HOTSPOT_ATTRIBUTION.md`.

## Upstream

This repository began as a fork of `thebuggeddev/empire`, whose Three.js viewer architecture is being adapted for a mountain-specific experience. The upstream repository currently does not declare a license, so reuse/distribution of upstream code should not be assumed to grant commercial rights without permission from the original author.
