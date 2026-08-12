/** Iran 3D Peaks — domain contracts.
 *
 * The application is peak-driven. Adding another mountain should require data
 * and assets, not changes to the viewer or the page shell.
 */

import type { PeakRoute } from "./route";

export type Vec3 = [number, number, number];

export interface PeakCoordinates {
  lat: number;
  lon: number;
}

export interface PeakCameraPreset {
  /** azimuth in degrees (0 = +Z front, positive orbits right) */
  azimuth: number;
  /** elevation in degrees above horizon */
  elevation: number;
  /** distance multiplier relative to auto-framing */
  dist: number;
  /** vertical framing bias: fraction of model height for look-at */
  targetY: number;
}

export type PeakFactIcon = "elevation" | "range" | "location" | "type" | "status";

export interface PeakFact {
  label: string;
  value: string;
  icon: PeakFactIcon;
}

export type PeakHotspotCategory = "summit" | "shelter" | "landmark" | "hazard" | "water" | "route";

/**
 * Hotspot anchors remain normalized model-space coordinates until the route
 * and geo-projection phase. The terrain manifest added in Phase 2 provides the
 * geographic transform needed to move these to lat/lon/elevation later.
 */
export interface PeakHotspot {
  id: string;
  title: string;
  short: string;
  detail: string;
  category: PeakHotspotCategory;
  /** Optional legacy normalized fallback for non-georeferenced models. */
  anchor?: Vec3;
  /** Preferred Phase 6 placement: WGS84 lat/lon raycast onto the terrain. */
  coordinates?: PeakCoordinates;
  /** Reference metadata only; rendered Y comes from the DEM surface. */
  elevationM?: number;
  sourceLabel?: string;
  focus?: number;
}

export interface PeakMedia {
  thumbnail: string;
  hero: string;
}

export interface PeakTerrain {
  /** Build manifest containing bbox, source tiles and coordinate contract. */
  manifestPath: string;
  /** Phase 3 imagery manifest containing scene IDs and processing metadata. */
  imageryManifestPath?: string;
  /** Public attribution required by the imagery source. */
  imageryAttribution?: string;
  /** Square source area represented by the terrain mesh. */
  extentKm: number;
  /** Samples on each axis before mesh compression. */
  gridSize: number;
  /** 1.0 means elevations are rendered in their real physical proportion. */
  verticalExaggeration: number;
  sourceLabel: string;
}

export interface Peak {
  id: string;
  name: string;
  localName: string;
  subtitle: string;
  description: string;

  elevationM: number;
  prominenceM?: number;
  range: string;
  province: string;
  country: string;
  coordinates: PeakCoordinates;

  /** GLB used by the Three.js viewer. */
  modelPath: string;
  terrain: PeakTerrain;
  tint: string;
  camera: PeakCameraPreset;

  facts: PeakFact[];
  hotspots: PeakHotspot[];
  routes: PeakRoute[];
  media: PeakMedia;
  keywords: string[];
}
