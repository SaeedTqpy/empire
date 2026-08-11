# Terrain data attribution

The Phase 2 Damavand terrain mesh is generated from the **AWS Open Data Terrain Tiles** dataset (`elevation-tiles-prod`), using its Skadi HGT elevation tiles.

For the Damavand region, the underlying global elevation source is SRTM. Credit used by this project:

> SRTM terrain data courtesy of the U.S. Geological Survey. Terrain tiles distributed through the AWS Open Data Terrain Tiles dataset / Mapzen-Tilezen terrain pipeline.

The generated `public/models/damavand.terrain.json` records the exact source tile URLs used for each build.

Important: elevation models are suitable for visualization and planning, but this product must not represent the DEM as a substitute for field navigation, authoritative surveying or safety-critical mountaineering decisions.
