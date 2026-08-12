#!/usr/bin/env python3
"""Probe Esri World Imagery metadata at Mount Damavand.

This script uses ArcGIS public item metadata only. It does not download or
redistribute imagery. The result is a source-quality gate for the optional
Phase 8 runtime imagery provider, including the exact footprint of the best
matching high-resolution source record.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ITEM_ID = "eafaa19cb03a4bcba592ef12fb6e14e5"  # Wayback 2026-03-26 metadata
SUMMIT = (52.1097, 35.9513)
DAMAVAND_BBOX = (51.94305968192662, 35.81640194544132, 52.27634031807337, 36.086198054558686)
USER_AGENT = "Iran-3D-Peaks/phase8-source-probe (+https://github.com/SaeedTqpy/empire)"


def get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def collect_layer_urls(node: Any, output: list[tuple[str, str]]) -> None:
    if isinstance(node, dict):
        url = node.get("url")
        title = node.get("title") or node.get("name") or node.get("id") or "unnamed"
        if isinstance(url, str) and ("FeatureServer" in url or "MapServer" in url):
            output.append((str(title), url))
        for value in node.values():
            collect_layer_urls(value, output)
    elif isinstance(node, list):
        for value in node:
            collect_layer_urls(value, output)


def feature_query_url(service_url: str) -> str | None:
    clean = service_url.rstrip("/")
    if "/FeatureServer/" in clean or "/MapServer/" in clean:
        return clean + "/query"
    return None


def expand_service(title: str, url: str) -> list[tuple[str, str]]:
    clean = url.rstrip("/")
    if clean.rsplit("/", 1)[-1].isdigit():
        return [(title, clean)]
    try:
        service = get_json(clean, {"f": "json"})
    except Exception as exc:
        print(f"Could not inspect {clean}: {exc}", flush=True)
        return []
    layers = service.get("layers") or []
    tables = service.get("tables") or []
    children = [*layers, *tables]
    return [
        (f"{title} / {layer.get('name', layer.get('id'))}", f"{clean}/{layer['id']}")
        for layer in children
        if "id" in layer
    ]


def parse_resolution(attrs: dict[str, Any]) -> float | None:
    likely = [
        "SRC_RES", "src_res", "RESOLUTION", "Resolution", "resolution",
        "GSD", "gsd", "PIXEL_SIZE", "PixelSize", "pixel_size", "MinPS",
        "minps", "MinPixelSize", "BestRes", "best_res",
    ]
    for key in likely:
        value = attrs.get(key)
        if value in (None, ""):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


def geometry_bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    rings = geometry.get("rings") or []
    points = [point for ring in rings for point in ring if len(point) >= 2]
    if not points:
        return None
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_overlap_fraction(
    target: tuple[float, float, float, float],
    source: tuple[float, float, float, float],
) -> float:
    tw, ts, te, tn = target
    sw, ss, se, sn = source
    width = max(0.0, min(te, se) - max(tw, sw))
    height = max(0.0, min(tn, sn) - max(ts, ss))
    target_area = max(0.0, (te - tw) * (tn - ts))
    return 0.0 if target_area == 0.0 else (width * height) / target_area


def point_in_ring(point: tuple[float, float], ring: list[list[float]]) -> bool:
    x, y = point
    inside = False
    if len(ring) < 3:
        return False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        crosses = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-30) + xi
        )
        if crosses:
            inside = not inside
        j = i
    return inside


def point_in_polygon(point: tuple[float, float], geometry: dict[str, Any]) -> bool:
    # ArcGIS polygon rings use winding to distinguish holes; for this source
    # gate we only need to prove that the already matched summit falls inside
    # at least one returned ring.
    return any(point_in_ring(point, ring) for ring in geometry.get("rings") or [])


def query_best_footprint(layer_url: str, object_id: int) -> dict[str, Any] | None:
    payload = get_json(
        layer_url.rstrip("/") + "/query",
        {
            "f": "json",
            "where": f"OBJECTID={object_id}",
            "outFields": "OBJECTID,SRC_DATE,SRC_RES,SAMP_RES,SRC_ACC,SRC_DESC,MinMapLevel,MaxMapLevel,NICE_NAME,NICE_DESC,BlockName,ReleaseName",
            "returnGeometry": "true",
            "outSR": 4326,
            "geometryPrecision": 7,
        },
    )
    if payload.get("error"):
        raise RuntimeError(f"ArcGIS footprint query failed: {payload['error']}")
    features = payload.get("features") or []
    return features[0] if features else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    item_url = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}"
    item = get_json(item_url, {"f": "json"})
    data = get_json(item_url + "/data", {"f": "json"})

    discovered: list[tuple[str, str]] = []
    collect_layer_urls(item, discovered)
    collect_layer_urls(data, discovered)

    direct_url = item.get("url")
    if isinstance(direct_url, str) and direct_url.startswith("http"):
        discovered.append((str(item.get("title") or ITEM_ID), direct_url))

    discovered = list(dict.fromkeys(discovered))
    print("ArcGIS item:", json.dumps({
        "id": item.get("id"),
        "title": item.get("title"),
        "type": item.get("type"),
        "url": item.get("url"),
        "typeKeywords": item.get("typeKeywords"),
    }, indent=2), flush=True)

    expanded: list[tuple[str, str]] = []
    for title, url in discovered:
        expanded.extend(expand_service(title, url))
    expanded = list(dict.fromkeys(expanded))

    records: list[dict[str, Any]] = []
    lon, lat = SUMMIT
    for title, layer_url in expanded:
        query_url = feature_query_url(layer_url)
        if not query_url:
            continue
        params = {
            "f": "json",
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
        }
        try:
            payload = get_json(query_url, params)
        except Exception as exc:
            print(f"Query failed for {layer_url}: {exc}", flush=True)
            continue
        if payload.get("error"):
            print(f"ArcGIS query error for {layer_url}: {payload['error']}", flush=True)
            continue
        for feature in payload.get("features") or []:
            attrs = feature.get("attributes") or {}
            records.append({
                "layer": title,
                "layer_url": layer_url,
                "reported_resolution": parse_resolution(attrs),
                "attributes": attrs,
            })

    records.sort(key=lambda row: row["reported_resolution"] if row["reported_resolution"] is not None else 1e12)
    qualifying = [row for row in records if row["reported_resolution"] is not None and row["reported_resolution"] < 10.0]

    best_source = None
    if qualifying:
        best = qualifying[0]
        attrs = best["attributes"]
        object_id = attrs.get("OBJECTID")
        if object_id is not None:
            feature = query_best_footprint(best["layer_url"], int(object_id))
            if feature:
                geometry = feature.get("geometry") or {}
                bounds = geometry_bounds(geometry)
                ring_count = len(geometry.get("rings") or [])
                vertex_count = sum(len(ring) for ring in geometry.get("rings") or [])
                best_source = {
                    "layer_url": best["layer_url"],
                    "object_id": int(object_id),
                    "attributes": feature.get("attributes") or attrs,
                    "footprint_wgs84_bbox": list(bounds) if bounds else None,
                    "footprint_ring_count": ring_count,
                    "footprint_vertex_count": vertex_count,
                    "summit_inside_footprint": point_in_polygon(SUMMIT, geometry),
                    "damavand_bbox_overlap_fraction": round(bbox_overlap_fraction(DAMAVAND_BBOX, bounds), 6) if bounds else 0.0,
                }

    report = {
        "schema_version": 2,
        "source": "Esri World Imagery Wayback metadata",
        "item_id": ITEM_ID,
        "item_title": item.get("title"),
        "item_type": item.get("type"),
        "item_service_url": item.get("url"),
        "item_url": item_url,
        "summit_wgs84": {"lon": lon, "lat": lat},
        "damavand_bbox_wgs84": list(DAMAVAND_BBOX),
        "layer_count": len(expanded),
        "records_at_summit": len(records),
        "qualifying_under_10m": len(qualifying),
        "best_reported_resolution": qualifying[0]["reported_resolution"] if qualifying else None,
        "best_source": best_source,
        "note": "Metadata-only source validation. No imagery is copied or exported by this probe.",
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str), flush=True)

    if best_source is None:
        raise SystemExit("No sub-10m Damavand source footprint could be validated")
    if not best_source["summit_inside_footprint"]:
        raise SystemExit("Best source footprint does not actually contain Damavand summit")


if __name__ == "__main__":
    main()
