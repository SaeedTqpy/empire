import type { Peak } from "@/types/peak";
import type { Empire } from "@/types/empire";
import { peakToViewerModel } from "@/lib/peak-viewer-adapter";
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
 * Temporary viewer compatibility exports
 * --------------------------------------------------------------------------
 * Viewer.tsx still consumes the original Empire-shaped rendering contract in
 * phase 1. It now receives ONLY the Damavand adapter, so no civilization data
 * is rendered or preloaded at runtime. This block disappears when the terrain
 * viewer becomes Peak-native.
 */
const DAMAVAND_VIEWER_MODEL = peakToViewerModel(damavand);

/** @deprecated Viewer compatibility only. Use PEAKS in product code. */
export const EMPIRES: Empire[] = [DAMAVAND_VIEWER_MODEL];
/** @deprecated Viewer compatibility only. Use peakById. */
export const empireById = (_id: string): Empire => DAMAVAND_VIEWER_MODEL;
/** @deprecated Viewer compatibility only. Use DEFAULT_PEAK_ID. */
export const DEFAULT_EMPIRE_ID = "damavand";
/** @deprecated Peak media lives on Peak.media. */
export const empireImages = (_empire: Empire) => ({
  thumbnail: damavand.media.thumbnail,
  hero: damavand.media.hero,
  interior: damavand.media.hero,
  floorPlan: damavand.media.hero,
  artifacts: damavand.media.hero,
  dailyLife: damavand.media.hero,
  map: damavand.media.hero,
});

/** @deprecated Legacy modal contract retained only until old files are removed. */
export interface SearchEntry {
  kind: "empire" | "dwelling" | "feature" | "room" | "artifact" | "material";
  title: string;
  subtitle: string;
  empireId: string;
  hotspotId?: string;
}

/** @deprecated Use buildPeakSearchIndex. */
export function buildSearchIndex(): SearchEntry[] {
  return [
    {
      kind: "empire",
      title: damavand.name,
      subtitle: `${damavand.elevationM.toLocaleString()} m · ${damavand.range}`,
      empireId: damavand.id,
    },
  ];
}
