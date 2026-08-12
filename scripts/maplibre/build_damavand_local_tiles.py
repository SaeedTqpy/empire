#!/usr/bin/env python3
"""Build token-free MapLibre XYZ imagery + Terrarium DEM tiles for Damavand.

The pipeline intentionally does not download or cache Mapbox assets. It turns
our existing open-source terrain contract and Copernicus authoring master into
standard web-mercator tiles that MapLibre GL JS can render natively.

Output contract:
  public/tiles/maplibre/damavand/
    manifest.json
    satellite/{z}/{x}/{y}.webp
    dem/{z}/{x}/{y}.png       # Mapzen Terrarium encoding
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.terrain.build_peak_terrain import (  # noqa: E402
    bilinear_from_tile,
    download,
    read_hgt,
    repair_small_grid_voids,
    required_tiles,
    tile_parts,
)

WEB_MERCATOR_HALF_WORLD = 20_037_508.342789244
MAX_MERCATOR_LAT = 85.0511287798066


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terrain-config", type=Path, default=Path("scripts/terrain/damavand.json"))
    parser.add_argument("--terrain-manifest", type=Path, default=Path("public/models/damavand.terrain.json"))
    parser.add_argument("--imagery-manifest", type=Path, default=Path("public/models/damavand.imagery.json"))
    parser.add_argument("--imagery-master", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("public/tiles/maplibre/damavand"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".terrain-cache"))
    parser.add_argument("--min-zoom", type=int, default=8)
    parser.add_argument("--max-zoom", type=int, default=14)
    parser.add_argument("--tile-size", type=int, default=512)
    parser.add_argument("--webp-quality", type=int, default=92)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def clamp_lat(lat: float) -> float:
    return max(-MAX_MERCATOR_LAT, min(MAX_MERCATOR_LAT, lat))


def lon_to_tile_x(lon: float, zoom: int) -> int:
    count = 1 << zoom
    return max(0, min(count - 1, int(math.floor((lon + 180.0) / 360.0 * count))))


def lat_to_tile_y(lat: float, zoom: int) -> int:
    count = 1 << zoom
    lat_rad = math.radians(clamp_lat(lat))
    value = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) * 0.5 * count
    return max(0, min(count - 1, int(math.floor(value))))


def tile_ranges(bounds: tuple[float, float, float, float], zoom: int) -> tuple[range, range]:
    west, south, east, north = bounds
    x0 = lon_to_tile_x(west, zoom)
    x1 = lon_to_tile_x(east - 1e-12, zoom)
    y0 = lat_to_tile_y(north - 1e-12, zoom)
    y1 = lat_to_tile_y(south + 1e-12, zoom)
    return range(x0, x1 + 1), range(y0, y1 + 1)


def tile_mercator_bounds(x: int, y: int, zoom: int) -> tuple[float, float, float, float]:
    count = 1 << zoom
    span = 2.0 * WEB_MERCATOR_HALF_WORLD / count
    minx = -WEB_MERCATOR_HALF_WORLD + x * span
    maxx = minx + span
    maxy = WEB_MERCATOR_HALF_WORLD - y * span
    miny = maxy - span
    return minx, miny, maxx, maxy


def tile_lon_lat_grid(x: int, y: int, zoom: int, size: int) -> tuple[np.ndarray, np.ndarray]:
    count = float(1 << zoom)
    pixel = (np.arange(size, dtype=np.float64) + 0.5) / float(size)
    x_normalized = (x + pixel) / count
    y_normalized = (y + pixel) / count
    lon_axis = x_normalized * 360.0 - 180.0
    lat_axis = np.degrees(np.arctan(np.sinh(math.pi * (1.0 - 2.0 * y_normalized))))
    lons, lats = np.meshgrid(lon_axis, lat_axis)
    return lons, lats


def load_dem_tiles(config: dict[str, Any], bounds: tuple[float, float, float, float], cache_dir: Path):
    template = config["source"]["url_template"]
    result: dict[tuple[int, int], np.ndarray] = {}
    records: list[dict[str, Any]] = []
    for lat0, lon0 in required_tiles(bounds):
        lat_band, tile_name = tile_parts(lat0, lon0)
        url = template.format(lat_band=lat_band, tile=tile_name)
        target = cache_dir / f"{tile_name}.hgt.gz"
        print(f"DEM source {tile_name}", flush=True)
        download(url, target)
        values = read_hgt(target)
        result[(lat0, lon0)] = values
        records.append({"tile": tile_name, "url": url, "samples_per_side": int(values.shape[0])})
    return result, records


def sample_dem(
    source_tiles: dict[tuple[int, int], np.ndarray],
    lats: np.ndarray,
    lons: np.ndarray,
) -> np.ndarray:
    heights = np.full(lats.shape, np.nan, dtype=np.float32)
    lat_keys = np.floor(lats + 1e-12).astype(np.int16)
    lon_keys = np.floor(lons + 1e-12).astype(np.int16)
    for (lat0, lon0), tile in source_tiles.items():
        mask = (lat_keys == lat0) & (lon_keys == lon0)
        if mask.any():
            heights[mask] = bilinear_from_tile(tile, lat0, lon0, lats[mask], lons[mask])
    if (~np.isfinite(heights)).any():
        heights = repair_small_grid_voids(heights)
    return heights


def encode_terrarium(heights: np.ndarray) -> np.ndarray:
    # Terrarium decoding: elevation = (R * 256 + G + B / 256) - 32768.
    fixed = np.rint((heights.astype(np.float64) + 32768.0) * 256.0).astype(np.int64)
    fixed = np.clip(fixed, 0, (1 << 24) - 1)
    rgb = np.empty((*heights.shape, 3), dtype=np.uint8)
    rgb[:, :, 0] = (fixed >> 16) & 0xFF
    rgb[:, :, 1] = (fixed >> 8) & 0xFF
    rgb[:, :, 2] = fixed & 0xFF
    return rgb


def save_dem_tile(path: Path, heights: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(encode_terrarium(heights), mode="RGB").save(path, format="PNG", optimize=True, compress_level=7)


def load_imagery_master(path: Path) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    return np.asarray(image, dtype=np.uint8)


def build_satellite_tile(
    source_rgb: np.ndarray,
    source_transform: rasterio.Affine,
    tile_bounds: tuple[float, float, float, float],
    size: int,
) -> np.ndarray:
    destination_transform = from_bounds(*tile_bounds, size, size)
    source_bands = np.moveaxis(source_rgb, 2, 0)
    destination = np.zeros((3, size, size), dtype=np.uint8)
    reproject(
        source=source_bands,
        destination=destination,
        src_transform=source_transform,
        src_crs="EPSG:4326",
        dst_transform=destination_transform,
        dst_crs="EPSG:3857",
        src_nodata=None,
        dst_nodata=0,
        resampling=Resampling.lanczos,
        num_threads=2,
    )

    source_alpha = np.full(source_rgb.shape[:2], 255, dtype=np.uint8)
    destination_alpha = np.zeros((size, size), dtype=np.uint8)
    reproject(
        source=source_alpha,
        destination=destination_alpha,
        src_transform=source_transform,
        src_crs="EPSG:4326",
        dst_transform=destination_transform,
        dst_crs="EPSG:3857",
        src_nodata=0,
        dst_nodata=0,
        resampling=Resampling.nearest,
        num_threads=2,
    )
    rgba = np.empty((size, size, 4), dtype=np.uint8)
    rgba[:, :, :3] = np.moveaxis(destination, 0, 2)
    rgba[:, :, 3] = destination_alpha
    return rgba


def save_satellite_tile(path: Path, rgba: np.ndarray, quality: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(path, format="WEBP", quality=quality, method=6)


def main() -> None:
    args = parse_args()
    if args.min_zoom > args.max_zoom:
        raise SystemExit("min zoom must be <= max zoom")
    if args.tile_size not in (256, 512):
        raise SystemExit("tile size must be 256 or 512")

    terrain_config = load_json(args.terrain_config)
    terrain_manifest = load_json(args.terrain_manifest)
    imagery_manifest = load_json(args.imagery_manifest)
    bbox = terrain_manifest["bbox_wgs84"]
    bounds = (float(bbox["west"]), float(bbox["south"]), float(bbox["east"]), float(bbox["north"]))

    if args.clean and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    source_rgb = load_imagery_master(args.imagery_master)
    source_transform = from_bounds(*bounds, source_rgb.shape[1], source_rgb.shape[0])
    dem_tiles, dem_records = load_dem_tiles(terrain_config, bounds, args.cache_dir)

    satellite_count = 0
    dem_count = 0
    zoom_counts: dict[str, dict[str, int]] = {}

    for zoom in range(args.min_zoom, args.max_zoom + 1):
        xs, ys = tile_ranges(bounds, zoom)
        level_satellite = 0
        level_dem = 0
        print(f"z{zoom}: {len(xs)} x {len(ys)} tiles", flush=True)
        for x in xs:
            for y in ys:
                lons, lats = tile_lon_lat_grid(x, y, zoom, args.tile_size)
                heights = sample_dem(dem_tiles, lats, lons)
                dem_path = args.output_dir / "dem" / str(zoom) / str(x) / f"{y}.png"
                save_dem_tile(dem_path, heights)
                dem_count += 1
                level_dem += 1

                rgba = build_satellite_tile(
                    source_rgb,
                    source_transform,
                    tile_mercator_bounds(x, y, zoom),
                    args.tile_size,
                )
                satellite_path = args.output_dir / "satellite" / str(zoom) / str(x) / f"{y}.webp"
                save_satellite_tile(satellite_path, rgba, args.webp_quality)
                satellite_count += 1
                level_satellite += 1

        zoom_counts[str(zoom)] = {"satellite": level_satellite, "dem": level_dem}

    total_bytes = sum(path.stat().st_size for path in args.output_dir.rglob("*") if path.is_file())
    imagery_source = imagery_manifest["source"]
    manifest = {
        "schema_version": 1,
        "peak_id": terrain_manifest["peak_id"],
        "bounds": list(bounds),
        "tile_size": args.tile_size,
        "min_zoom": args.min_zoom,
        "max_zoom": args.max_zoom,
        "satellite": {
            "tile_template": f"/tiles/maplibre/{terrain_manifest['peak_id']}/satellite/{{z}}/{{x}}/{{y}}.webp",
            "format": "image/webp",
            "attribution": imagery_manifest["attribution"],
            "source_native_resolution_m": imagery_source["native_ground_resolution_m"],
            "source": imagery_source["provider"],
            "detail_policy": "native source detail; no synthetic super-resolution",
        },
        "terrain": {
            "tile_template": f"/tiles/maplibre/{terrain_manifest['peak_id']}/dem/{{z}}/{{x}}/{{y}}.png",
            "format": "image/png",
            "encoding": "terrarium",
            "attribution": terrain_manifest["source"]["attribution"],
            "source_native_resolution_m": 30,
            "source": "Skadi / SRTM 1 arc-second",
        },
        "presentation": {
            "terrain_exaggeration": 1.22,
            "max_pitch": 85,
            "default_zoom": 12.7,
            "default_pitch": 78,
            "default_bearing": -34,
        },
        "generated": {
            "satellite_tiles": satellite_count,
            "dem_tiles": dem_count,
            "zoom_counts": zoom_counts,
            "asset_bytes_before_manifest": total_bytes,
            "source_dem_tiles": dem_records,
        },
        "runtime_policy": {
            "api_key_required": False,
            "external_runtime_tile_requests": False,
            "renderer": "MapLibre GL JS native raster terrain",
        },
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    final_bytes = sum(path.stat().st_size for path in args.output_dir.rglob("*") if path.is_file())
    print(
        f"MapLibre dataset complete: {satellite_count} satellite + {dem_count} DEM tiles, "
        f"{final_bytes / 1024 / 1024:.2f} MiB",
        flush=True,
    )


if __name__ == "__main__":
    main()
