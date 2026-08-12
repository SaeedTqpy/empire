/** Phase 7 spatial terrain-streaming contracts. */
export interface TerrainStreamingConfig {
  enabled: boolean;
  tilesetPath: string;
  /** Lightweight whole-mountain mesh retained for routes, hotspots and fallback. */
  interactionModelPath: string;
  datasetVersion: string;
  /** Screen-space error target in CSS/render pixels. Lower means more detail. */
  targetSSE: number;
  maxDepth: number;
}

export type TerrainStreamingMode = "3d-tiles" | "fallback";

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
}
