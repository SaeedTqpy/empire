# Damavand Digital Twin — Phase 8 source contract

Phase 8 increases **observed visual imagery detail** without inventing geographic detail. It does not claim sub-meter terrain geometry.

## What changed

The Phase 7 terrain hierarchy remains the stable self-hosted base:

- 30 × 30 km Damavand terrain footprint
- Skadi/SRTM elevation source, roughly 30 m-class source sampling
- Copernicus Sentinel-2 true-colour imagery as the complete self-hosted fallback
- 3D Tiles 1.1 L0/L1/L2 spatial streaming

Phase 8 adds an optional runtime-only high-resolution imagery overlay over the part of Damavand for which a matching source footprint was validated.

## Validated high-detail source

The source discovery pipeline queries the official metadata item for **World Imagery (Wayback 2026-03-26)** at the Damavand summit.

Validated best record:

| Field | Value |
| --- | --- |
| Metadata item | `eafaa19cb03a4bcba592ef12fb6e14e5` |
| Metadata layer | `World_Imagery_Metadata_2026_r03/MapServer/5` |
| Feature OBJECTID | `3154394` |
| Provider | Vantor |
| Product | Vivid |
| Block | `Vivid_Standard_IR02_25Q3` |
| Source date | 2025-06-22 |
| Observed source resolution (`SRC_RES`) | **0.34 m** |
| Sampled/delivered resolution (`SAMP_RES`) | **0.6 m** |
| Source accuracy field (`SRC_ACC`) | 5 |
| Minimum map level | 12 |
| Maximum validated map level | **18** |
| Release | `Raster Basemaps 2025.R10` |

The runtime is deliberately capped at **z18**. Higher service zoom levels are not treated as additional observed detail for this Damavand source.

## Coverage

The matching metadata feature is one irregular polygon with 5,045 vertices and contains the Damavand summit.

Its WGS84 bounds are:

```text
west  52.0312477
south 35.6338357
east  52.1723191
north 35.9580380
```

The bounds intersect approximately **22.2212%** of the current 30 × 30 km Damavand terrain bounding box. This is therefore a **summit / south-side high-detail region**, not a claim that the entire 30 km terrain has 0.6 m imagery.

Outside the validated high-detail bounds, the existing Sentinel-2 material remains the visual fallback.

## Exact runtime snapshot

Runtime imagery is bound to the public ArcGIS Wayback item:

```text
b4c5c1b59c4141c5b503335b5baa2df4
World Imagery (Wayback 2026-03-26)
```

The item-provided tile template is used at runtime. A CI probe validated the summit tile at z18 as an HTTP 200 JPEG response with cross-origin access enabled. A second stale WMTS-info tile identifier returned 404 and is intentionally not used.

The VHR imagery is **not copied into `public/`, not baked into GLBs, and not published as offline tiles**. `scripts/digital_twin/validate_phase8_contract.py` fails if a Wayback/Vantor/Vivid asset is accidentally bundled under `public/`.

Attribution shown by the viewer:

```text
Esri, Vantor, Earthstar Geographics, and the GIS User Community
```

The Copernicus attribution remains visible because Sentinel-2 is still the complete fallback.

Before commercial deployment, review the current ArcGIS/Esri service terms for the intended distribution model. The implementation intentionally avoids offline tile export or redistribution.

## Geographic alignment

The terrain pipeline uses:

```text
X = east metres
Z = north metres
```

around the Damavand centre. Phase 8 recovers longitude/latitude from every streamed terrain vertex using the same Earth-radius coordinate contract as the DEM builder, then applies the image overlay's EPSG:3857 projection per vertex.

This avoids using one affine local-to-WebMercator matrix across the 30 km model, which would be too imprecise for sub-meter imagery.

The overlay retains `3d-tiles-renderer`'s image tile fetching, cache, material composition and virtual leaf splitting, while only replacing the local-terrain geographic projection step.

## Failure behavior

High-detail imagery is an enhancement, never a hard dependency:

```text
VHR tile succeeds   → Vantor/Esri detail draped over the validated region
VHR tile fails      → Sentinel-2 terrain remains visible
3D Tiles fail       → canonical Damavand GLB fallback remains available
```

Debug / comparison switches:

```text
?detail=0     disable Phase 8 VHR overlay, keep 3D Tiles
?streaming=0  disable spatial streaming and use canonical GLB path
```

## Reproducible source gates

```text
scripts/digital_twin/probe_esri_world_imagery.py
scripts/digital_twin/probe_esri_wayback_runtime.py
scripts/digital_twin/probe_esri_wayback_tile.py
scripts/digital_twin/validate_phase8_contract.py
.github/workflows/probe-phase8-esri-imagery.yml
.github/workflows/probe-phase8-esri-runtime.yml
.github/workflows/validate-phase8-digital-twin.yml
```

Other discovery probes are kept for auditability:

- OpenAerialMap returned no imagery in the current Damavand bbox at probe time.
- NASA/JSC exposed a GeoTIFF action for `ISS072-E-265`, but its GeoTIFF CGI repeatedly returned HTTP 502 during the probe, so it was not used and no resolution claim was inferred from the JPEG dimensions.

## Current limitation

Phase 8 is a major **imagery** fidelity upgrade around the summit/south-side source footprint. The elevation surface is still SRTM-derived, so rocks, gullies and micro-relief smaller than the DEM sampling cannot become physically correct 3D geometry merely because the image is sharper.

A future geometry upgrade can plug photogrammetry, LiDAR or another licensed sub-meter elevation/mesh source into the existing spatial hierarchy without changing routes, hotspots, camera semantics or the product-level Peak model.
