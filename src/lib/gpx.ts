import type { GeoRoutePoint } from "@/types/route";

function firstText(node: Element, selector: string) {
  return node.querySelector(selector)?.textContent?.trim() || undefined;
}

export function parseGpx(text: string): GeoRoutePoint[] {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.querySelector("parsererror")) throw new Error("The GPX file is not valid XML.");

  const nodes = Array.from(doc.querySelectorAll("trkpt, rtept"));
  const points = nodes
    .map((node) => {
      const lat = Number(node.getAttribute("lat"));
      const lon = Number(node.getAttribute("lon"));
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
      const elevationText = firstText(node, "ele");
      const elevationM = elevationText === undefined ? undefined : Number(elevationText);
      return {
        lat,
        lon,
        elevationM: Number.isFinite(elevationM) ? elevationM : undefined,
        name: firstText(node, "name"),
      } satisfies GeoRoutePoint;
    })
    .filter((point): point is GeoRoutePoint => point !== null);

  if (points.length < 2) throw new Error("The GPX file needs at least two track or route points.");
  return points;
}
