# Self-hosted MapLibre terrain

The default Damavand viewer now uses MapLibre GL JS with a completely local raster stack. No Mapbox token is required and the default renderer makes no external tile request at runtime.

## Runtime stack

```text
MapLibre GL JS 6.3.0
├── local satellite XYZ
│   └── /tiles/maplibre/damavand/satellite/{z}/{x}/{y}.webp
├── local raster-dem XYZ
│   └── /tiles/maplibre/damavand/dem/{z}/{x}/{y}.png
│       └── Terrarium RGB elevation encoding
├── native GPU terrain
├── hillshade
├── South Route / imported GPX
└── WGS84 summit / shelter / landmark / hazard / water markers
```

The generated source manifest is `public/tiles/maplibre/damavand/manifest.json`.

## Current self-hosted source fidelity

The renderer and the source fidelity are intentionally documented separately.

- Satellite source: Copernicus Sentinel-2 true colour, **10 m native source resolution**.
- Terrain source: Skadi / SRTM 1 arc-second, roughly **30 m-class elevation sampling**.
- Source footprint: the existing **30 × 30 km** Damavand build extent.
- Tile pyramid: **z8 through z14**, 512 px XYZ tiles.
- Generated dataset: **414 satellite + 414 DEM tiles**.
- Current generated asset size: roughly **131.4 MB** before the small JSON manifest.
- Satellite tiles: WebP quality 92 from the lossless 4096 × 4096 authoring master.
- DEM tiles: lossless PNG using Mapzen Terrarium encoding.

MapLibre may continue zooming above source z14 by overscaling the highest available source tile. This improves interaction continuity but does **not** create new observed terrain or imagery detail.

## Why this architecture

The old viewer used pre-authored GLB / 3D Tiles geometry. That path is still available, but native MapLibre terrain is now the primary presentation because it gives the same class of interaction as modern map terrain renderers:

- continuous zoom, pitch and bearing
- camera-driven tile loading
- native raster-dem terrain on the GPU
- seamless raster imagery streaming
- hillshade blended with satellite imagery
- no monolithic maximum-detail terrain mesh permanently resident
- straightforward replacement of the source pyramid when better licensed data becomes available

This is a renderer upgrade, not a claim that Sentinel-2 or SRTM have become more detailed.

## Source generation

The reproducible build is:

```bash
python scripts/imagery/build_sentinel_texture.py \
  --config scripts/imagery/damavand.json \
  --texture .build/maplibre/damavand-sentinel-master.png \
  --preview .build/maplibre/damavand-sentinel-preview.webp \
  --manifest .build/maplibre/damavand.imagery.json

python scripts/maplibre/build_damavand_local_tiles.py \
  --terrain-config scripts/terrain/damavand.json \
  --terrain-manifest public/models/damavand.terrain.json \
  --imagery-manifest .build/maplibre/damavand.imagery.json \
  --imagery-master .build/maplibre/damavand-sentinel-master.png \
  --output-dir public/tiles/maplibre/damavand \
  --cache-dir .terrain-cache \
  --min-zoom 8 \
  --max-zoom 14 \
  --tile-size 512 \
  --webp-quality 92 \
  --clean

python scripts/maplibre/validate_damavand_local_tiles.py \
  --dataset public/tiles/maplibre/damavand
```

GitHub Actions runs the same process in `.github/workflows/build-maplibre-self-hosted.yml`, validates the summit DEM and imagery tile, applies a 250 MiB dataset gate, runs the production TypeScript/Vite build and ESLint, and only then publishes generated assets.

## DEM edge policy

At low XYZ zooms, one web tile is geographically much larger than the 30 km observed source rectangle. Pixels of those edge tiles that lie outside the declared Damavand bbox are clamped to the nearest bbox edge. This avoids downloading unrelated elevation degrees while keeping a valid complete RGB tile. MapLibre's source `bounds` remains the authoritative observed terrain extent.

## Runtime switches

Default self-hosted MapLibre renderer:

```text
/
```

Previous Three.js / 3D Tiles renderer for A/B comparison:

```text
/?renderer=legacy
```

`?renderer=three` and the older `?streaming=0` switch also select the legacy path.

## What is deliberately not bundled

The Phase 8 Vantor / Esri Wayback source around the summit had substantially higher imagery resolution, but its service imagery is not copied into this self-hosted dataset. The local MapLibre mode uses only data we can publish under the existing open-source data contracts.

A future true source-quality upgrade should replace the local pyramid with imagery and elevation/photogrammetry that explicitly permit self-hosting. The MapLibre viewer does not need to be redesigned for that upgrade; the tile URLs and manifest can remain the same product boundary.
