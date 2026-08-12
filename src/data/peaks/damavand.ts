import type { Peak } from "@/types/peak";
import { damavandHotspots } from "./damavand-hotspots";

/**
 * Damavand is the reference peak for the terrain + imagery + route pipeline.
 *
 * The self-hosted terrain remains SRTM-derived and the complete visual fallback
 * remains Sentinel-2. Phase 8 adds a runtime-only VHR drape over the validated
 * Vantor/Esri footprint around the summit and south side; it does not pretend
 * that the underlying elevation model is sub-meter geometry.
 */
export const damavand: Peak = {
  id: "damavand",
  name: "Mount Damavand",
  localName: "دماوند",
  subtitle: "Iran's highest mountain",
  description:
    "Explore Mount Damavand as a real 30 km terrain model with streamed high-detail summit imagery, 3D climbing routes and terrain-aware mountain intelligence.",

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
  modelPath: "/models/damavand.glb?v=extreme1025-4k-20260812",
  terrain: {
    manifestPath: "/models/damavand.terrain.json",
    imageryManifestPath: "/models/damavand.imagery.json",
    imageryAttribution: "Contains modified Copernicus Sentinel data 2026",
    extentKm: 30,
    gridSize: 1025,
    verticalExaggeration: 1.0,
    sourceLabel: "SRTM terrain + Copernicus Sentinel-2 imagery",
    streaming: {
      enabled: true,
      tilesetPath: "/tiles/damavand/phase7-v1/tileset.json",
      interactionModelPath: "/tiles/damavand/phase7-v1/interaction.glb",
      datasetVersion: "phase8-vhr-wayback-20260326",
      targetSSE: 2.5,
      maxDepth: 2,
      detailImagery: {
        enabled: true,
        provider: "esri-wayback",
        itemId: "b4c5c1b59c4141c5b503335b5baa2df4",
        tileTemplate:
          "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/22869/{level}/{row}/{col}",
        maxZoom: 18,
        observedResolutionM: 0.34,
        sampledResolutionM: 0.6,
        sourceDate: "2025-06-22",
        sourceLabel: "Vantor Vivid · Esri Wayback 2026-03-26",
        attribution: "Esri, Vantor, Earthstar Geographics, and the GIS User Community",
        // Exact WGS84 bounds of metadata feature OBJECTID 3154394. The source
        // itself is an irregular polygon; this bounds gate prevents high-zoom
        // requests outside the validated summit/south-side source block.
        coverageBboxWgs84: [52.0312477, 35.6338357, 52.1723191, 35.958038],
        centerLat: 35.9513,
        centerLon: 52.1097,
      },
    },
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
    { label: "Detail imagery", value: "0.6 m summit coverage", icon: "status" },
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
    thumbnail: "/img/peaks/damavand-sentinel.webp?v=extreme1025-4k-20260812",
    hero: "/img/peaks/damavand-sentinel.webp?v=extreme1025-4k-20260812",
  },

  keywords: ["damavand", "دماوند", "iran", "alborz", "mountain", "volcano", "peak", "terrain", "dem", "sentinel-2", "vhr", "vantor", "gpx", "route"],
};