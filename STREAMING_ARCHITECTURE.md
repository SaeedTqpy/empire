# Phase 7 — Spatial terrain streaming

Iran 3D Peaks no longer treats maximum-detail terrain as one permanently resident visual GLB. Phase 7 introduces a 3D Tiles 1.1 spatial quadtree while preserving the existing mountain coordinate contract and product interaction layers.

## Runtime layout

```text
ViewerEngine
├── hidden interaction proxy (whole 30 km terrain)
│   ├── route projection / GPX raycasts
│   ├── geo-hotspot projection
│   └── automatic fallback if the tileset cannot load
└── TerrainTilesStreamer
    └── 3D Tiles REPLACE quadtree
        ├── L0: 1 whole-mountain tile
        ├── L1: 4 quadrant tiles
        └── L2: 16 near-field tiles
```

The proxy and streamed tiles use the same local metric frame:

```text
+X = east
+Y = elevation above the shared build base
+Z = north
```

`ViewerEngine` applies the same normalization transform to both layers. Routes and markers therefore do not need to know which visual LOD happens to be resident.

## Detail profile

| LOD | Tiles | Grid per tile | Texture per tile | Approx terrain spacing | Approx imagery texel |
| --- | ---: | ---: | ---: | ---: | ---: |
| L0 | 1 | 129×129 | 512×512 | 234.4 m | 58.6 m |
| L1 | 4 | 129×129 | 512×512 | 117.2 m | 29.3 m |
| L2 | 16 | 257×257 | 1024×1024 | 29.3 m | 7.3 m |

The L2 leaves preserve the same useful source detail as the previous 1025×1025 / 4096×4096 monolithic build, but detail is spatially partitioned so only camera-relevant pieces need to be loaded.

The source is still SRTM terrain plus Copernicus Sentinel-2 imagery. Phase 7 is an architecture upgrade, not a claim of new observed ground resolution. Phase 8 can replace leaf content with commercial elevation, native very-high-resolution imagery, photogrammetry or LiDAR without changing the viewer boundary.

## Selection and fallback

The runtime uses `3d-tiles-renderer` with camera screen-space error selection and `REPLACE` refinement. Ancestors remain available while children are loading, then higher-detail children replace them.

The full canonical `/models/damavand.glb` remains a product fallback. The streaming path also has a lightweight interaction model under the tileset directory. If the root tileset cannot load, the interaction model stays visible rather than leaving the stage empty.

For debugging or comparison, append:

```text
?streaming=0
```

to force the canonical single-GLB path.

## Memory policy

The streaming adapter adjusts request concurrency and cache budgets from `navigator.deviceMemory` when available. Constrained devices target a larger screen-space error and smaller LRU byte budget. High-memory devices retain a tighter target and larger cache. This is deliberately a runtime policy, not baked into the tile content.

## Build outputs

```text
public/tiles/damavand/phase7-v1/
├── tileset.json
├── streaming.manifest.json
├── interaction.glb
├── l0/
├── l1/
└── l2/
```

The build samples the canonical 1025×1025 DEM once, derives every LOD from that same sampled grid, crops imagery from the same georeferenced 4096×4096 lossless master, then WebP-compresses textures and Draco-compresses geometry.

`validate_streaming.py` verifies the 1/4/16 hierarchy, unique content URIs, REPLACE refinement, leaf error contract, interaction proxy and byte accounting before runtime code and generated assets are published.
