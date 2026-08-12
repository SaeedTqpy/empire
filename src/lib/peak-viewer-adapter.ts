import type { Peak, PeakHotspot, Vec3 } from "@/types/peak";
import type { Empire } from "@/types/empire";

const EARTH_RADIUS_M = 6_371_008.8;

function hotspotFallbackAnchor(peak: Peak, hotspot: PeakHotspot): Vec3 {
  if (hotspot.anchor) return hotspot.anchor;
  if (!hotspot.coordinates) return [0.5, 0.5, 0.5];
  const extentM = peak.terrain.extentKm * 1000;
  const centerLatRad = (peak.coordinates.lat * Math.PI) / 180;
  const eastM = EARTH_RADIUS_M * Math.cos(centerLatRad) * (((hotspot.coordinates.lon - peak.coordinates.lon) * Math.PI) / 180);
  const northM = EARTH_RADIUS_M * (((hotspot.coordinates.lat - peak.coordinates.lat) * Math.PI) / 180);
  const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
  return [clamp01(0.5 + eastM / extentM), 0.5, clamp01(0.5 + northM / extentM)];
}

function imageryAttribution(peak: Peak) {
  const sentinel = peak.terrain.imageryAttribution;
  const detail = peak.terrain.streaming?.detailImagery;
  if (!detail?.enabled) return sentinel;

  // Keep both credits visible at all times. The VHR layer is geographically
  // partial and can be disabled with ?detail=0, while Sentinel-2 remains the
  // complete fallback under it.
  return `${detail.attribution} · Sentinel-2 fallback: ${sentinel}`;
}

/**
 * Temporary compatibility boundary while the old viewer types are retired.
 * Peak semantics, including Phase 6 geo markers, stay intact across it.
 */
export function peakToViewerModel(peak: Peak): Empire {
  return {
    id: peak.id,
    name: peak.name,
    dwelling: peak.name,
    subtitle: peak.subtitle,
    description: peak.description,
    modelPath: peak.modelPath,
    streaming: peak.terrain.streaming,
    imageryAttribution: imageryAttribution(peak),
    tint: peak.tint,
    camera: peak.camera,
    facts: [],
    hotspots: peak.hotspots.map((hotspot) => ({
      id: hotspot.id,
      title: hotspot.title,
      short: hotspot.short,
      detail: hotspot.detail,
      category: hotspot.category,
      anchor: hotspotFallbackAnchor(peak, hotspot),
      geo: hotspot.coordinates
        ? {
            lat: hotspot.coordinates.lat,
            lon: hotspot.coordinates.lon,
            elevationM: hotspot.elevationM,
            sourceLabel: hotspot.sourceLabel,
          }
        : undefined,
      focus: hotspot.focus,
    })),
    interior: emptySection("Terrain View"),
    floorPlan: {
      ...emptySection("Route Overview"),
      rooms: [],
    },
    artifacts: {
      ...emptySection("Mountain Landmarks"),
      items: [],
    },
    dailyLife: emptySection("Mountain Conditions"),
    geography: {
      ...emptySection("Geography"),
      regionLabel: `${peak.range}, ${peak.country}`,
    },
    lesson: {
      title: peak.name,
      intro: peak.description,
      blocks: [],
    },
    quiz: [],
    timeline: [],
    keywords: peak.keywords,
  };
}

function emptySection(title: string) {
  return {
    title,
    kicker: "Iran 3D Peaks",
    cta: "Explore",
    text: "Content will be connected after the real terrain pipeline is in place.",
    image: "",
  };
}