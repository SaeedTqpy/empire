# Iran 3D Peaks

Interactive 3D mountain atlas for Iran, starting with **Mount Damavand**.

The product direction is a real-terrain experience: DEM-derived mountain geometry, georeferenced imagery, cinematic camera movement, climbing routes, shelters and mountain landmarks — backed by camera-driven spatial LOD streaming.

## Current status — Phase 8 complete

Damavand now combines real terrain, a self-hosted Sentinel-2 fallback, an interruptible cinematic camera, terrain-aware 3D climbing routes, geo-aware mountain markers, 3D Tiles streaming, and a **validated sub-meter runtime imagery layer over the summit / south-side source footprint**.

### Real terrain base

- represented area: **30 × 30 km** around the summit
- source DEM: public Skadi/SRTM, four 3601 × 3601 HGT tiles
- canonical source grid: **1025 × 1025 samples / 1,050,625 vertices / 2,097,152 terrain triangles**
- source-grid spacing: roughly **29.3 m** across the 30 km footprint
- vertical proportion: **1:1 physical scale**, no elevation exaggeration
- sampled elevation in the current build: roughly **877 m to 5,599 m**

The elevation surface remains SRTM-derived. Phase 8 increases observed **imagery** fidelity; it does not misrepresent the terrain mesh as sub-meter elevation geometry.

### Sentinel-2 fallback

- true-colour imagery uses Copernicus Sentinel-2 B04/B03/B02
- source RGB resolution recorded by the pipeline: **10 m**
- authoring master: **4096 × 4096 lossless PNG**, about **7.32 m/output texel** across the 30 km footprint
- browser delivery uses high-quality WebP and Draco-compressed geometry
- current composite valid source coverage: **99.9657%** before residual edge repair
- no AI/synthetic super-resolution is used
- imagery attribution is rendered in-view

Sentinel-2 remains the complete visual fallback under the Phase 8 high-detail region.

### Phase 8 — Damavand Digital Twin imagery

Phase 8 source discovery found a real higher-resolution source at the Damavand summit in **World Imagery (Wayback 2026-03-26)** metadata.

Validated source record:

- provider: **Vantor**
- product: **Vivid**
- source date: **2025-06-22**
- observed source resolution (`SRC_RES`): **0.34 m**
- sampled/delivered resolution (`SAMP_RES`): **0.6 m**
- validated maximum map level: **18**
- metadata feature: `OBJECTID 3154394`
- source footprint contains the Damavand summit
- source WGS84 bounds: `52.0312477, 35.6338357 → 52.1723191, 35.9580380`
- footprint bounds intersect about **22.2212%** of the current 30 × 30 km Damavand terrain bbox

This is deliberately described as a **summit / south-side VHR region**, not 0.6 m coverage for the whole mountain.

Runtime behavior:

```text
Phase 7 3D Tiles terrain
        ↓
exact local metric X/Z → WGS84 lon/lat per vertex
        ↓
EPSG:3857 projection per vertex
        ↓
validated Wayback z0…z18 imagery stream
        ↓
VHR over the validated region
        ↓
Sentinel-2 everywhere else / on VHR failure
```

The implementation keeps `3d-tiles-renderer` image fetching, caching, material composition and virtual leaf splitting, while replacing only the geographic projection step required by Damavand's local metric terrain frame.

The VHR source is **runtime-only**:

- no Wayback/Vantor imagery is copied into `public/`
- no VHR imagery is baked into GLBs
- no offline tile export is produced
- a CI guard fails if VHR assets are accidentally bundled
- z18 is a hard fidelity ceiling even though the service exposes higher tile levels, because the matching Damavand metadata record declares `MaxMapLevel = 18`

Viewer attribution includes Esri/Vantor/Earthstar/GIS User Community together with the Copernicus fallback attribution. See `DIGITAL_TWIN_SOURCES.md` for the exact source contract and deployment caveats.

Comparison switches:

```text
?detail=0     disable Phase 8 VHR, keep 3D Tiles
?streaming=0  use the canonical single-GLB fallback path
```

### Spatial 3D Tiles streaming

Phase 7 removed the monolithic visual-model bottleneck. Damavand uses a **3D Tiles 1.1 `REPLACE` quadtree** selected from camera screen-space error.

```text
ViewerEngine
├── hidden interaction proxy
│   ├── GPX / route terrain projection
│   ├── geo-hotspot terrain projection
│   └── visual fallback if streaming cannot start
└── TerrainTilesStreamer
    ├── L0: 1 whole-mountain tile
    ├── L1: 4 quadrant tiles
    └── L2: 16 near-field tiles
         └── Phase 8 virtual image-detail splitting where VHR is available
```

The self-hosted hierarchy contains **21 visual tiles** plus one lightweight interaction proxy and is about **9.36 MiB** in generated tile assets.

| LOD | Visual tiles | Terrain grid / tile | Embedded texture / tile | Approx terrain spacing | Approx embedded imagery texel |
| --- | ---: | ---: | ---: | ---: | ---: |
| L0 | 1 | 129 × 129 | 512 × 512 | 234.4 m | 58.6 m |
| L1 | 4 | 129 × 129 | 512 × 512 | 117.2 m | 29.3 m |
| L2 | 16 | 257 × 257 | 1024 × 1024 | 29.3 m | 7.3 m |

