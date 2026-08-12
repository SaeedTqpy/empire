import type { TerrainStreamingConfig } from "./streaming";

/** Empire Atlas — core data contracts.
 *  The entire application is driven by these types; adding a new empire
 *  means adding data + assets, never touching the viewer or UI. */

export type Vec3 = [number, number, number];

/** Hotspot anchor, expressed in *normalised model space*:
 *  x/z are fractions across the model footprint (0..1, min→max),
 *  y is a fraction of model height (0..1). Converted to world
 *  coordinates after the model is normalised. */
export interface Hotspot {
  id: string;
  title: string;
  /** one-line italic summary shown on the floating label */
  short: string;
  /** longer educational description shown when activated */
  detail: string;
  category: "structure" | "roof" | "court" | "entrance" | "interior" | "artifact-zone" | "facade" | "summit" | "shelter" | "landmark" | "hazard" | "water" | "route";
  /** Placed against the model's bounding box; the viewer snaps it onto the
   *  nearest real surface so the pin sits on the building, not in the air. */
  anchor: Vec3;
  /** Phase 6 geographic placement for real terrain peaks. */
  geo?: { lat: number; lon: number; elevationM?: number; sourceLabel?: string };
  /** Which kind of surface the pin belongs on. The viewer resolves this
   *  against the model's own geometry, so a pin lands on the feature it
   *  names whatever the dwelling's shape:
   *  - "roof"  the highest built mass nearest the anchor
   *  - "court" the open low ground enclosed by that mass
   *  - "wall"  the outer skin, met by coming in horizontally from outside
   *  The anchor then only steers *which* roof, court or wall. */
  snap?: "roof" | "court" | "wall";
  /** @deprecated Annotations now appear on hover at the pin, so labels no
   *  longer float at a fixed offset. Retained so existing data still type-checks. */
  labelOffset?: [number, number];
  /** how strongly the camera pushes in when activated (1 = default) */
  focus?: number;
}

export interface KeyFact {
  label: string;
  value: string;
  icon: "period" | "region" | "materials" | "feature" | "occupants";
}

export interface Artifact {
  name: string;
  purpose: string;
  material: string;
  context: string;
}

export interface QuizQuestion {
  q: string;
  choices: string[];
  answer: number;
  explanation: string;
}

export interface TimelineEntry {
  era: string;
  year: string;
  text: string;
}

export interface CameraPreset {
  /** azimuth in degrees (0 = +Z front, positive orbits right) */
  azimuth: number;
  /** elevation in degrees above horizon */
  elevation: number;
  /** distance multiplier relative to auto-framing */
  dist: number;
  /** vertical framing bias: fraction of model height for look-at */
  targetY: number;
}

export interface EmpireSection {
  title: string;
  kicker: string;
  cta: string;
  text: string;
  /** image path under /img */
  image: string;
}

export interface FloorPlanRoom {
  name: string;
  note?: string;
}

export interface LessonBlock {
  heading: string;
  body: string;
}

export interface Empire {
  id: string;
  name: string;
  dwelling: string;
  subtitle: string;
  description: string;
  modelPath: string;
  /** Optional Phase 7 spatial LOD configuration. */
  streaming?: TerrainStreamingConfig;
  /** Optional public credit for imagery baked into the model. */
  imageryAttribution?: string;
  /** per-empire warm accent used for subtle scene tinting */
  tint: string;
  camera: CameraPreset;
  facts: KeyFact[];
  hotspots: Hotspot[];
  interior: EmpireSection;
  floorPlan: EmpireSection & { rooms: FloorPlanRoom[] };
  artifacts: EmpireSection & { items: Artifact[] };
  dailyLife: EmpireSection;
  geography: EmpireSection & { regionLabel: string };
  lesson: { title: string; intro: string; blocks: LessonBlock[] };
  quiz: QuizQuestion[];
  timeline: TimelineEntry[];
  keywords: string[];
}
