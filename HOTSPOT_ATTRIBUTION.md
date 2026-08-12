# Damavand hotspot data

Phase 6 mountain markers reuse the geographic waypoint set already used to build the Phase 5 Damavand South Route.

## Reference coordinates

The following marker coordinates/elevations are taken from the Phase 5 waypoint configuration under `scripts/routes/damavand-south.json`:

- Goosfand Sara
- Seasonal River 2
- Sang-e Do Shakh
- Bargah Sevom New Hut
- First Ridge End (presented as the Upper Ridge high-altitude context marker)
- Damavand Summit

The route configuration credits OpenStreetMap contributors for trail geometry and the published Damavand GPS waypoint reference used to guide the corridor.

## Runtime placement

Reference elevations are descriptive metadata. Marker Y positions are not forced from those values. ViewerEngine transforms the marker latitude/longitude with the same terrain georeference used by Phase 5 routes and raycasts downward onto the actual Phase 2 DEM mesh. A small physical lift is then applied so the pin does not z-fight with the satellite-textured terrain.

## Safety

Markers are contextual visualization, not live mountain intelligence or navigation guidance. Shelter status, water availability, route condition, weather, access, hazards and rescue information can change and must be checked independently before a climb.
