#!/usr/bin/env python3
"""Build a Damavand reference route from open trail geometry.

The authored GPS landmarks choose the intended corridor. OpenStreetMap supplies
trail geometry between those controls when the graph is connected. Missing OSM
segments fall back to a densified landmark-to-landmark line and are recorded in
the output metadata so the UI never presents the result as navigation-grade.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

EARTH_RADIUS_M = 6_371_008.8
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def request_json(url: str, payload: bytes | None = None, retries: int = 2) -> dict:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "User-Agent": "Iran-3D-Peaks-route-builder/1.0",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                },
            )
            with urllib.request.urlopen(req, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"request failed: {last}")


def fetch_osm(anchors: list[dict]) -> dict | None:
    lats = [float(a["lat"]) for a in anchors]
    lons = [float(a["lon"]) for a in anchors]
    margin = 0.012
    south, north = min(lats) - margin, max(lats) + margin
    west, east = min(lons) - margin, max(lons) + margin
    query = f'''[out:json][timeout:60];
way["highway"~"^(path|footway|track|steps)$"]({south},{west},{north},{east});
out body geom;'''
    payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"Overpass: {endpoint}", flush=True)
            data = request_json(endpoint, payload)
            if data.get("elements"):
                return data
        except Exception as exc:
            print(f"Overpass endpoint failed: {exc}", flush=True)
    return None


def build_graph(data: dict) -> tuple[dict[int, tuple[float, float]], dict[int, list[tuple[int, float]]]]:
    coords: dict[int, tuple[float, float]] = {}
    graph: dict[int, list[tuple[int, float]]] = {}
    for element in data.get("elements", []):
        nodes = element.get("nodes") or []
        geometry = element.get("geometry") or []
        if len(nodes) != len(geometry) or len(nodes) < 2:
            continue
        for node_id, point in zip(nodes, geometry):
            coords[int(node_id)] = (float(point["lat"]), float(point["lon"]))
        for left, right in zip(nodes, nodes[1:]):
            left = int(left)
            right = int(right)
            a = coords[left]
            b = coords[right]
            weight = haversine(a, b)
            graph.setdefault(left, []).append((right, weight))
            graph.setdefault(right, []).append((left, weight))
    return coords, graph


def nearest_node(point: tuple[float, float], coords: dict[int, tuple[float, float]]) -> tuple[int | None, float]:
    best_id: int | None = None
    best = float("inf")
    for node_id, coord in coords.items():
        distance = haversine(point, coord)
        if distance < best:
            best = distance
            best_id = node_id
    return best_id, best


def shortest_path(start: int, goal: int, graph: dict[int, list[tuple[int, float]]]) -> list[int] | None:
    queue: list[tuple[float, int]] = [(0.0, start)]
    dist = {start: 0.0}
    previous: dict[int, int] = {}
    while queue:
        cost, node = heapq.heappop(queue)
        if node == goal:
            path = [goal]
            while path[-1] != start:
                path.append(previous[path[-1]])
            path.reverse()
            return path
        if cost != dist.get(node):
            continue
        for neighbour, edge in graph.get(node, []):
            candidate = cost + edge
            if candidate < dist.get(neighbour, float("inf")):
                dist[neighbour] = candidate
                previous[neighbour] = node
                heapq.heappush(queue, (candidate, neighbour))
    return None


def fallback_segment(a: tuple[float, float], b: tuple[float, float], spacing_m: float = 55.0) -> list[tuple[float, float]]:
    count = max(2, math.ceil(haversine(a, b) / spacing_m) + 1)
    return [
        (a[0] + (b[0] - a[0]) * i / (count - 1), a[1] + (b[1] - a[1]) * i / (count - 1))
        for i in range(count)
    ]


def append_unique(target: list[tuple[float, float]], incoming: list[tuple[float, float]]) -> None:
    for point in incoming:
        if target and haversine(target[-1], point) < 0.5:
            continue
        target.append(point)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    anchors = config["anchors"]

    osm = fetch_osm(anchors)
    coords: dict[int, tuple[float, float]] = {}
    graph: dict[int, list[tuple[int, float]]] = {}
    if osm:
        coords, graph = build_graph(osm)
    print(f"OSM graph: {len(coords)} nodes", flush=True)

    route: list[tuple[float, float]] = []
    osm_weight = 0.0
    total_weight = 0.0
    osm_segments = 0
    fallback_segments = 0

    for left, right in zip(anchors, anchors[1:]):
        a = (float(left["lat"]), float(left["lon"]))
        b = (float(right["lat"]), float(right["lon"]))
        direct = haversine(a, b)
        total_weight += direct
        selected: list[tuple[float, float]] | None = None

        if coords:
            start, start_gap = nearest_node(a, coords)
            goal, goal_gap = nearest_node(b, coords)
            if start is not None and goal is not None and start_gap <= 260 and goal_gap <= 260:
                ids = shortest_path(start, goal, graph)
                if ids:
                    candidate = [coords[node_id] for node_id in ids]
                    candidate_length = sum(haversine(x, y) for x, y in zip(candidate, candidate[1:]))
                    if candidate_length <= max(direct * 4.0, direct + 450):
                        selected = [a, *candidate, b]

        if selected:
            osm_segments += 1
            osm_weight += direct
            append_unique(route, selected)
        else:
            fallback_segments += 1
            append_unique(route, fallback_segment(a, b))

    # Remove points that are effectively duplicates after snapping to OSM nodes.
    compact: list[tuple[float, float]] = []
    for point in route:
        if not compact or haversine(compact[-1], point) >= 3.0:
            compact.append(point)
    if compact[-1] != route[-1]:
        compact.append(route[-1])

    output_path = Path(config["output"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    coverage = 0.0 if total_weight <= 0 else osm_weight / total_weight
    document = {
        "schema_version": 1,
        "peak_id": config["peak_id"],
        "route_id": config["route_id"],
        "name": config["name"],
        "source": {
            "label": config["source"]["label"],
            "attribution": config["source"]["attribution"],
            "mode": "osm-with-landmark-fallback" if osm else "landmark-fallback",
            "osm_coverage_ratio": round(coverage, 4),
            "osm_segments": osm_segments,
            "fallback_segments": fallback_segments,
        },
        "reference_metrics": config.get("reference_metrics", {}),
        "points": [{"lat": round(lat, 7), "lon": round(lon, 7)} for lat, lon in compact],
        "landmarks": anchors,
        "safety": "Reference visualization only. Do not use this generated line as your sole navigation source.",
    }
    output_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    length_km = sum(haversine(x, y) for x, y in zip(compact, compact[1:])) / 1000.0
    print(
        f"Wrote {output_path}: {len(compact)} points, {length_km:.2f} km geometric, "
        f"OSM corridor coverage {coverage:.1%} ({osm_segments} OSM / {fallback_segments} fallback segments)",
        flush=True,
    )


if __name__ == "__main__":
    main()
