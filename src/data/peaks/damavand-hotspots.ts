import type { PeakHotspot } from "@/types/peak";

/**
 * Phase 6 geo-aware Damavand markers.
 *
 * Coordinates/elevations reuse the same reference waypoint set that guides
 * the Phase 5 South Route. ViewerEngine raycasts each lat/lon onto the real
 * DEM at runtime, so the reference elevation is metadata rather than the
 * rendered Y coordinate.
 */
export const damavandHotspots: PeakHotspot[] = [
  {
    id: "goosfand-sara",
    title: "Goosfand Sara",
    short: "Lower staging point on the South Route reference corridor.",
    detail:
      "A useful orientation marker near the lower end of the South Route dataset. The 3D pin is clamped to the DEM; use it as geographic context rather than a statement about current services or access.",
    category: "route",
    coordinates: { lat: 35.9027778, lon: 52.1094444 },
    elevationM: 3040,
    sourceLabel: "Damavand South Route reference waypoints",
    focus: 0.82,
  },
  {
    id: "seasonal-river-2",
    title: "Seasonal Watercourse",
    short: "A seasonal river waypoint on the southern approach.",
    detail:
      "The source waypoint identifies seasonal flow here. Water availability is not guaranteed; this marker is geographic context only and must not be treated as a live water report.",
    category: "water",
    coordinates: { lat: 35.9216667, lon: 52.1044444 },
    elevationM: 3688,
    sourceLabel: "Damavand South Route reference waypoints",
    focus: 0.86,
  },
  {
    id: "sang-e-do-shakh",
    title: "Sang-e Do Shakh",
    short: "Named landmark on the South Route waypoint sequence.",
    detail:
      "A route-orientation landmark between the lower approach and Bargah Sevom. The marker is projected from its geographic waypoint onto the same terrain mesh used by the route overlay.",
    category: "landmark",
    coordinates: { lat: 35.9283333, lon: 52.1086111 },
    elevationM: 4055,
    sourceLabel: "Damavand South Route reference waypoints",
    focus: 0.9,
  },
  {
    id: "bargah-sevom",
    title: "Bargah Sevom",
    short: "High-camp / hut reference point on Damavand's South Route.",
    detail:
      "This marker uses the 'Bargah Sevom New Hut' waypoint in the route reference set. It identifies the geographic position in the 3D atlas; current hut status, capacity and access should be checked separately before a climb.",
    category: "shelter",
    coordinates: { lat: 35.9325, lon: 52.1088889 },
    elevationM: 4250,
    sourceLabel: "Damavand South Route reference waypoints",
    focus: 0.94,
  },
  {
    id: "upper-ridge",
    title: "Upper Ridge",
    short: "High-altitude context marker near the end of the first ridge.",
    detail:
      "The reference waypoint is around 4,912 m. Above this zone the route is already in sustained high-altitude terrain. The hazard marker is contextual, not a forecast or a substitute for current mountain conditions and judgment.",
    category: "hazard",
    coordinates: { lat: 35.9441667, lon: 52.1088889 },
    elevationM: 4912,
    sourceLabel: "Damavand South Route reference waypoints",
    focus: 1.02,
  },
  {
    id: "damavand-summit",
    title: "Damavand Summit",
    short: "The summit marker at the top of the South Route reference corridor.",
    detail:
      "The atlas keeps the canonical 5,610 m summit value as reference metadata while the visible pin is raycast onto the sampled DEM surface. DEM sample height and canonical summit elevation are intentionally kept separate.",
    category: "summit",
    coordinates: { lat: 35.9513, lon: 52.1097 },
    elevationM: 5610,
    sourceLabel: "Damavand peak data + South Route reference waypoints",
    focus: 1.08,
  },
];
