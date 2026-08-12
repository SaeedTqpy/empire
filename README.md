# Iran 3D Peaks

Interactive 3D mountain atlas for Iran, starting with **Mount Damavand**.

The product direction is a real-terrain experience: DEM-derived mountain geometry, satellite imagery, cinematic camera movement, climbing routes, shelters and mountain landmarks.

## Current status — Phase 4 complete

Damavand now renders as a real terrain model with geographically aligned satellite imagery, mountain-specific daylight presentation, and an interruptible cinematic camera experience.

### Real terrain

- `Peak` is the product domain model under `src/types/peak.ts`
- Damavand is the only product dataset rendered at runtime
- the Three.js viewer loads the versioned `/models/damavand.glb` asset
- terrain comes from public Skadi/SRTM elevation data
- represented area: **30 × 30 km** around the summit
- source DEM: four 3601 × 3601 HGT tiles
- generated terrain: **513 × 513 samples / 263,169 vertices / 524,288 terrain triangles**
- terrain skirt: **4,096 triangles**
- vertical proportion remains **1:1 physical scale** with no elevation exaggeration
- sampled elevation inside the model is roughly **880 m to 5,595 m**

### Sentinel-2 material

- true-colour imagery is built from **Copernicus Sentinel-2 B04/B03/B02** surface reflectance
- the imagery builder reads the exact Phase 2 terrain bbox, so the satellite raster and terrain UV contract stay aligned
- output texture: **2048 × 2048**
- valid source-data coverage: **99.9655%** before residual edge repair
- cloud, cloud shadow and invalid pixels are masked with the Sentinel-2 Scene Classification Layer when available
- the final composite currently uses two exceptionally clear observations:
  - `S2A_T39SXV_20260614T071319_L2A` — 14 June 2026
  - `S2B_T39SWV_20260710T072912_L2A` — 10 July 2026
- exact scene IDs, acquisition timestamps, cloud-cover metadata, bbox and processing parameters are recorded in `public/models/damavand.imagery.json`
- required imagery credit is rendered in the viewer: **Contains modified Copernicus Sentinel data 2026**

### Web delivery

- satellite imagery is embedded into a rough non-metallic PBR terrain material
- the texture is converted to **WebP** before geometry compression
- terrain geometry is then compressed with **Draco**
- final GLB uses both `EXT_texture_webp` and `KHR_draco_mesh_compression`
- embedded 2048 × 2048 WebP payload: about **730 KB**
- final `damavand.glb`: **1,583,332 bytes (~1.51 MiB)**
- generated peak preview: about **162 KB WebP**
- Earth Search and remote Sentinel COGs are build-time dependencies only; the production browser loads local generated assets

### Mountain presentation

The original museum-style Empire lighting has been adapted for terrain:

- cool daylight hemisphere illumination
- stronger elevated warm sun/key light
- reduced decorative rim light
- softer terrain contact shadow
- cool atmospheric fog
- blue-sky / bright-horizon environment gradient
- outdoor mountain stage background
- terrain-specific control labels
- in-view satellite attribution

### Cinematic camera

Phase 4 adds an explicit camera state machine in `src/types/viewer-camera.ts`:

```text
loading → intro → cinematic → manual
                         ↘ focus → manual
```

The experience now includes:

- an authored first-load flight from a wider, lower bearing into Damavand's canonical hero angle
- a short GSAP-driven cinematic orbit after the arrival
- immediate cancellation of authored camera motion on pointer, touch, wheel, keyboard zoom/orbit, or direct OrbitControls interaction
- `OrbitControls` → camera-state synchronization so manual drag never causes the next zoom/focus/reset to snap back to stale coordinates
- canonical animated Reset View behavior
- hotspot focus as an explicit camera mode
- reduced-motion support that skips intro/orbit and frames the mountain directly
- the existing user-controlled **Start 3D orbit** mode remains available after the cinematic sequence

The reproducible Phase 4 migration lives at:

```text
scripts/camera/apply_phase4_code.py
```

and is validated by:

```text
.github/workflows/apply-phase4-camera.yml
```

