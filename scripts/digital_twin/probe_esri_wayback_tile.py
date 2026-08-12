#!/usr/bin/env python3
"""Validate the exact public Wayback runtime tile endpoint at Damavand.

The probe downloads two *single* summit tiles only to verify the ArcGIS item
metadata, response type and browser CORS behavior. It never persists imagery.
"""

from __future__ import annotations

import hashlib
import json
import math
import urllib.request

LON = 52.1097
LAT = 35.9513
ZOOM = 18
TEMPLATES = {
    "item_template": "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/22869/{z}/{y}/{x}",
    "wmts_info": "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/8249/{z}/{y}/{x}",
}


def slippy(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    n = 2**zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y


def main() -> None:
    x, y = slippy(LON, LAT, ZOOM)
    report = {"zoom": ZOOM, "x": x, "y": y, "responses": {}}
    for key, template in TEMPLATES.items():
        url = template.format(z=ZOOM, x=x, y=y)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Iran-3D-Peaks/phase8-runtime-probe", "Origin": "http://localhost:3001"},
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read()
                headers = response.headers
                report["responses"][key] = {
                    "status": response.status,
                    "final_url": response.geturl(),
                    "content_type": headers.get("Content-Type"),
                    "content_length": len(body),
                    "cors": headers.get("Access-Control-Allow-Origin"),
                    "cache_control": headers.get("Cache-Control"),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "signature_hex": body[:16].hex(),
                }
        except Exception as exc:
            report["responses"][key] = {"error": repr(exc), "url": url}
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
