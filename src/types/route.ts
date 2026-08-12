export interface GeoRoutePoint {
  lat: number;
  lon: number;
  elevationM?: number;
  name?: string;
}

export interface RouteMetrics {
  distanceKm: number;
  ascentM: number;
  descentM: number;
  minElevationM: number;
  maxElevationM: number;
  sampledPoints: number;
}

export interface PeakRouteReferenceMetrics {
  distanceKm?: number;
  ascentM?: number;
}

export interface PeakRoute {
  id: string;
  name: string;
  localName?: string;
  description: string;
  dataPath: string;
  color: string;
  sourceLabel: string;
  attribution: string;
  safetyNote: string;
  referenceMetrics?: PeakRouteReferenceMetrics;
}

export interface RouteDocument {
  schema_version: 1;
  peak_id: string;
  route_id: string;
  name: string;
  source: {
    label: string;
    attribution: string;
    mode?: string;
    osm_coverage_ratio?: number;
  };
  points: GeoRoutePoint[];
}

export interface TerrainGeoReference {
  centerLat: number;
  centerLon: number;
  baseElevationM: number;
}

export interface TerrainManifestDocument {
  center: { lat: number; lon: number };
  elevation_m: { base: number };
}
