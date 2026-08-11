/** Iran 3D Peaks — domain contracts.
 *
 * The application is peak-driven. Adding another mountain should require data
 * and assets, not changes to the viewer or the page shell.
 */

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
 * Phase 1 hotspot coordinates are normalized model-space anchors so the
 * existing Three.js engine can keep working while the real DEM model is being
 * built. In the terrain phase this becomes a geo-aware lat/lon/elevation
 * contract and is projected onto the mountain mesh.
 */
export interface PeakHotspot {
  id: string;
  title: string;
  short: string;
  detail: string;
  category: PeakHotspotCategory;
  anchor: Vec3;
  focus?: number;
}

export interface PeakMedia {
  thumbnail: string;
  hero: string;
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

  /** GLB used by the Three.js viewer. Phase 1 uses a placeholder model. */
  modelPath: string;
  tint: string;
  camera: PeakCameraPreset;

  facts: PeakFact[];
  hotspots: PeakHotspot[];
  media: PeakMedia;
  keywords: string[];
}
