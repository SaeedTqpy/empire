#!/usr/bin/env python3
"""Embed the Phase 3 satellite image into the raw terrain GLB.

The Phase 2 mesh already owns geospatially aligned TEXCOORD_0 values. This
step only replaces the top-surface material; geometry, normals, skirt and
physical proportions stay untouched.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--texture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scene = trimesh.load(args.model, force="scene", process=False)
    if not isinstance(scene, trimesh.Scene):
        raise SystemExit("expected a glTF scene")

    geometries = list(scene.geometry.items())
    if len(geometries) < 2:
        raise SystemExit("expected terrain and skirt geometries")

    terrain_name, terrain = max(geometries, key=lambda entry: len(entry[1].faces))
    uv = getattr(terrain.visual, "uv", None)
    if uv is None or len(uv) != len(terrain.vertices):
        raise SystemExit("terrain is missing the Phase 2 UV coordinate contract")
    if not np.isfinite(np.asarray(uv)).all():
        raise SystemExit("terrain UVs contain NaN/Inf")

    texture = Image.open(args.texture).convert("RGB")
    material = PBRMaterial(
        name="Damavand Sentinel-2 Terrain",
        baseColorFactor=[255, 255, 255, 255],
        baseColorTexture=texture,
        metallicFactor=0.0,
        roughnessFactor=0.94,
        doubleSided=False,
    )
    terrain.visual = TextureVisuals(uv=np.asarray(uv).copy(), material=material)
    terrain.metadata["name"] = "Damavand Satellite Terrain"

    # The skirt deliberately stays texture-free: a neutral edge keeps the
    # 30 km cutout readable as a physical terrain exhibit at low angles.
    for name, mesh in geometries:
        if name != terrain_name:
            mesh.metadata["name"] = "Terrain Skirt"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = scene.export(file_type="glb")
    if not isinstance(payload, (bytes, bytearray)):
        raise SystemExit("GLB export did not return bytes")
    args.output.write_bytes(payload)
    print(f"embedded {args.texture} into {args.output} ({args.output.stat().st_size / 1024 / 1024:.2f} MiB raw)")


if __name__ == "__main__":
    main()
