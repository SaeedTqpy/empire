#!/usr/bin/env python3
"""Prefetch public Skadi HGT tiles concurrently into the terrain cache.

The mesh builder deliberately remains deterministic and network-agnostic once
its cache is populated. This helper only accelerates the I/O boundary used by
CI and local builds.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

EARTH_RADIUS_M = 6_371_008.8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path, default=Path(".terrain-cache"))
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def bbox_around(lat: float, lon: float, extent_km: float) -> tuple[float, float, float, float]:
    half_m = extent_km * 500.0
    dlat = math.degrees(half_m / EARTH_RADIUS_M)
    dlon = math.degrees(half_m / (EARTH_RADIUS_M * math.cos(math.radians(lat))))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def required_tiles(bbox: tuple[float, float, float, float]) -> list[tuple[int, int]]:
    west, south, east, north = bbox
    lat_min = math.floor(south)
    lat_max = math.floor(north - 1e-12)
    lon_min = math.floor(west)
    lon_max = math.floor(east - 1e-12)
    return [(lat0, lon0) for lat0 in range(lat_min, lat_max + 1) for lon0 in range(lon_min, lon_max + 1)]


def tile_parts(lat0: int, lon0: int) -> tuple[str, str]:
    lat_band = f"{'N' if lat0 >= 0 else 'S'}{abs(lat0):02d}"
    lon_band = f"{'E' if lon0 >= 0 else 'W'}{abs(lon0):03d}"
    return lat_band, f"{lat_band}{lon_band}"


def fetch_one(url: str, destination: Path, retries: int = 3) -> tuple[str, int, bool]:
    if destination.exists() and destination.stat().st_size > 0:
        return destination.name, destination.stat().st_size, True

    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "iran-3d-peaks-terrain-builder/1.0"})
    last_error: Exception | None = None

    for attempt in range(retries):
        temp = destination.with_suffix(destination.suffix + ".part")
        try:
            with urllib.request.urlopen(request, timeout=45) as response, temp.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            temp.replace(destination)
            return destination.name, destination.stat().st_size, False
        except Exception as exc:
            last_error = exc
            temp.unlink(missing_ok=True)
            if attempt + 1 < retries:
                time.sleep(2**attempt)

    raise RuntimeError(f"Failed to download {url}: {last_error}")


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    center = config["center"]
    bbox = bbox_around(float(center["lat"]), float(center["lon"]), float(config["extent_km"]))
    template = config["source"]["url_template"]

    tasks: list[tuple[str, Path]] = []
    for lat0, lon0 in required_tiles(bbox):
        lat_band, tile = tile_parts(lat0, lon0)
        url = template.format(lat_band=lat_band, tile=tile)
        tasks.append((url, args.cache_dir / f"{tile}.hgt.gz"))

    print(f"Prefetching {len(tasks)} DEM tiles with {args.workers} workers", flush=True)
    total_bytes = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(fetch_one, url, path): (url, path) for url, path in tasks}
        for future in as_completed(futures):
            name, size, cached = future.result()
            total_bytes += size
            state = "cached" if cached else "downloaded"
            print(f"{state}: {name} ({size / 1024 / 1024:.1f} MiB)", flush=True)

    print(f"DEM cache ready: {total_bytes / 1024 / 1024:.1f} MiB", flush=True)


if __name__ == "__main__":
    main()
