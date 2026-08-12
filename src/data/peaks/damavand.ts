import type { Peak } from "@/types/peak";

/**
 * Damavand is the reference peak for the terrain + imagery pipeline.
 *
 * Phase 2 created the real 30×30 km DEM mesh. Phase 3 keeps that geometry
 * intact and adds a georeferenced Sentinel-2 true-colour material plus a
 * mountain daylight scene profile.
 */
export const damavand: Peak = {
  id: "damavand",
  name: "Mount Damavand",
  localName: "دماوند",
  subtitle: "Iran's highest mountain",
  description:
    "Explore Mount Damavand as a real 30 km terrain model, textured with georeferenced Copernicus Sentinel-2 imagery and ready for routes, shelters and mountain landmarks.",

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
  modelPath: "/models/damavand.glb?v=phase3-sentinel-20260812",
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
    { label: "Imagery", value: "Sentinel-2 true colour", icon: "status" },
  ],

  // Geo-aware hotspots are added once route projection is introduced.
  hotspots: [],

  media: {
    thumbnail: "/img/peaks/damavand-sentinel.webp?v=phase3-sentinel-20260812",
    hero: "/img/peaks/damavand-sentinel.webp?v=phase3-sentinel-20260812",
  },

  keywords: ["damavand", "دماوند", "iran", "alborz", "mountain", "volcano", "peak", "terrain", "dem", "sentinel-2"],
};
