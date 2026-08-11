# Iran 3D Peaks

Interactive 3D mountain atlas for Iran, starting with **Mount Damavand**.

The product direction is a real-terrain experience: DEM-derived mountain geometry, satellite imagery, cinematic camera movement, climbing routes, shelters and mountain landmarks.

## Current status — Phase 2 complete

The product domain and the first real mountain terrain are now in place.

- `Peak` domain model lives under `src/types/peak.ts`
- Damavand is the only product dataset rendered at runtime
- peak library and peak information panel replace empire-facing UI
- the Three.js viewer now loads `/models/damavand.glb`
- Damavand geometry is generated from real Skadi/SRTM elevation data
- the represented area is 30 × 30 km around the summit
- source DEM tiles are 3601 × 3601 HGT samples
- the generated top surface is 257 × 257 samples: 66,049 vertices / 131,072 terrain triangles
- a closed terrain skirt prevents paper-thin edges at low camera angles
- terrain uses real 1:1 physical vertical proportion — no elevation exaggeration
- UV coordinates are already authored for the satellite-texture phase
- the final GLB uses Draco compression and is about 228 KB before satellite imagery
- exact source tiles, bounds and elevation statistics are recorded in `public/models/damavand.terrain.json`
- real satellite texture is deliberately deferred to Phase 3

The DEM build sampled roughly **887 m to 5,593 m** inside the 30 km square. The product metadata keeps the canonical summit elevation separately from the raster sample, rather than pretending a ~30 m DEM cell is a survey measurement.

## Architecture

```text
Peak domain
   ↓
src/data/peaks/damavand.ts
   ↓
Peak UI
   ├─ PeakLibrary
   └─ PeakInfoPanel
   ↓
peak-viewer-adapter.ts
   ↓
Three.js ViewerEngine
   ↓
public/models/damavand.glb
   ↑
Skadi/SRTM HGT → crop/sample → terrain mesh → validation → Draco
```

The terrain asset is reproducible. Its source configuration is:

```text
scripts/terrain/damavand.json
```

and the builder is:

```text
scripts/terrain/build_peak_terrain.py
```

The generated model coordinate contract is intentionally geographic-friendly:

```text
+X = east
+Y = elevation
+Z = north
UV  = west→east / south→north
units = metres before ViewerEngine presentation normalization
```

That contract is the basis for projecting GPX routes and geographic hotspots onto the same mesh in later phases.

## Terrain pipeline

The repository includes a dedicated GitHub Actions workflow:

```text
.github/workflows/build-damavand-terrain.yml
```

It:

1. downloads the required public Skadi HGT tiles
2. bilinearly samples a 30 × 30 km square around Damavand
3. generates terrain geometry and edge skirt
4. validates footprint, relief, vertices and triangle counts
5. applies Draco mesh compression with glTF-Transform
6. inspects the final glTF structure
7. commits `damavand.glb` and its manifest back to `iran-peaks`

For a local raw build:

```bash
python3 -m pip install -r scripts/terrain/requirements.txt
python3 scripts/terrain/build_peak_terrain.py \
  --config scripts/terrain/damavand.json \
  --output public/models/damavand.raw.glb \
  --manifest public/models/damavand.terrain.json

python3 scripts/terrain/validate_terrain.py \
  --model public/models/damavand.raw.glb \
  --manifest public/models/damavand.terrain.json

npx gltf-transform draco \
  public/models/damavand.raw.glb \
  public/models/damavand.glb \
  --method edgebreaker
```

Terrain-source attribution is documented in `TERRAIN_ATTRIBUTION.md` and the generated manifest records the exact source tile URLs used for the build.

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
2. ✅ **Real Terrain Pipeline** — DEM → real terrain mesh → validated + compressed Damavand GLB
3. **Satellite Material & Lighting** — geographically aligned satellite texture and mountain-specific lighting
4. **Camera & Cinematic Experience** — intro flight, orbit, camera constraints and presets
5. **Routes & Mountain Intelligence** — GPX routes projected onto terrain
6. **Hotspots & Peak UI** — summit, shelters, landmarks, hazards and final product UI
7. **Production Hardening** — LOD, texture compression, caching, mobile GPU handling and tests

## Upstream

This repository began as a fork of `thebuggeddev/empire`, whose Three.js viewer architecture is being adapted for a mountain-specific experience. The upstream repository currently does not declare a license, so reuse/distribution of upstream code should not be assumed to grant commercial rights without permission from the original author.