The workflow applies the camera migration, runs production build + ESLint, then publishes the validated viewer code back to `iran-peaks`.

## Architecture

```text
                         ┌─ Skadi / SRTM HGT
                         │       ↓
                         │  DEM sample / mesh
                         │       ↓
Peak domain ─────────────┼─ 513×513 terrain + skirt
                         │       ↓
                         │      UVs
                         │       ↓
                         └───────────────────────────┐
                                                     │
Copernicus Sentinel-2                                │
        ↓                                            │
Earth Search STAC                                    │
        ↓                                            │
low-cloud scene selection                            │
        ↓                                            │
B04/B03/B02 + SCL mask                               │
        ↓                                            │
exact terrain-bbox reprojection                      │
        ↓                                            │
2048×2048 true-colour composite                      │
        ↓                                            │
PBR baseColor texture ───────────────────────────────┘
        ↓
WebP texture compression
        ↓
Draco geometry compression
        ↓
public/models/damavand.glb
        ↓
Three.js ViewerEngine + mountain daylight profile
        ↓
intro flight → cinematic orbit → manual camera
```

The geographic coordinate contract remains:

```text
+X = east
+Y = elevation
+Z = north
UV  = west→east / south→north
units = metres before ViewerEngine presentation normalization
```

That contract is the basis for projecting GPX routes and geographic hotspots onto the same mesh in later phases.

## Terrain pipeline

Terrain configuration:

```text
scripts/terrain/damavand.json
```

Builder:

```text
scripts/terrain/build_peak_terrain.py
```

Workflow:

```text
.github/workflows/build-damavand-terrain.yml
```

The terrain workflow restores/prefetches source HGT tiles, samples the 30 km bbox, builds and validates the production-density terrain, applies Draco compression and publishes the generated terrain assets.

Terrain-source attribution is documented in `TERRAIN_ATTRIBUTION.md`.

## Imagery pipeline

Imagery configuration:

```text
scripts/imagery/damavand.json
```

Main texture builder:

```text
scripts/imagery/build_sentinel_texture.py
```

PBR authoring step:

```text
scripts/imagery/embed_texture.py
```

Viewer profile migration:

```text
scripts/imagery/apply_phase3_code.py
```

Workflow:

```text
.github/workflows/build-damavand-imagery.yml
```

The imagery workflow:

1. validates/rebuilds the same Phase 2 terrain geometry
2. queries the public Sentinel-2 Collection 1 L2A catalogue for low-cloud scenes
3. composites true-colour B04/B03/B02 imagery with SCL masking
4. enforces at least 97% real source coverage
5. reprojects imagery onto the exact terrain bbox
6. authors the satellite image as the terrain PBR base-colour material
7. compresses the texture to WebP
8. applies Draco to the geometry
9. verifies the final GLB, imagery manifest and asset sizes
10. runs `npm run build` and `npm run lint`
11. publishes the generated model, preview, manifest and mountain viewer profile back to `iran-peaks`

Satellite-source attribution and usage notes are documented in `IMAGERY_ATTRIBUTION.md`.

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
2. ✅ **Real Terrain Pipeline** — production-density DEM → real terrain mesh → validated + compressed Damavand GLB
3. ✅ **Satellite Material & Lighting** — georeferenced Sentinel-2 texture, PBR terrain material and mountain daylight presentation
4. ✅ **Camera & Cinematic Experience** — intro flight, interruptible cinematic orbit, camera-state synchronization, canonical reset and reduced motion
5. **Routes & Mountain Intelligence** — GPX routes projected onto terrain
6. **Hotspots & Peak UI** — summit, shelters, landmarks, hazards and final product UI
7. **Production Hardening** — LOD, GPU texture compression/KTX2, caching, mobile GPU handling, dependency audit and tests

## Upstream

This repository began as a fork of `thebuggeddev/empire`, whose Three.js viewer architecture is being adapted for a mountain-specific experience. The upstream repository currently does not declare a license, so reuse/distribution of upstream code should not be assumed to grant commercial rights without permission from the original author.
