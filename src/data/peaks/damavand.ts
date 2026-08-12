import type { Peak } from "@/types/peak";
import { damavandHotspots } from "./damavand-hotspots";

/**
 * Damavand is the reference peak for the terrain + imagery + route pipeline.
 *
 * Phase 2 created the real 30×30 km DEM mesh. Phase 3 added georeferenced
 * Sentinel-2 true-colour imagery. Phase 5 projects climbing routes against the
 * exact same terrain coordinate contract.
 */
export const damavand: Peak = {
  id: "damavand",
  name: "Mount Damavand",
  localName: "دماوند",
  subtitle: "Iran's highest mountain",
  description:
    "Explore Mount Damavand as a real 30 km terrain model with Sentinel-2 imagery, 3D climbing routes and terrain-aware mountain intelligence.",

  elevationM: 5610,
  prominenceM: 4667,
  range: "Alborz",
  province: "Mazandaran",
  country: "Iran",
  coordinates: {
    lat: 35.9513,
    lon: 52.1097,
  },

  // Keep a version token on generated assets. Vite serves files from /public
  // at stable paths, and browsers can otherwise keep an older GLB after a
  // terrain/imagery rebuild because the filename itself did not change.
  modelPath: "/models/damavand.glb?v=ultra4k-sentinel-20260812",
  terrain: {
    manifestPath: "/models/damavand.terrain.json",
    imageryManifestPath: "/models/damavand.imagery.json",
    imageryAttribution: "Contains modified Copernicus Sentinel data 2026",
    extentKm: 30,
    gridSize: 513,
    verticalExaggeration: 1.0,
    sourceLabel: "SRTM terrain + Copernicus Sentinel-2 imagery",
  },
  tint: "#6f91a4",
  camera: {
    azimuth: -36,
    elevation: 31,
    dist: 1.0,
    targetY: 0.22,
  },

  facts: [
    { label: "Elevation", value: "5,610 m", icon: "elevation" },
    { label: "Mountain range", value: "Alborz", icon: "range" },
    { label: "Location", value: "Mazandaran, Iran", icon: "location" },
    { label: "Terrain", value: "30 km real DEM", icon: "type" },
    { label: "Routes", value: "3D + GPX import", icon: "status" },
  ],

  // Phase 6 markers use WGS84 coordinates and are raycast onto the DEM.
  hotspots: damavandHotspots,

  routes: [
    {
      id: "south-reference",
      name: "South Route",
      localName: "مسیر جنوبی",
      description: "Reference visualization of the classic south-side ascent from Goosfand Sara through Bargah Sevom toward the summit.",
      dataPath: "/routes/damavand-south.json?v=phase5-20260812",
      color: "#ef5b32",
      sourceLabel: "South route reference",
      attribution: "© OpenStreetMap contributors · landmark controls from Damavand GPS Waypoints",
      safetyNote: "Reference visualization only — not turn-by-turn navigation. Verify current mountain conditions and your navigation source before climbing.",
      referenceMetrics: {
        distanceKm: 8.0,
        ascentM: 2630,
      },
    },
  ],

  media: {
    thumbnail: "/img/peaks/damavand-sentinel.webp?v=phase3-sentinel-20260812",
    hero: "/img/peaks/damavand-sentinel.webp?v=phase3-sentinel-20260812",
  },

  keywords: ["damavand", "دماوند", "iran", "alborz", "mountain", "volcano", "peak", "terrain", "dem", "sentinel-2", "gpx", "route"],
};
