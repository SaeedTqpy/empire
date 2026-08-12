#!/usr/bin/env python3
"""Search OpenAerialMap for genuinely high-resolution Damavand imagery.

The probe is source-discovery only: a catalog hit still has to pass raster
georeferencing, overlap and measured-resolution validation before ingestion.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

DAMAVAND_BBOX = (51.94305968192662, 35.81640194544132, 52.27634031807337, 36.086198054558686)
API = "https://api.openaerialmap.org/meta"
USER_AGENT = "Iran-3D-Peaks/phase8-source-probe (+https://github.com/SaeedTqpy/empire)"


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    bbox = ",".join(str(value) for value in DAMAVAND_BBOX)
    # OAM API accepts bbox and sorts can be applied client-side. A generous
    # limit keeps the source probe deterministic without paging for this AOI.
    query = urllib.parse.urlencode({"bbox": bbox, "limit": 100})
    url = f"{API}?{query}"
    payload = fetch_json(url)

    raw_results = payload.get("results") or []
    candidates = []
    for result in raw_results:
        properties = result.get("properties") or {}
        resolution = properties.get("gsd")
        if resolution is None:
            resolution = properties.get("resolution")
        try:
            resolution_m = float(resolution) if resolution is not None else None
        except (TypeError, ValueError):
            resolution_m = None

        candidate = {
            "uuid": result.get("uuid") or result.get("_id"),
            "title": properties.get("title") or result.get("title"),
            "provider": properties.get("provider"),
            "acquisition_start": properties.get("acquisition_start"),
            "acquisition_end": properties.get("acquisition_end"),
            "platform": properties.get("platform"),
            "sensor": properties.get("sensor"),
            "gsd_m": resolution_m,
            "license": properties.get("license"),
            "url": properties.get("url"),
            "tms": properties.get("tms"),
            "bbox": result.get("bbox"),
            "geojson": result.get("geojson"),
        }
        candidates.append(candidate)

    candidates.sort(key=lambda item: item["gsd_m"] if item["gsd_m"] is not None else 1e9)
    qualifying = [item for item in candidates if item["gsd_m"] is not None and item["gsd_m"] < 10.0]

    report = {
        "schema_version": 1,
        "source": "OpenAerialMap / Open Imagery Network",
        "api": url,
        "bbox_wgs84": list(DAMAVAND_BBOX),
        "catalog_found": payload.get("meta", {}).get("found"),
        "results_in_bbox": len(candidates),
        "qualifying_under_10m": len(qualifying),
        "qualification_rule": "reported OAM ground resolution < 10m; exact overlap and source raster georeferencing must still be validated before ingestion",
        "license_note": "OAM states imagery in OIN is CC-BY 4.0; preserve per-item attribution in the final source manifest.",
        "candidates": candidates,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
