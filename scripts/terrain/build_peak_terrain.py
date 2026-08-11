#!/usr/bin/env python3
"""Build a georeferenced mountain terrain GLB from public Skadi HGT tiles.

Coordinate contract used by Iran 3D Peaks:
  +X = east
  +Y = elevation
  +Z = north
  UV (0, 0) = south-west, UV (1, 1) = north-east

The output stays in real metre proportions. ViewerEngine may normalize the
footprint for presentation, but the mountain's vertical ratio remains real.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import time
import urllib.request
from pathlib import Path

import numpy as np
import trimesh
from trimesh.visual.material import SimpleMaterial
from trimesh.visual.texture import TextureVisuals

EARTH_RADIUS_M = 6_371_008.8
VOID = -32768


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path, default=Path(".terrain-cache"))
    return parser.parse_args()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def bbox_around(lat: float, lon: float, extent_km: float) -> tuple[float, float, float, float]:
    half_m = extent_km * 500.0
    dlat = math.degrees(half_m / EARTH_RADIUS_M)
    dlon = math.degrees(half_m / (EARTH_RADIUS_M * math.cos(math.radians(lat))))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def tile_parts(lat0: int, lon0: int) -> tuple[str, str]:
    lat_band = f"{'N' if lat0 >= 0 else 'S'}{abs(lat0):02d}"
    lon_band = f"{'E' if lon0 >= 0 else 'W'}{abs(lon0):03d}"
    return lat_band, f"{lat_band}{lon_band}"


def required_tiles(bbox: tuple[float, float, float, float]) -> list[tuple[int, int]]:
    west, south, east, north = bbox
    lat_min = math.floor(south)
    lat_max = math.floor(north - 1e-12)
    lon_min = math.floor(west)
    lon_max = math.floor(east - 1e-12)
    return [(lat0, lon0) for lat0 in range(lat_min, lat_max + 1) for lon0 in range(lon_min, lon_max + 1)]


def download(url: str, destination: Path, retries: int = 4) -> None:
    if destination.exists() and destination.stat().st_size > 0:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "iran-3d-peaks-terrain-builder/1.0"})
    error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            return
        except Exception as exc:
            error = exc
            destination.unlink(missing_ok=True)
            time.sleep(2**attempt)
    raise RuntimeError(f"Failed to download {url}: {error}")


def read_hgt(path: Path) -> np.ndarray:
    with gzip.open(path, "rb") as handle:
        raw = handle.read()
    samples = len(raw) // 2
    side = math.isqrt(samples)
    if side * side != samples:
        raise ValueError(f"Unexpected HGT byte length for {path}: {len(raw)}")
    return np.frombuffer(raw, dtype=">i2").reshape(side, side).astype(np.float32)


def bilinear_from_tile(tile: np.ndarray, lat0: int, lon0: int, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    n = tile.shape[0]
    x = np.clip((lons - lon0) * (n - 1), 0.0, n - 1.0)
    y = np.clip((lat0 + 1.0 - lats) * (n - 1), 0.0, n - 1.0)

    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.minimum(x0 + 1, n - 1)
    y1 = np.minimum(y0 + 1, n - 1)
    fx = x - x0
    fy = y - y0

    q00 = tile[y0, x0]
    q10 = tile[y0, x1]
    q01 = tile[y1, x0]
    q11 = tile[y1, x1]
    sampled = (
        q00 * (1.0 - fx) * (1.0 - fy)
        + q10 * fx * (1.0 - fy)
        + q01 * (1.0 - fx) * fy
        + q11 * fx * fy
    )
    invalid = (q00 == VOID) | (q10 == VOID) | (q01 == VOID) | (q11 == VOID)
    sampled[invalid] = np.nan
    return sampled


def repair_small_grid_voids(values: np.ndarray) -> np.ndarray:
    result = values.copy()
    for _ in range(16):
        bad = ~np.isfinite(result)
        if not bad.any():
            return result
        total = np.zeros_like(result, dtype=np.float64)
        count = np.zeros_like(result, dtype=np.uint8)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            shifted = np.roll(result, shift=(dy, dx), axis=(0, 1))
            valid = np.isfinite(shifted)
            if dy == -1:
                valid[-1, :] = False
            elif dy == 1:
                valid[0, :] = False
            if dx == -1:
                valid[:, -1] = False
            elif dx == 1:
                valid[:, 0] = False
            total[valid] += shifted[valid]
            count[valid] += 1
        fill = bad & (count > 0)
        result[fill] = (total[fill] / count[fill]).astype(np.float32)
    if (~np.isfinite(result)).any():
        raise ValueError("DEM still contains voids after repair")
    return result


def sample_dem(config: dict, bbox: tuple[float, float, float, float], cache_dir: Path) -> tuple[np.ndarray, list[dict]]:
    grid_size = int(config["grid_size"])
    west, south, east, north = bbox
    lat_axis = np.linspace(north, south, grid_size, dtype=np.float64)
    lon_axis = np.linspace(west, east, grid_size, dtype=np.float64)
    lons, lats = np.meshgrid(lon_axis, lat_axis)
    heights = np.full((grid_size, grid_size), np.nan, dtype=np.float32)
    tile_records: list[dict] = []

    template = config["source"]["url_template"]
    tile_key_lat = np.floor(lats + 1e-12).astype(np.int16)
    tile_key_lon = np.floor(lons + 1e-12).astype(np.int16)

    for lat0, lon0 in required_tiles(bbox):
        lat_band, tile = tile_parts(lat0, lon0)
        url = template.format(lat_band=lat_band, tile=tile)
        target = cache_dir / f"{tile}.hgt.gz"
        print(f"DEM tile: {tile}", flush=True)
        download(url, target)
        data = read_hgt(target)
        mask = (tile_key_lat == lat0) & (tile_key_lon == lon0)
        if mask.any():
            heights[mask] = bilinear_from_tile(data, lat0, lon0, lats[mask], lons[mask])
        tile_records.append({"tile": tile, "url": url, "samples_per_side": int(data.shape[0])})

    if (~np.isfinite(heights)).any():
        heights = repair_small_grid_voids(heights)
    return heights, tile_records


def heightfield_normals(y: np.ndarray, x_axis: np.ndarray, z_axis: np.ndarray) -> np.ndarray:
    """Return smooth unit normals directly from the regular height field.

    Generic mesh adjacency is unnecessary for a regular DEM grid and becomes
    disproportionately expensive as triangle density grows. Gradients preserve
    the same physical metre scale while keeping the build O(number of samples).
    """
    dy_dz, dy_dx = np.gradient(y, z_axis, x_axis, edge_order=2)
    normals = np.stack((-dy_dx, np.ones_like(y), -dy_dz), axis=-1)
    lengths = np.linalg.norm(normals, axis=-1, keepdims=True)
    normals /= np.maximum(lengths, 1e-12)
    return normals.reshape(-1, 3).astype(np.float32)


def build_top_mesh(
    heights: np.ndarray,
    bbox: tuple[float, float, float, float],
    base_elevation: float,
    color: list[float],
) -> trimesh.Trimesh:
    n = heights.shape[0]
    west, south, east, north = bbox
    center_lat = (south + north) * 0.5
    center_lon = (west + east) * 0.5

    lon_axis = np.linspace(west, east, n, dtype=np.float64)
    lat_axis = np.linspace(north, south, n, dtype=np.float64)
    x_axis = EARTH_RADIUS_M * math.cos(math.radians(center_lat)) * np.radians(lon_axis - center_lon)
    z_axis = EARTH_RADIUS_M * np.radians(lat_axis - center_lat)
    x, z = np.meshgrid(x_axis, z_axis)
    y = heights.astype(np.float64) - base_elevation

    vertices = np.column_stack((x.ravel(), y.ravel(), z.ravel())).astype(np.float32)
    rows, cols = np.meshgrid(np.arange(n - 1), np.arange(n - 1), indexing="ij")
    a = (rows * n + cols).ravel()
    b = a + 1
    c = ((rows + 1) * n + cols).ravel()
    d = c + 1
    faces = np.vstack((np.column_stack((a, b, c)), np.column_stack((b, d, c)))).astype(np.int32)

    u = np.tile(np.linspace(0.0, 1.0, n, dtype=np.float32), n)
    v = np.repeat(np.linspace(1.0, 0.0, n, dtype=np.float32), n)
    uv = np.column_stack((u, v))

    rgba = np.clip(np.asarray(color) * 255.0, 0, 255).astype(np.uint8)
    material = SimpleMaterial(diffuse=rgba, glossiness=0.0)
    visual = TextureVisuals(uv=uv, material=material)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, visual=visual, process=False)
    mesh.metadata["name"] = "Damavand Terrain"
    mesh.vertex_normals = heightfield_normals(y, x_axis, z_axis)
    return mesh


def build_skirt(top: trimesh.Trimesh, n: int) -> trimesh.Trimesh:
    north = list(range(0, n))
    east = [row * n + (n - 1) for row in range(1, n)]
    south = list(range(n * n - 2, n * (n - 1) - 1, -1))
    west = [row * n for row in range(n - 2, 0, -1)]
    perimeter = np.asarray(north + east + south + west, dtype=np.int32)

    top_ring = np.asarray(top.vertices)[perimeter].astype(np.float32)
    bottom_ring = top_ring.copy()
    bottom_ring[:, 1] = 0.0
    vertices = np.vstack((top_ring, bottom_ring))
    count = len(top_ring)

    faces: list[list[int]] = []
    for i in range(count):
        j = (i + 1) % count
        faces.append([i, i + count, j])
        faces.append([j, i + count, j + count])

    colors = np.tile(np.array([82, 87, 89, 255], dtype=np.uint8), (len(vertices), 1))
    mesh = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces, dtype=np.int32), vertex_colors=colors, process=False)
    mesh.metadata["name"] = "Terrain Skirt"
    _ = mesh.vertex_normals
    return mesh


def export_scene(top: trimesh.Trimesh, skirt: trimesh.Trimesh, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    scene = trimesh.Scene()
    scene.add_geometry(top, geom_name="terrain", node_name="terrain")
    scene.add_geometry(skirt, geom_name="skirt", node_name="skirt")
    payload = scene.export(file_type="glb")
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("Expected GLB export to return bytes")
    output.write_bytes(payload)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    center = config["center"]
    bbox = bbox_around(float(center["lat"]), float(center["lon"]), float(config["extent_km"]))
    print(f"Building {config['name']} bbox={bbox} grid={config['grid_size']}x{config['grid_size']}", flush=True)

    heights, tiles = sample_dem(config, bbox, args.cache_dir)
    elevation_min = float(np.min(heights))
    elevation_max = float(np.max(heights))
    base_elevation = math.floor(elevation_min - float(config.get("base_depth_m", 100.0)))
    print(f"DEM sampled: {elevation_min:.1f}..{elevation_max:.1f} m", flush=True)

    top = build_top_mesh(heights, bbox, base_elevation, config["material"]["base_color"])
    print(f"Top mesh: {len(top.vertices)} vertices / {len(top.faces)} triangles", flush=True)
    skirt = build_skirt(top, int(config["grid_size"]))
    export_scene(top, skirt, args.output)

    west, south, east, north = bbox
    manifest = {
        "schema_version": 1,
        "peak_id": config["id"],
        "source": config["source"],
        "source_tiles": tiles,
        "center": center,
        "bbox_wgs84": {"west": west, "south": south, "east": east, "north": north},
        "extent_km": config["extent_km"],
        "grid_size": config["grid_size"],
        "terrain_triangles": int(len(top.faces)),
        "skirt_triangles": int(len(skirt.faces)),
        "elevation_m": {
            "min_sampled": round(elevation_min, 2),
            "max_sampled": round(elevation_max, 2),
            "base": base_elevation,
        },
        "coordinate_contract": {
            "units": "meters",
            "x": "east",
            "y": "elevation_above_base",
            "z": "north",
            "uv": "u west-to-east; v south-to-north",
        },
        "model": {
            "path": "/models/damavand.glb",
            "satellite_texture": "phase-3",
            "vertical_exaggeration": 1.0,
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"Wrote {args.output} ({args.output.stat().st_size / 1024 / 1024:.2f} MiB raw), "
        f"elevation {elevation_min:.1f}..{elevation_max:.1f} m",
        flush=True,
    )


if __name__ == "__main__":
    main()
