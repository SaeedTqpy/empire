# Terrain pipeline

Phase 2 generates the real Mount Damavand terrain geometry used by the Three.js viewer.

## Source

Elevation comes from Mapzen Terrain Tiles in the AWS Open Data bucket `elevation-tiles-prod` using the Terrarium encoding. No API key is required.

## Damavand build

The builder samples a 30 x 30 km square centered on `35.9513, 52.1097`, keeps a real 1:1 horizontal/vertical meter scale, and produces a 513 x 513 regular terrain grid (524,288 triangles).

```bash
python -m venv .venv-terrain
source .venv-terrain/bin/activate
pip install -r tools/terrain/requirements.txt
python tools/terrain/build_damavand.py
npx gltf-transform draco .cache/terrain/damavand-raw.glb public/models/damavand.glb --method edgebreaker
```

Generated metadata is written to `public/models/damavand.meta.json` and records the DEM source, bounding box, elevation range, grid size and generation timestamp.

Satellite imagery is intentionally not baked in here. Geometry is Phase 2; satellite material and rendering are Phase 3.
