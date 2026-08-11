import type { Peak } from "@/types/peak";

/**
 * Phase 1 Damavand data.
 *
 * The real terrain GLB and satellite imagery arrive in phases 2–3. Until then
 * the original Persian model is intentionally used as a rendering placeholder
 * so we can validate the peak-domain wiring without touching ViewerEngine.
 */
export const damavand: Peak = {
  id: "damavand",
  name: "Mount Damavand",
  localName: "دماوند",
  subtitle: "Iran's highest mountain",
  description:
    "An interactive 3D exploration of Mount Damavand, designed to combine real terrain, climbing routes, shelters and mountain landmarks in a single peak-focused experience.",

  elevationM: 5610,
  prominenceM: 4667,
  range: "Alborz",
  province: "Mazandaran",
  country: "Iran",
  coordinates: {
    lat: 35.9513,
    lon: 52.1097,
  },

  // Phase 1 placeholder. Replaced by /models/damavand.glb in phase 2.
  modelPath: "/models/persian.glb",
  tint: "#78909c",
  camera: {
    azimuth: -36,
    elevation: 34,
    dist: 1.0,
    targetY: 0.32,
  },

  facts: [
    { label: "Elevation", value: "5,610 m", icon: "elevation" },
    { label: "Mountain range", value: "Alborz", icon: "range" },
    { label: "Location", value: "Mazandaran, Iran", icon: "location" },
    { label: "Mountain type", value: "Stratovolcano", icon: "type" },
    { label: "Experience", value: "3D terrain atlas", icon: "status" },
  ],

  // Real geo-aware hotspots are added after the DEM terrain is in place.
  hotspots: [],

  // Temporary assets prevent broken images during the foundation migration.
  // These are replaced by Damavand satellite/hero assets in phase 3.
  media: {
    thumbnail: "/img/persian/thumbnail.webp",
    hero: "/img/persian/hero.webp",
  },

  keywords: ["damavand", "دماوند", "iran", "alborz", "mountain", "volcano", "peak"],
};
