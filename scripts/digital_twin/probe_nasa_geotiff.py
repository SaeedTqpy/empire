#!/usr/bin/env python3
"""Probe the official NASA/JSC GeoTIFF for the Damavand astronaut photo.

The probe measures the delivered geospatial raster instead of inferring detail
from the JPEG pixel dimensions. Phase 8 only accepts a source as higher detail
when georeferencing, coverage and measured pixel footprint support the claim.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import math
import re
import shutil
import tempfile
import time
import urllib.error
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
USER_AGENT = "Iran-3D-Peaks/phase8-source-probe (+https://github.com/SaeedTqpy/empire)"


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


def make_session() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request_bytes(
    session: urllib.request.OpenerDirector,
    url: str,
    *,
    referer: str | None = None,
    attempts: int = 6,
) -> tuple[bytes, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.8",
        "Connection": "close",
    }
    if referer:
        headers["Referer"] = referer

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with session.open(request, timeout=120) as response:
                return response.read(), response.geturl()
        except urllib.error.HTTPError as exc:
            last_error = exc
            retryable = exc.code in {429, 500, 502, 503, 504}
            if not retryable or attempt == attempts:
                raise
            delay = min(20.0, 1.5 * (2 ** (attempt - 1)))
            print(f"NASA endpoint returned HTTP {exc.code}; retry {attempt}/{attempts} after {delay:.1f}s", flush=True)
            time.sleep(delay)
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt == attempts:
                raise
            delay = min(20.0, 1.5 * (2 ** (attempt - 1)))
            print(f"NASA endpoint network error {exc}; retry {attempt}/{attempts} after {delay:.1f}s", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"NASA request failed after retries: {last_error}")


def discover_geotiff(
    session: urllib.request.OpenerDirector,
    page_url: str,
) -> tuple[str, str]:
    payload, final_url = request_bytes(session, page_url)
    html = payload.decode("utf-8", errors="replace")
    parser = LinkParser()
    parser.feed(html)
    candidates: list[str] = []
    for href, text in parser.links:
        marker = f"{text} {href}".lower()
        if "geotiff" in marker or ".tif" in marker or ".tiff" in marker:
            candidates.append(urljoin(final_url, href))

    # JSC currently exposes GeoTIFF through a JavaScript onclick on a div.
    if not candidates:
        for match in re.finditer(r"geotiff", html, flags=re.IGNORECASE):
            snippet = html[max(0, match.start() - 900) : min(len(html), match.end() + 1400)]
            for quoted in re.findall(r"[\"']([^\"']+)[\"']", snippet):
                lower = quoted.lower()
                if "geotiff" in lower or ".tif" in lower or ".tiff" in lower:
                    if not lower.startswith(("javascript:", "#")):
                        candidates.append(urljoin(final_url, quoted.replace("&amp;", "&")))

    if not candidates:
        raise SystemExit("NASA/JSC page advertised no resolvable GeoTIFF endpoint")

    unique = list(dict.fromkeys(candidates))
    unique.sort(key=lambda value: (not value.lower().endswith((".tif", ".tiff", ".zip")), len(value)))
    print("NASA GeoTIFF candidates:", *unique, sep="\n  - ", flush=True)
    return unique[0], final_url


def materialize_raster(
    session: urllib.request.OpenerDirector,
    download_url: str,
    work_dir: Path,
    *,
    referer: str,
) -> tuple[Path, str, int]:
    payload, final_url = request_bytes(session, download_url, referer=referer)
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

    if payload[:4] not in (b"II*\x00", b"MM\x00*"):
        head = payload[:240].decode("utf-8", errors="replace")
        raise SystemExit(f"GeoTIFF endpoint returned unsupported payload from {final_url}: {head!r}")
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

    session = make_session()
    geotiff_url, page_url = discover_geotiff(session, args.page)
    print(f"Selected NASA GeoTIFF endpoint: {geotiff_url}", flush=True)

    with tempfile.TemporaryDirectory(prefix="damavand-nasa-") as tmp:
        raster_path, final_download_url, download_bytes = materialize_raster(
            session,
            geotiff_url,
            Path(tmp),
            referer=page_url,
        )
        with rasterio.open(raster_path) as ds:
            if ds.crs is None:
                gcps, gcp_crs = ds.gcps
                if not gcps or gcp_crs is None:
                    raise SystemExit("NASA raster has neither a CRS transform nor georeferenced GCPs")
                raise SystemExit("NASA raster is GCP-only; explicit orthorectification is required before use")

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
                "caveat": "A georeferenced astronaut photograph is not automatically survey-grade orthophotography; geometric accuracy must be validated before terrain draping.",
            }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
