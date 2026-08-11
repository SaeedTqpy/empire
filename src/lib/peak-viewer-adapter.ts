import type { Peak } from "@/types/peak";
import type { Empire } from "@/types/empire";

/**
 * Temporary phase-1 boundary between the new Peak domain and the untouched
 * Empire viewer engine. Keeping the adapter here lets the domain migrate
 * cleanly without destabilizing the rendering stack before the DEM arrives.
 */
export function peakToViewerModel(peak: Peak): Empire {
  return {
    id: peak.id,
    name: peak.name,
    dwelling: peak.name,
    subtitle: peak.subtitle,
    description: peak.description,
    modelPath: peak.modelPath,
    imageryAttribution: peak.terrain.imageryAttribution,
    tint: peak.tint,
    camera: peak.camera,
    facts: [],
    hotspots: peak.hotspots.map((hotspot) => ({
      id: hotspot.id,
      title: hotspot.title,
      short: hotspot.short,
      detail: hotspot.detail,
      category: "structure",
      anchor: hotspot.anchor,
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
