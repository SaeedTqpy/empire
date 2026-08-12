import type { GeoRoutePoint } from "@/types/route";

function firstText(node: Element, selector: string) {
  return node.querySelector(selector)?.textContent?.trim() || undefined;
}

export function parseGpx(text: string): GeoRoutePoint[] {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.querySelector("parsererror")) throw new Error("The GPX file is not valid XML.");

  const points: GeoRoutePoint[] = [];
  for (const node of Array.from(doc.querySelectorAll("trkpt, rtept"))) {
    const lat = Number(node.getAttribute("lat"));
    const lon = Number(node.getAttribute("lon"));
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;

    const elevationText = firstText(node, "ele");
    const elevationM = elevationText === undefined ? undefined : Number(elevationText);
    const point: GeoRoutePoint = { lat, lon };
    if (Number.isFinite(elevationM)) point.elevationM = elevationM;
    const name = firstText(node, "name");
    if (name) point.name = name;
    points.push(point);
  }

  if (points.length < 2) throw new Error("The GPX file needs at least two track or route points.");
  return points;
}