Phase 8 does not duplicate the VHR imagery into this table; high-detail image tiles are requested only at runtime over the validated source region.

### Cinematic camera

Phase 4 added an explicit camera state machine:

```text
loading → intro → cinematic → manual
                         ↘ focus → manual
```

Pointer, touch, wheel, keyboard or direct OrbitControls input cancels authored motion immediately. Camera state is synchronized back from OrbitControls and reduced-motion users skip the intro/orbit.

### Terrain-aware routes

The built-in **Damavand South Route** is generated from OpenStreetMap path geometry plus published Damavand GPS landmarks. The validated reference contains **167 geographic points** and all ten landmark-to-landmark segments resolved through the OSM trail graph in that build.

At runtime:

- lat/lon uses the same geographic coordinate contract as terrain
- route points are densified and raycast onto the interaction terrain
- distance, DEM-sampled min/max elevation, ascent and descent are computed from the route
- **Focus route** frames the route with the Phase 4 camera system
- users can import GPX locally in the browser; the file is not uploaded by this implementation

The built-in line is a reference visualization, **not turn-by-turn navigation**. See `ROUTE_ATTRIBUTION.md`.

### Geo-aware mountain markers

Phase 6 uses WGS84 mountain markers for summit, shelter, landmark, hazard, seasonal water and route context. Their visual elevation is resolved independently against the interaction DEM, so markers, GPX and streamed visual terrain remain in one geographic frame.

These markers are contextual visualization, not live mountain conditions. See `HOTSPOT_ATTRIBUTION.md`.

## Coordinate contract

```text
+X = east
+Y = elevation above the shared build base
+Z = north
UV  = west→east / south→north
units = metres before ViewerEngine presentation normalization
```

The canonical model, interaction proxy, streamed visual tiles, routes, geo hotspots and Phase 8 VHR projection preserve this same frame.

## Reproducible pipelines

Terrain source validation:

```text
scripts/terrain/damavand.json
scripts/terrain/build_peak_terrain.py
.github/workflows/build-damavand-terrain.yml
```

Canonical terrain + Sentinel fallback:

```text
scripts/imagery/damavand.json
scripts/imagery/build_sentinel_texture.py
scripts/imagery/embed_texture.py
.github/workflows/build-damavand-imagery.yml
```

Spatial streaming:

```text
scripts/streaming/build_damavand_quadtree.py
scripts/streaming/validate_streaming.py
.github/workflows/apply-phase7-streaming.yml
STREAMING_ARCHITECTURE.md
```

Digital Twin / VHR source gates:

```text
scripts/digital_twin/probe_esri_world_imagery.py
scripts/digital_twin/probe_esri_wayback_runtime.py
scripts/digital_twin/probe_esri_wayback_tile.py
scripts/digital_twin/validate_phase8_contract.py
.github/workflows/probe-phase8-esri-imagery.yml
.github/workflows/probe-phase8-esri-runtime.yml
.github/workflows/validate-phase8-digital-twin.yml
DIGITAL_TWIN_SOURCES.md
```

Other source probes are retained under `scripts/digital_twin/` so rejected/unavailable sources remain auditable instead of disappearing from project history.

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
python scripts/digital_twin/validate_phase8_contract.py
```

## Roadmap

1. ✅ **Foundation** — peak domain, Damavand-only runtime, stable viewer boundary
2. ✅ **Real Terrain Pipeline** — DEM → validated + compressed Damavand terrain
3. ✅ **Satellite Material & Lighting** — georeferenced Sentinel-2 texture and mountain daylight presentation
4. ✅ **Camera & Cinematic Experience** — intro flight, interruptible orbit, canonical reset and reduced motion
5. ✅ **Routes & Mountain Intelligence** — South Route, terrain projection, metrics, route focus/layers and local GPX import
6. ✅ **Hotspots & Peak UI** — WGS84 summit/shelter/landmark/hazard/water/route markers, filtering and focus
7. ✅ **3D Tiles + LOD + High-Res Streaming Foundation** — spatial hierarchy, SSE selection, cache policy, interaction proxy and canonical fallback
8. ✅ **Damavand Digital Twin / Maximum Detail** — validated Vantor/Esri 0.34 m source / 0.6 m sampled summit imagery, exact per-vertex geographic drape, runtime-only z18 streaming and Sentinel fallback
9. **Production Hardening** — GPU-native texture compression/KTX2, deeper cache policy, mobile GPU profiling, dependency/security audit and automated runtime tests

## Attribution

Terrain-source attribution is documented in `TERRAIN_ATTRIBUTION.md`. Sentinel source attribution is documented in `IMAGERY_ATTRIBUTION.md`. Phase 8 high-detail source scope and terms are documented in `DIGITAL_TWIN_SOURCES.md`. Route source/safety notes are in `ROUTE_ATTRIBUTION.md`; mountain marker source/safety scope is in `HOTSPOT_ATTRIBUTION.md`.

## Upstream

This repository began as a fork of `thebuggeddev/empire`, whose Three.js viewer architecture is being adapted for a mountain-specific experience. The upstream repository currently does not declare a license, so reuse/distribution of upstream code should not be assumed to grant commercial rights without permission from the original author.
