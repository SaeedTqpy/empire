import type { Peak } from "@/types/peak";

/**
 * Damavand is the reference peak for the terrain pipeline.
 *
 * Phase 2 replaces the architectural placeholder with a real 30×30 km DEM
 * mesh generated from public Skadi/SRTM elevation tiles. Satellite imagery is
 * deliberately deferred to Phase 3 so geometry can be validated on its own.
 */
export const damavand: Peak = {
  id: "damavand",
  name: "Mount Damavand",
  localName: "دماوند",
  subtitle: "Iran's highest mountain",
  description:
    "An interactive 3D exploration of Mount Damavand, built from real elevation data and designed to layer climbing routes, shelters, landmarks and satellite imagery onto the same geographic terrain model.",

  elevationM: 5610,
  prominenceM: 4667,
  range: "Alborz",
  province: "Mazandaran",
  country: "Iran",
  coordinates: {
    lat: 35.9513,
    lon: 52.1097,
  },

  modelPath: "/models/damavand.glb",
  terrain: {
    manifestPath: "/models/damavand.terrain.json",
    extentKm: 30,
    gridSize: 257,
    verticalExaggeration: 1.0,
    sourceLabel: "Skadi / SRTM via AWS Open Data Terrain Tiles",
  },
  tint: "#78909c",
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
    { label: "Vertical scale", value: "1:1 physical ratio", icon: "status" },
  ],

  // Geo-aware hotspots are added once route projection is introduced.
  hotspots: [],

  // Replaced by satellite/hero assets in Phase 3.
  media: {
    thumbnail: "/img/peaks/damavand-placeholder.svg",
    hero: "/img/peaks/damavand-placeholder.svg",
  },

  keywords: ["damavand", "دماوند", "iran", "alborz", "mountain", "volcano", "peak", "terrain", "dem"],
};
