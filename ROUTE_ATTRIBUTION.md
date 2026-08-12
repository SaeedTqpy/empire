# Route data attribution

Phase 5 adds geospatial route visualization to Iran 3D Peaks.

## Built-in Damavand South reference

The generated South Route uses OpenStreetMap trail geometry where a connected trail graph is available. The intended corridor is selected with published Damavand GPS landmark coordinates so unrelated nearby trails are not chosen accidentally.

OpenStreetMap data is © OpenStreetMap contributors and is available under the Open Data Commons Open Database License (ODbL). See the OpenStreetMap copyright and licence page for attribution and share-alike requirements.

Reference landmark names and coordinates are used as factual control points from the public “Damavand GPS Waypoints” page maintained at damawand.de. The generated route does not copy a proprietary GPX track.

The terrain surface used to clamp route geometry comes from the same SRTM/Skadi DEM pipeline documented in `TERRAIN_ATTRIBUTION.md`.

## Safety

The built-in route is a reference visualization, not a turn-by-turn navigation product and not a substitute for current local route information, weather, mountain conditions, permits, guides, maps, or emergency planning.

Imported GPX files are parsed locally in the browser and projected onto the current DEM. They are not uploaded by the Phase 5 implementation.
