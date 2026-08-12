#!/usr/bin/env python3
"""Probe the official NASA/JSC GeoTIFF for the Damavand astronaut photo.

This script deliberately measures the delivered geospatial raster instead of
inferring detail from the JPEG pixel dimensions. Phase 8 only accepts a source
as a higher-detail layer when its actual georeferencing, coverage and measured
pixel footprint support that claim.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import tempfile
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import rasterio
from rasterio.warp import transform_bounds

DEFAULT_PAGE = "https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?frame=265&mission=ISS072&roll=E"
DAMAVAND_BBOX = (51.94305968192662, 35.81640194544132, 52.27634031807337, 36.086198054558686)
EARTH_RADIUS_M = 6_371_008.8


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.href: str | None = None
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self.href = dict(attrs).get("href")
        self.text = []

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.href is not None:
            self.links.append((self.href, " ".join(self.text).strip()))
            self.href = None
            self.text = []


def request_bytes(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Iran-3D-Peaks/phase8-source-probe (+https://github.com/SaeedTqpy/empire)",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read(), response.geturl()


def discover_geotiff(page_url: str) -> str:
    payload, final_url = request_bytes(page_url)
    parser = LinkParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    candidates: list[str] = []
    for href, text in parser.links:
        marker = f"{text} {href}".lower()
        if "geotiff" in marker or ".tif" in marker or ".tiff" in marker:
            candidates.append(urljoin(final_url, href))
    if not candidates:
        raise SystemExit("NASA/JSC page did not expose a GeoTIFF download link")
    # Prefer the anchor explicitly labelled as a GeoTIFF download.
    candidates.sort(key=lambda value: ("geotiff" not in value.lower(), len(value)))
    return candidates[0]


def materialize_raster(download_url: str, work_dir: Path) -> tuple[Path, str, int]:
    payload, final_url = request_bytes(download_url)
    raw_path = work_dir / "nasa-download"
    raw_path.write_bytes(payload)
    size = len(payload)

    if payload[:4] == b"PK\x03\x04":
        archive = work_dir / "nasa-geotiff.zip"
        raw_path.replace(archive)
        with zipfile.ZipFile(archive) as zf:
            names = [name for name in zf.namelist() if name.lower().endswith((".tif", ".tiff"))]
            if not names:
                raise SystemExit("NASA GeoTIFF ZIP contained no .tif/.tiff file")
            target = work_dir / Path(names[0]).name
            with zf.open(names[0]) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
        return target, final_url, size

    # TIFF byte order signatures: II*\0 or MM\0*.
    if payload[:4] not in (b"II*\x00", b"MM\x00*"):
        head = payload[:120].decode("utf-8", errors="replace")
        raise SystemExit(f"GeoTIFF link returned an unsupported payload: {head!r}")
    tif = work_dir / "nasa-geotiff.tif"
    raw_path.replace(tif)
    return tif, final_url, size


def approx_pixel_m(ds: rasterio.io.DatasetReader, bounds4326: tuple[float, float, float, float]) -> tuple[float, float]:
    west, south, east, north = bounds4326
    center_lat = (south + north) * 0.5
    width_m = EARTH_RADIUS_M * math.cos(math.radians(center_lat)) * math.radians(east - west)
    height_m = EARTH_RADIUS_M * math.radians(north - south)
    return abs(width_m / ds.width), abs(height_m / ds.height)


def overlap_fraction(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    aw, as_, ae, an = a
    bw, bs, be, bn = b
    iw = max(0.0, min(ae, be) - max(aw, bw))
    ih = max(0.0, min(an, bn) - max(as_, bs))
    area = max(0.0, (ae - aw) * (an - as_))
    return 0.0 if area == 0 else (iw * ih) / area


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", default=DEFAULT_PAGE)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    geotiff_url = discover_geotiff(args.page)
    print(f"NASA GeoTIFF link: {geotiff_url}", flush=True)

    with tempfile.TemporaryDirectory(prefix="damavand-nasa-") as tmp:
        raster_path, final_download_url, download_bytes = materialize_raster(geotiff_url, Path(tmp))
        with rasterio.open(raster_path) as ds:
            if ds.crs is None:
                gcps, gcp_crs = ds.gcps
                if not gcps or gcp_crs is None:
                    raise SystemExit("NASA raster has neither a CRS transform nor georeferenced GCPs")
                raise SystemExit("NASA raster is GCP-only; Phase 8 requires an explicit orthorectification step before use")

            bounds4326 = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds, densify_pts=21)
            pixel_x_m, pixel_y_m = approx_pixel_m(ds, bounds4326)
            overlap = overlap_fraction(DAMAVAND_BBOX, bounds4326)
            observed_gsd_m = max(pixel_x_m, pixel_y_m)
            qualifies_as_detail = overlap >= 0.80 and observed_gsd_m < 10.0

            report = {
                "schema_version": 1,
                "source": "NASA/JSC Gateway to Astronaut Photography of Earth",
                "photo_id": "ISS072-E-265",
                "photo_page": args.page,
                "geotiff_url": final_download_url,
                "download_bytes": download_bytes,
                "driver": ds.driver,
                "width": ds.width,
                "height": ds.height,
                "bands": ds.count,
                "dtype": list(ds.dtypes),
                "crs": ds.crs.to_string(),
                "bounds_native": list(ds.bounds),
                "bounds_wgs84": list(bounds4326),
                "approx_pixel_m": {"x": round(pixel_x_m, 3), "y": round(pixel_y_m, 3)},
                "observed_gsd_m_conservative": round(observed_gsd_m, 3),
                "damavand_30km_overlap_fraction": round(overlap, 5),
                "qualifies_as_sub_sentinel_detail": qualifies_as_detail,
                "qualification_rule": "coverage >= 80% of the 30 km Damavand bbox and conservative pixel footprint < 10 m",
                "caveat": "A georeferenced astronaut photograph is not automatically equivalent to a survey-grade orthophoto; geometric accuracy must be validated before terrain draping.",
            }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
