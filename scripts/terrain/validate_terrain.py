#!/usr/bin/env python3
"""Fail the terrain build if the generated GLB is structurally implausible."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    if not args.model.exists() or args.model.stat().st_size < 100_000:
        raise SystemExit("terrain GLB is missing or suspiciously small")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest["peak_id"] != "damavand":
        raise SystemExit("manifest peak_id mismatch")
    if manifest["grid_size"] < 129:
        raise SystemExit("terrain grid is below production floor")

    scene = trimesh.load(args.model, force="scene", process=False)
    geometries = list(scene.geometry.values())
    if len(geometries) < 2:
        raise SystemExit("expected terrain and skirt geometries")

    terrain = max(geometries, key=lambda mesh: len(mesh.faces))
    vertices = np.asarray(terrain.vertices)
    if not np.isfinite(vertices).all():
        raise SystemExit("terrain contains NaN/Inf vertices")
    if len(terrain.faces) < 100_000:
        raise SystemExit(f"terrain triangle count too low: {len(terrain.faces)}")

    bounds = terrain.bounds
    width = float(bounds[1, 0] - bounds[0, 0])
    depth = float(bounds[1, 2] - bounds[0, 2])
    relief = float(bounds[1, 1] - bounds[0, 1])
    if not (27_000 <= width <= 33_000 and 27_000 <= depth <= 33_000):
        raise SystemExit(f"unexpected footprint: {width:.1f}m x {depth:.1f}m")
    if relief < 2_000:
        raise SystemExit(f"terrain relief is implausibly low: {relief:.1f}m")

    source_tiles = manifest.get("source_tiles", [])
    if len(source_tiles) < 2:
        raise SystemExit("manifest does not record source tiles")

    print(
        f"terrain validation OK: {len(terrain.vertices)} vertices, "
        f"{len(terrain.faces)} triangles, {width:.0f}x{depth:.0f}m, relief={relief:.0f}m"
    )


if __name__ == "__main__":
    main()
