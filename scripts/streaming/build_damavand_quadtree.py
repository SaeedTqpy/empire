#!/usr/bin/env python3
"""Build a spatial 3D Tiles quadtree for Damavand from the canonical DEM + imagery.

Phase 7 keeps the current 30 km coordinate contract but replaces one monolithic
visual model with a true spatial hierarchy:

  L0: 1 whole-mountain tile
  L1: 4 quadrant tiles
  L2: 16 near-field tiles

Every leaf reaches the same ~29 m DEM sample spacing as the 1025×1025 canonical
terrain and ~7.3 m/texel imagery density as the 4096×4096 Sentinel-2 master.
Only the tiles required by the camera are intended to be resident at once.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from trimesh.visual.material import SimpleMaterial
from trimesh.visual.texture import TextureVisuals

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
import build_peak_terrain as terrain  # noqa: E402


@dataclass(frozen=True)
class LodProfile:
    level: int
    divisions: int
    grid_size: int
    texture_size: int
    webp_quality: int


PROFILES = (
    LodProfile(level=0, divisions=1, grid_size=129, texture_size=512, webp_quality=82),
    LodProfile(level=1, divisions=2, grid_size=129, texture_size=512, webp_quality=88),
    LodProfile(level=2, divisions=4, grid_size=257, texture_size=1024, webp_quality=95),
)
FULL_GRID = 1025
INTERACTION_GRID = 513
SKIRT_DEPTH_M = 90.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terrain-config", required=True, type=Path)
    parser.add_argument("--master-texture", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path, default=Path(".terrain-cache"))
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def tile_bbox(global_bbox: tuple[float, float, float, float], divisions: int, row: int, col: int) -> tuple[float, float, float, float]:
    west, south, east, north = global_bbox
    lon_step = (east - west) / divisions
    lat_step = (north - south) / divisions
    tw = west + col * lon_step
    te = west + (col + 1) * lon_step
    tn = north - row * lat_step
    ts = north - (row + 1) * lat_step
    return tw, ts, te, tn


def tile_heights(full: np.ndarray, profile: LodProfile, row: int, col: int) -> np.ndarray:
    intervals = FULL_GRID - 1
    span = intervals // profile.divisions
    start_r = row * span
    start_c = col * span
    stop_r = (row + 1) * span
    stop_c = (col + 1) * span
    stride = span // (profile.grid_size - 1)
    if stride < 1 or span % (profile.grid_size - 1) != 0:
        raise ValueError(f"grid {profile.grid_size} does not divide L{profile.level} span {span}")
    result = full[start_r : stop_r + 1 : stride, start_c : stop_c + 1 : stride]
    if result.shape != (profile.grid_size, profile.grid_size):
        raise ValueError(f"unexpected L{profile.level} sample shape {result.shape}")
    return result


def build_top_mesh(
    heights: np.ndarray,
    bbox: tuple[float, float, float, float],
    global_center: tuple[float, float],
    base_elevation: float,
    color: list[float],
) -> trimesh.Trimesh:
    n = heights.shape[0]
    west, south, east, north = bbox
    center_lat, center_lon = global_center

    lon_axis = np.linspace(west, east, n, dtype=np.float64)
    lat_axis = np.linspace(north, south, n, dtype=np.float64)
    x_axis = terrain.EARTH_RADIUS_M * math.cos(math.radians(center_lat)) * np.radians(lon_axis - center_lon)
    z_axis = terrain.EARTH_RADIUS_M * np.radians(lat_axis - center_lat)
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
    visual = TextureVisuals(uv=uv, material=SimpleMaterial(diffuse=rgba, glossiness=0.0))
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, visual=visual, process=False)
    mesh.metadata["name"] = "Damavand Terrain"
    mesh.vertex_normals = terrain.heightfield_normals(y, x_axis, z_axis)
    return mesh


def build_skirt(top: trimesh.Trimesh, n: int) -> trimesh.Trimesh:
    north = list(range(0, n))
    east = [r * n + (n - 1) for r in range(1, n)]
    south = list(range(n * n - 2, n * (n - 1) - 1, -1))
    west = [r * n for r in range(n - 2, 0, -1)]
    perimeter = np.asarray(north + east + south + west, dtype=np.int32)
    top_ring = np.asarray(top.vertices)[perimeter].astype(np.float32)
    bottom_ring = top_ring.copy()
    bottom_ring[:, 1] = np.maximum(0.0, bottom_ring[:, 1] - SKIRT_DEPTH_M)
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
    return mesh


def export_raw(top: trimesh.Trimesh, skirt: trimesh.Trimesh, path: Path) -> tuple[np.ndarray, np.ndarray]:
    path.parent.mkdir(parents=True, exist_ok=True)
    scene = trimesh.Scene()
    scene.add_geometry(top, geom_name="terrain", node_name="terrain")
    scene.add_geometry(skirt, geom_name="skirt", node_name="skirt")
    payload = scene.export(file_type="glb")
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("expected GLB bytes")
    path.write_bytes(payload)
    vertices = np.vstack((np.asarray(top.vertices), np.asarray(skirt.vertices)))
    return np.min(vertices, axis=0), np.max(vertices, axis=0)


def crop_texture(master: Image.Image, divisions: int, row: int, col: int, size: int, path: Path) -> None:
    w, h = master.size
    left = round(col * w / divisions)
    right = round((col + 1) * w / divisions)
    upper = round(row * h / divisions)
    lower = round((row + 1) * h / divisions)
    image = master.crop((left, upper, right, lower))
    if image.size != (size, size):
        image = image.resize((size, size), Image.Resampling.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True, compress_level=5)


def compress_model(raw: Path, texture: Path, output: Path, quality: int, work_dir: Path) -> None:
    textured = work_dir / f"{output.stem}.textured.glb"
    webp = work_dir / f"{output.stem}.webp.glb"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "imagery" / "embed_texture.py"), "--model", str(raw), "--texture", str(texture), "--output", str(textured)],
        check=True,
    )
    subprocess.run(
        ["npx", "gltf-transform", "webp", str(textured), str(webp), "--slots", "baseColor", "--quality", str(quality)],
        check=True,
    )
    subprocess.run(
        ["npx", "gltf-transform", "draco", str(webp), str(output), "--method", "edgebreaker"],
        check=True,
    )
    raw.unlink(missing_ok=True)
    texture.unlink(missing_ok=True)
    textured.unlink(missing_ok=True)
    webp.unlink(missing_ok=True)


def box_volume(bounds_min: np.ndarray, bounds_max: np.ndarray) -> list[float]:
    center = (bounds_min + bounds_max) * 0.5
    half = (bounds_max - bounds_min) * 0.5
    return [
        float(center[0]), float(center[1]), float(center[2]),
        float(half[0]), 0.0, 0.0,
        0.0, float(half[1]), 0.0,
        0.0, 0.0, float(half[2]),
    ]


def main() -> None:
    args = parse_args()
    config = terrain.load_config(args.terrain_config)
    source_config = json.loads(json.dumps(config))
    source_config["grid_size"] = FULL_GRID
    center_lat = float(config["center"]["lat"])
    center_lon = float(config["center"]["lon"])
    global_bbox = terrain.bbox_around(center_lat, center_lon, float(config["extent_km"]))

    args.work_dir.mkdir(parents=True, exist_ok=True)
    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Sampling canonical {FULL_GRID}×{FULL_GRID} DEM once for the streaming quadtree", flush=True)
    full_heights, source_tiles = terrain.sample_dem(source_config, global_bbox, args.cache_dir)
    elevation_min = float(np.min(full_heights))
    elevation_max = float(np.max(full_heights))
    base_elevation = math.floor(elevation_min - float(config.get("base_depth_m", 100.0)))
    master = Image.open(args.master_texture).convert("RGB")
    if master.size != (4096, 4096):
        raise SystemExit(f"expected a 4096×4096 master texture, got {master.size}")

    # Lightweight interaction proxy remains raycastable for routes/hotspots while
    # visual terrain is streamed independently. Its 513 grid is never rendered
    # after the first 3D tile arrives.
    interaction_heights = full_heights[::2, ::2]
    top = build_top_mesh(interaction_heights, global_bbox, (center_lat, center_lon), base_elevation, config["material"]["base_color"])
    skirt = build_skirt(top, INTERACTION_GRID)
    raw = args.work_dir / "interaction.raw.glb"
    export_raw(top, skirt, raw)
    interaction_texture = args.work_dir / "interaction.png"
    master.resize((512, 512), Image.Resampling.LANCZOS).save(interaction_texture, format="PNG", optimize=True)
    compress_model(raw, interaction_texture, args.output_dir / "interaction.glb", 82, args.work_dir)

    records: dict[tuple[int, int, int], dict] = {}
    total_bytes = (args.output_dir / "interaction.glb").stat().st_size

    for profile in PROFILES:
        for row in range(profile.divisions):
            for col in range(profile.divisions):
                heights = tile_heights(full_heights, profile, row, col)
                bbox = tile_bbox(global_bbox, profile.divisions, row, col)
                top = build_top_mesh(heights, bbox, (center_lat, center_lon), base_elevation, config["material"]["base_color"])
                skirt = build_skirt(top, profile.grid_size)

                rel = Path(f"l{profile.level}") / f"r{row}_c{col}.glb"
                output = args.output_dir / rel
                raw = args.work_dir / f"l{profile.level}_r{row}_c{col}.raw.glb"
                bounds_min, bounds_max = export_raw(top, skirt, raw)
                texture = args.work_dir / f"l{profile.level}_r{row}_c{col}.png"
                crop_texture(master, profile.divisions, row, col, profile.texture_size, texture)
                compress_model(raw, texture, output, profile.webp_quality, args.work_dir)
                total_bytes += output.stat().st_size

                tile_extent_m = float(config["extent_km"]) * 1000.0 / profile.divisions
                sample_spacing_m = tile_extent_m / (profile.grid_size - 1)
                imagery_spacing_m = tile_extent_m / profile.texture_size
                error = 0.0 if profile.level == PROFILES[-1].level else sample_spacing_m
                records[(profile.level, row, col)] = {
                    "boundingVolume": {"box": box_volume(bounds_min, bounds_max)},
                    "geometricError": round(error, 4),
                    "refine": "REPLACE",
                    "content": {"uri": rel.as_posix()},
                    "extras": {
                        "lod": profile.level,
                        "row": row,
                        "col": col,
                        "gridSize": profile.grid_size,
                        "textureSize": profile.texture_size,
                        "groundSampleM": round(sample_spacing_m, 4),
                        "imageryTexelM": round(imagery_spacing_m, 4),
                    },
                }
                print(f"built {rel} · grid={profile.grid_size} texture={profile.texture_size} bytes={output.stat().st_size:,}", flush=True)

    for profile in reversed(PROFILES[:-1]):
        next_level = profile.level + 1
        for row in range(profile.divisions):
            for col in range(profile.divisions):
                node = records[(profile.level, row, col)]
                node["children"] = [
                    records[(next_level, row * 2 + dr, col * 2 + dc)]
                    for dr in range(2)
                    for dc in range(2)
                ]

    root = records[(0, 0, 0)]
    tileset = {
        "asset": {
            "version": "1.1",
            "generator": "Iran 3D Peaks Phase 7 spatial streaming pipeline",
        },
        "geometricError": root["geometricError"],
        "root": root,
        "extras": {
            "peak": "damavand",
            "datasetVersion": "phase7-v1",
            "coordinateContract": "+X east, +Y elevation above shared base, +Z north, metres",
            "sourceTerrain": "Skadi/SRTM",
            "sourceImagery": "Copernicus Sentinel-2",
        },
    }
    (args.output_dir / "tileset.json").write_text(json.dumps(tileset, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "peak_id": "damavand",
        "dataset_version": "phase7-v1",
        "format": "3D Tiles 1.1",
        "tile_count": len(records),
        "max_depth": PROFILES[-1].level,
        "interaction_grid": INTERACTION_GRID,
        "source_full_grid": FULL_GRID,
        "total_asset_bytes": total_bytes,
        "elevation_m": {"min": round(elevation_min, 2), "max": round(elevation_max, 2), "base": base_elevation},
        "profiles": [profile.__dict__ for profile in PROFILES],
        "source_tiles": source_tiles,
    }
    (args.output_dir / "streaming.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Streaming quadtree ready: {len(records)} visual tiles, {total_bytes / 1024 / 1024:.2f} MiB assets", flush=True)


if __name__ == "__main__":
    main()
