#!/usr/bin/env python3
"""Resolve the exact ArcGIS runtime service for the validated Wayback snapshot.

No imagery bytes are downloaded here. The script records only public ArcGIS
item/service metadata so Phase 8 can bind the VHR overlay to the same snapshot
whose source metadata was validated at Damavand.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ITEM_ID = "b4c5c1b59c4141c5b503335b5baa2df4"
USER_AGENT = "Iran-3D-Peaks/phase8-runtime-probe (+https://github.com/SaeedTqpy/empire)"


def get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    with urllib.request.urlopen(request, timeout=90) as response:
        raw = response.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Expected JSON from {url}, got: {raw[:300]!r}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    item_rest = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}"
    item = get_json(item_rest, {"f": "json"})
    data = get_json(item_rest + "/data", {"f": "json"})

    service_url = item.get("url")
    service_info: dict[str, Any] | None = None
    if isinstance(service_url, str) and service_url.startswith("http"):
        try:
            service_info = get_json(service_url, {"f": "json"})
        except Exception as exc:
            print(f"Service metadata request failed: {exc}", flush=True)

    interesting_data = {
        key: value
        for key, value in data.items()
        if key.lower() in {
            "url", "templateurl", "styleurl", "wmtsinfo", "tileinfo", "layers", "operationalLayers".lower(),
            "copyrighttext", "attribution", "serviceurl", "resourceinfo"
        }
    }

    interesting_service: dict[str, Any] = {}
    if service_info:
        for key in (
            "currentVersion", "serviceDescription", "mapName", "copyrightText", "supportedImageFormatTypes",
            "singleFusedMapCache", "tileInfo", "initialExtent", "fullExtent", "units", "supportedExtensions",
        ):
            if key in service_info:
                interesting_service[key] = service_info[key]

    report = {
        "schema_version": 1,
        "item_id": ITEM_ID,
        "item": {
            "title": item.get("title"),
            "type": item.get("type"),
            "url": item.get("url"),
            "access": item.get("access"),
            "licenseInfo": item.get("licenseInfo"),
            "accessInformation": item.get("accessInformation"),
            "typeKeywords": item.get("typeKeywords"),
        },
        "data": interesting_data,
        "service": interesting_service,
        "raw_data_keys": sorted(data.keys()),
        "note": "Metadata-only probe; no imagery tiles are downloaded or redistributed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
