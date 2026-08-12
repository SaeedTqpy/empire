/** Spatial terrain-streaming contracts. */
export interface TerrainDetailImageryConfig {
  enabled: boolean;
  provider: "esri-wayback";
  /** Exact public ArcGIS Wayback item whose source metadata was validated. */
  itemId: string;
  /** Exact XYZ-compatible public runtime URL; never persisted as offline tiles. */
  tileTemplate: string;
  /** Inclusive highest source zoom that is backed by observed source detail. */
  maxZoom: number;
  /** Native/observed source resolution from the matching metadata record. */
  observedResolutionM: number;
  /** Resolution delivered by the validated runtime tile level. */
  sampledResolutionM: number;
  sourceDate: string;
  sourceLabel: string;
  attribution: string;
  /** Local terrain georeference used to derive exact lon/lat per vertex. */
  centerLat: number;
  centerLon: number;
}

export interface TerrainStreamingConfig {
  enabled: boolean;
  tilesetPath: string;
  /** Lightweight whole-mountain mesh retained for routes, hotspots and fallback. */
  interactionModelPath: string;
  datasetVersion: string;
  /** Screen-space error target in CSS/render pixels. Lower means more detail. */
  targetSSE: number;
  maxDepth: number;
  /** Optional Phase 8 runtime-only high-resolution imagery drape. */
  detailImagery?: TerrainDetailImageryConfig;
}

export type TerrainStreamingMode = "3d-tiles" | "fallback";
export type DetailImageryStatus = "off" | "initializing" | "active" | "error";

export interface TerrainStreamingStats {
  mode: TerrainStreamingMode;
  loading: boolean;
  progress: number;
  visibleTiles: number;
  activeTiles: number;
  loadedTiles: number;
  visibleDepth: number;
  maxDepth: number;
  failed: boolean;
  detailImageryStatus?: DetailImageryStatus;
  detailImageryLabel?: string;
  detailImageryResolutionM?: number;
}
