# Satellite imagery attribution

Phase 3+ textures for Iran 3D Peaks are generated from **Copernicus Sentinel-2** surface-reflectance imagery.

Required public notice used by the application:

> Contains modified Copernicus Sentinel data 2026

## Damavand pipeline

The build searches the public Sentinel-2 Collection 1 Level-2A catalogue exposed through Earth Search / AWS Open Data, selects low-cloud observations intersecting the exact Phase 2 terrain bounding box, and composes true-colour imagery from:

- B04 — red
- B03 — green
- B02 — blue

Cloud, cloud-shadow and invalid classes are masked from the Sentinel-2 Scene Classification Layer (SCL) when available. The resulting image is reprojected onto the exact WGS84 terrain bounding box before it is embedded into the terrain GLB.

## Ultra-detail texture profile

The Damavand terrain now uses a **4096 × 4096** satellite authoring texture for the 30 km terrain footprint. That is roughly **7.3 m per output texel**, which is slightly finer than the nominal 10 m Sentinel-2 RGB source resolution and therefore preserves the available source detail without intentionally throwing pixels away.

The authoring master is written as **lossless PNG**. The browser delivery texture is then encoded once as high-quality WebP before Draco geometry compression. This avoids the previous JPEG → WebP double-lossy path.

The viewer also enables closer camera inspection, higher render-resolution budgets, mipmapped trilinear texture filtering and device-aware anisotropic filtering so the higher-resolution texture remains sharper at oblique viewing angles.

This pipeline deliberately does **not** use AI or synthetic super-resolution to invent geographic detail. An 8K or 16K upscale of a 10 m Sentinel-2 source would increase GPU/download cost without creating new observed ground detail. A future higher-resolution imagery source can plug into the same georeferenced UV pipeline when licensing and coverage allow it.

The generated file:

`public/models/damavand.imagery.json`

records the exact Sentinel scene identifiers, acquisition times, cloud-cover metadata, source asset keys, represented bounding box, output dimensions, coverage, approximate output ground resolution, delivery format and processing settings used by the build.

Earth Search and remote Cloud Optimized GeoTIFFs are **build-time dependencies only**. The production viewer does not call the catalogue or satellite data service; it loads the generated local GLB and preview asset.

Satellite imagery and elevation models are visualization sources. They must not be represented as a substitute for authoritative maps, current field conditions, route verification or safety-critical mountain navigation.
