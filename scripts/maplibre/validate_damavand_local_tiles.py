#!/usr/bin/env python3
"""Quality gates for the self-hosted MapLibre Damavand dataset."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

MAX_MERCATOR_LAT = 85.0511287798066
SUMMIT_LAT = 35.9513
SUMMIT_LON = 52.1097


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("public/tiles/maplibre/damavand"))
    return parser.parse_args()


def tile_and_pixel(lon: float, lat: float, zoom: int, size: int) -> tuple[int, int, int, int]:
    count = 1 << zoom
    x_float = (lon + 180.0) / 360.0 * count
    lat = max(-MAX_MERCATOR_LAT, min(MAX_MERCATOR_LAT, lat))
    lat_rad = math.radians(lat)
    y_float = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) * 0.5 * count
    x = int(math.floor(x_float))
    y = int(math.floor(y_float))
    px = min(size - 1, max(0, int(math.floor((x_float - x) * size))))
    py = min(size - 1, max(0, int(math.floor((y_float - y) * size))))
    return x, y, px, py


def decode_terrarium(rgb: np.ndarray) -> float:
    return float(rgb[0]) * 256.0 + float(rgb[1]) + float(rgb[2]) / 256.0 - 32768.0


def main() -> None:
    args = parse_args()
    manifest_path = args.dataset / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit("missing MapLibre manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("peak_id") != "damavand":
        raise SystemExit("unexpected peak id")
    if manifest.get("tile_size") not in (256, 512):
        raise SystemExit("unsupported tile size")
    if manifest.get("max_zoom", 0) < 14:
        raise SystemExit("terrain pyramid does not reach the required visual LOD")
    if manifest.get("terrain", {}).get("encoding") != "terrarium":
        raise SystemExit("DEM must use token-free Terrarium encoding")
    policy = manifest.get("runtime_policy", {})
    if policy.get("api_key_required") is not False or policy.get("external_runtime_tile_requests") is not False:
        raise SystemExit("runtime policy is not fully self-hosted")

    satellite_template = str(manifest["satellite"]["tile_template"])
    terrain_template = str(manifest["terrain"]["tile_template"])
    if satellite_template.startswith("http") or terrain_template.startswith("http"):
        raise SystemExit("runtime tile templates must be local paths")

    satellite_files = list((args.dataset / "satellite").rglob("*.webp"))
    dem_files = list((args.dataset / "dem").rglob("*.png"))
    generated = manifest["generated"]
    if len(satellite_files) != int(generated["satellite_tiles"]):
        raise SystemExit("satellite tile count mismatch")
    if len(dem_files) != int(generated["dem_tiles"]):
        raise SystemExit("DEM tile count mismatch")
    if not satellite_files or not dem_files:
        raise SystemExit("empty tile pyramid")

    zoom = int(manifest["max_zoom"])
    size = int(manifest["tile_size"])
    x, y, px, py = tile_and_pixel(SUMMIT_LON, SUMMIT_LAT, zoom, size)
    dem_path = args.dataset / "dem" / str(zoom) / str(x) / f"{y}.png"
    sat_path = args.dataset / "satellite" / str(zoom) / str(x) / f"{y}.webp"
    if not dem_path.exists() or not sat_path.exists():
        raise SystemExit("summit tile is missing at maximum source zoom")

    dem = np.asarray(Image.open(dem_path).convert("RGB"), dtype=np.uint8)
    summit_height = decode_terrarium(dem[py, px])
    if not 5000.0 <= summit_height <= 5700.0:
        raise SystemExit(f"implausible summit DEM sample: {summit_height:.1f} m")

    satellite = np.asarray(Image.open(sat_path).convert("RGBA"), dtype=np.uint8)
    if satellite[py, px, 3] < 240:
        raise SystemExit("summit satellite pixel is unexpectedly transparent")
    opaque = satellite[:, :, 3] > 240
    if opaque.mean() < 0.20:
        raise SystemExit("summit satellite tile has too little valid coverage")
    valid_rgb = satellite[:, :, :3][opaque]
    if float(valid_rgb.std()) < 8.0:
        raise SystemExit("summit satellite tile lacks expected image variation")

    total_bytes = sum(path.stat().st_size for path in args.dataset.rglob("*") if path.is_file())
    print(
        f"validated MapLibre dataset: {len(satellite_files)} satellite + {len(dem_files)} DEM tiles; "
        f"summit={summit_height:.1f} m; size={total_bytes / 1024 / 1024:.2f} MiB",
        flush=True,
    )


if __name__ == "__main__":
    main()
