import type { Peak } from "@/types/peak";
import { damavand } from "./peaks/damavand";

/** Peak-first runtime dataset. */
export const PEAKS: Peak[] = [damavand];

export const peakById = (id: string): Peak => PEAKS.find((peak) => peak.id === id) ?? PEAKS[0];

export const DEFAULT_PEAK_ID = "damavand";

export const peakImages = (peak: Peak) => peak.media;

export interface PeakSearchEntry {
  kind: "peak" | "hotspot" | "keyword";
  title: string;
  subtitle: string;
  peakId: string;
  hotspotId?: string;
}

export function buildPeakSearchIndex(): PeakSearchEntry[] {
  const out: PeakSearchEntry[] = [];
  for (const peak of PEAKS) {
    out.push({
      kind: "peak",
      title: peak.name,
      subtitle: `${peak.elevationM.toLocaleString()} m · ${peak.range}, ${peak.country}`,
      peakId: peak.id,
    });
    for (const hotspot of peak.hotspots) {
      out.push({
        kind: "hotspot",
        title: hotspot.title,
        subtitle: `${peak.name} · ${hotspot.short}`,
        peakId: peak.id,
        hotspotId: hotspot.id,
      });
    }
    for (const keyword of peak.keywords) {
      out.push({
        kind: "keyword",
        title: keyword,
        subtitle: `Related to ${peak.name}`,
        peakId: peak.id,
      });
    }
  }
  return out;
}

/* --------------------------------------------------------------------------
 * Legacy Empire exports
 * --------------------------------------------------------------------------
 * These stay temporarily so the original, currently-unused modal/components
 * still type-check while the runtime is migrated incrementally. The new app
 * does not render this dataset. Remove this compatibility block once the old
 * Empire-only components are deleted in a later cleanup pass.
 */
import type { Empire } from "@/types/empire";
import { roman } from "./empires/roman";
import { egypt } from "./empires/egypt";
import { persian } from "./empires/persian";
import { han } from "./empires/han";
import { byzantine } from "./empires/byzantine";
import { ottoman } from "./empires/ottoman";
import { mughal } from "./empires/mughal";
import { inca } from "./empires/inca";

/** @deprecated Use PEAKS. */
export const EMPIRES: Empire[] = [roman, egypt, persian, han, byzantine, ottoman, mughal, inca];
/** @deprecated Use peakById. */
export const empireById = (id: string): Empire => EMPIRES.find((empire) => empire.id === id) ?? EMPIRES[0];
/** @deprecated Use DEFAULT_PEAK_ID. */
export const DEFAULT_EMPIRE_ID = "roman";
/** @deprecated Peak media lives on Peak.media. */
export const empireImages = (empire: Empire) => ({
  thumbnail: `/img/${empire.id}/thumbnail.webp`,
  hero: `/img/${empire.id}/hero.webp`,
  interior: empire.interior.image,
  floorPlan: empire.floorPlan.image,
  artifacts: empire.artifacts.image,
  dailyLife: empire.dailyLife.image,
  map: empire.geography.image,
});

/** @deprecated Legacy search contract retained for old modal compilation. */
export interface SearchEntry {
  kind: "empire" | "dwelling" | "feature" | "room" | "artifact" | "material";
  title: string;
  subtitle: string;
  empireId: string;
  hotspotId?: string;
}

/** @deprecated Use buildPeakSearchIndex. */
export function buildSearchIndex(): SearchEntry[] {
  const out: SearchEntry[] = [];
  for (const empire of EMPIRES) {
    out.push({ kind: "empire", title: empire.name, subtitle: `${empire.dwelling} — ${empire.subtitle}`, empireId: empire.id });
    out.push({ kind: "dwelling", title: empire.dwelling, subtitle: `Dwelling of ${empire.name}`, empireId: empire.id });
    for (const hotspot of empire.hotspots) {
      out.push({ kind: "feature", title: hotspot.title, subtitle: `${empire.dwelling} · ${hotspot.short}`, empireId: empire.id, hotspotId: hotspot.id });
    }
    for (const room of empire.floorPlan.rooms) {
      out.push({ kind: "room", title: room.name, subtitle: `${empire.dwelling} floor plan`, empireId: empire.id });
    }
    for (const artifact of empire.artifacts.items) {
      out.push({ kind: "artifact", title: artifact.name, subtitle: `${empire.dwelling} · ${artifact.purpose}`, empireId: empire.id });
    }
    for (const keyword of empire.keywords) {
      out.push({ kind: "material", title: keyword, subtitle: `Related to ${empire.name}`, empireId: empire.id });
    }
  }
  return out;
}
