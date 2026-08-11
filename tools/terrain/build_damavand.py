from __future__ import annotations

import json
import math
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
import trimesh

CENTER_LAT = 35.9513
CENTER_LON = 52.1097
HALF_SIZE_M = 15_000.0
EARTH_RADIUS_M = 6_378_137.0
ZOOM = 12
TILE_SIZE = 256
GRID_SIZE = 513
SOURCE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / ".cache" / "terrain" / "damavand"
RAW_GLB = ROOT / ".cache" / "terrain" / "damavand-raw.glb"
META_PATH = ROOT / "public" / "models" / "damavand.meta.json"


def lonlat_to_global_pixel(lon: np.ndarray | float, lat: np.ndarray | float, zoom: int):
    n = 2**zoom * TILE_SIZE
    x = (np.asarray(lon) + 180.0) / 360.0 * n
    lat_rad = np.radians(np.asarray(lat))
    y = (1.0 - np.arcsinh(np.tan(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def download_tile(z: int, x: int, y: int) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{z}-{x}-{y}.png"
    if path.exists():
        return path
    url = SOURCE_URL.format(z=z, x=x, y=y)
    req = urllib.request.Request(url, headers={"User-Agent": "iran-3d-peaks-terrain-builder/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response, path.open("wb") as out:
        out.write(response.read())
    return path


def decode_terrarium(path: Path) -> np.ndarray:
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    return rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0


def bilinear_sample(image: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, image.shape[1] - 1)
    y1 = np.clip(y0 + 1, 0, image.shape[0] - 1)
    x0 = np.clip(x0, 0, image.shape[1] - 1)
    y0 = np.clip(y0, 0, image.shape[0] - 1)
    xf = x - x0
    yf = y - y0
    a = image[y0, x0]
    b = image[y0, x1]
    c = image[y1, x0]
    d = image[y1, x1]
    return a * (1 - xf) * (1 - yf) + b * xf * (1 - yf) + c * (1 - xf) * yf + d * xf * yf


def build_height_grid() -> tuple[np.ndarray, dict]:
    cos_lat = math.cos(math.radians(CENTER_LAT))
    dlat = math.degrees(HALF_SIZE_M / EARTH_RADIUS_M)
    dlon = math.degrees(HALF_SIZE_M / (EARTH_RADIUS_M * cos_lat))
    west, east = CENTER_LON - dlon, CENTER_LON + dlon
    south, north = CENTER_LAT - dlat, CENTER_LAT + dlat

    px_w, py_n = lonlat_to_global_pixel(west, north, ZOOM)
    px_e, py_s = lonlat_to_global_pixel(east, south, ZOOM)
    tx0, tx1 = int(math.floor(px_w / TILE_SIZE)), int(math.floor(px_e / TILE_SIZE))
    ty0, ty1 = int(math.floor(py_n / TILE_SIZE)), int(math.floor(py_s / TILE_SIZE))

    rows = []
    for ty in range(ty0, ty1 + 1):
        row = [decode_terrarium(download_tile(ZOOM, tx, ty)) for tx in range(tx0, tx1 + 1)]
        rows.append(np.concatenate(row, axis=1))
    mosaic = np.concatenate(rows, axis=0)

    east_m = np.linspace(-HALF_SIZE_M, HALF_SIZE_M, GRID_SIZE, dtype=np.float64)
    north_m = np.linspace(HALF_SIZE_M, -HALF_SIZE_M, GRID_SIZE, dtype=np.float64)
    xx, nn = np.meshgrid(east_m, north_m)
    lat = CENTER_LAT + np.degrees(nn / EARTH_RADIUS_M)
    lon = CENTER_LON + np.degrees(xx / (EARTH_RADIUS_M * cos_lat))
    gx, gy = lonlat_to_global_pixel(lon, lat, ZOOM)
    local_x = gx - tx0 * TILE_SIZE
    local_y = gy - ty0 * TILE_SIZE
    heights = bilinear_sample(mosaic, local_x, local_y).astype(np.float32)

    if not np.isfinite(heights).all():
        raise RuntimeError("DEM contains invalid values")
    if heights.max() < 5_300 or heights.max() > 5_900:
        raise RuntimeError(f"Unexpected Damavand max elevation: {heights.max():.1f} m")
    if heights.min() < 0 or heights.min() > 4_000:
        raise RuntimeError(f"Unexpected Damavand minimum elevation: {heights.min():.1f} m")

    center_height = float(heights[GRID_SIZE // 2, GRID_SIZE // 2])
    meta = {
        "source": "Mapzen Terrain Tiles on AWS Open Data",
        "source_url_template": SOURCE_URL,
        "zoom": ZOOM,
        "center": {"lat": CENTER_LAT, "lon": CENTER_LON},
        "extent_m": HALF_SIZE_M * 2,
        "bbox": {"west": west, "south": south, "east": east, "north": north},
        "grid_size": GRID_SIZE,
        "triangle_count": (GRID_SIZE - 1) * (GRID_SIZE - 1) * 2,
        "min_elevation_m": float(heights.min()),
        "max_elevation_m": float(heights.max()),
        "center_sample_elevation_m": center_height,
        "vertical_exaggeration": 1.0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tiles": {"x_min": tx0, "x_max": tx1, "y_min": ty0, "y_max": ty1},
    }
    return heights, meta


def build_mesh(heights: np.ndarray) -> trimesh.Trimesh:
    min_h = float(heights.min())
    relief = heights - min_h
    east = np.linspace(-HALF_SIZE_M, HALF_SIZE_M, GRID_SIZE, dtype=np.float32)
    north = np.linspace(HALF_SIZE_M, -HALF_SIZE_M, GRID_SIZE, dtype=np.float32)
    xx, nn = np.meshgrid(east, north)
    zz = -nn
    vertices = np.column_stack((xx.ravel(), relief.ravel(), zz.ravel())).astype(np.float32)

    idx = np.arange(GRID_SIZE * GRID_SIZE, dtype=np.uint32).reshape(GRID_SIZE, GRID_SIZE)
    a = idx[:-1, :-1].ravel()
    b = idx[:-1, 1:].ravel()
    c = idx[1:, :-1].ravel()
    d = idx[1:, 1:].ravel()
    faces = np.vstack((np.column_stack((a, c, b)), np.column_stack((b, c, d)))).astype(np.uint32)

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False, validate=False)
    mesh.visual.material = trimesh.visual.material.PBRMaterial(
        baseColorFactor=[112, 124, 119, 255], roughnessFactor=0.96, metallicFactor=0.0
    )
    return mesh


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_GLB.parent.mkdir(parents=True, exist_ok=True)
    META_PATH.parent.mkdir(parents=True, exist_ok=True)

    heights, meta = build_height_grid()
    mesh = build_mesh(heights)
    scene = trimesh.Scene(mesh)
    RAW_GLB.write_bytes(scene.export(file_type="glb"))
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(meta, indent=2))
    print(f"raw_glb={RAW_GLB}")
    print(f"raw_glb_bytes={RAW_GLB.stat().st_size}")


if __name__ == "__main__":
    main()
