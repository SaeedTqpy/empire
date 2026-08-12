#!/usr/bin/env python3
"""Validate the Phase 7 Damavand spatial streaming dataset."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


EXPECTED_LEVELS = {0: 1, 1: 4, 2: 16}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tileset", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--interaction", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.tileset.parent
    tileset = json.loads(args.tileset.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    if tileset.get("asset", {}).get("version") != "1.1":
        raise SystemExit("expected 3D Tiles 1.1")
    if manifest.get("peak_id") != "damavand" or manifest.get("dataset_version") != "phase7-v1":
        raise SystemExit("streaming manifest identity mismatch")
    if manifest.get("tile_count") != 21 or manifest.get("max_depth") != 2:
        raise SystemExit("unexpected streaming hierarchy metadata")
    if manifest.get("interaction_grid") != 513 or manifest.get("source_full_grid") != 1025:
        raise SystemExit("interaction/source grid contract mismatch")
    if not args.interaction.exists() or args.interaction.stat().st_size < 100_000:
        raise SystemExit("interaction proxy is missing or suspiciously small")

    levels: Counter[int] = Counter()
    files: list[Path] = []
    leaf_errors: list[float] = []

    def walk(node: dict, depth: int) -> None:
        extras = node.get("extras", {})
        level = int(extras.get("lod", -1))
        if level != depth:
            raise SystemExit(f"LOD/depth mismatch: extras={level}, depth={depth}")
        levels[level] += 1

        box = node.get("boundingVolume", {}).get("box")
        if not isinstance(box, list) or len(box) != 12 or not all(isinstance(x, (int, float)) for x in box):
            raise SystemExit(f"invalid bounding box at L{level}")
        if node.get("refine") != "REPLACE":
            raise SystemExit(f"tile at L{level} must use REPLACE refinement")

        content = node.get("content", {})
        uri = content.get("uri")
        if not isinstance(uri, str) or not uri.endswith(".glb") or ".." in Path(uri).parts:
            raise SystemExit(f"invalid content URI at L{level}: {uri!r}")
        path = root_dir / uri
        if not path.exists() or path.stat().st_size < 20_000:
            raise SystemExit(f"tile asset missing or suspiciously small: {path}")
        files.append(path)

        children = node.get("children", [])
        error = float(node.get("geometricError", -1))
        if children:
            if len(children) != 4:
                raise SystemExit(f"non-leaf L{level} tile must have four children")
            if error <= 0:
                raise SystemExit(f"non-leaf L{level} tile must have positive geometric error")
            for child in children:
                walk(child, depth + 1)
        else:
            leaf_errors.append(error)
            if depth != 2:
                raise SystemExit(f"premature leaf at depth {depth}")

    walk(tileset["root"], 0)

    if dict(levels) != EXPECTED_LEVELS:
        raise SystemExit(f"unexpected level counts: {dict(levels)}")
    if any(abs(value) > 1e-9 for value in leaf_errors):
        raise SystemExit(f"leaf geometric error must be zero: {leaf_errors[:3]}")
    if len({path.resolve() for path in files}) != 21:
        raise SystemExit("tile content URIs are not unique")

    asset_bytes = sum(path.stat().st_size for path in files) + args.interaction.stat().st_size
    recorded = int(manifest.get("total_asset_bytes", 0))
    if abs(asset_bytes - recorded) > 4096:
        raise SystemExit(f"asset byte accounting mismatch: actual={asset_bytes}, recorded={recorded}")
    if asset_bytes > 100 * 1024 * 1024:
        raise SystemExit(f"Phase 7 starter dataset exceeds 100 MiB: {asset_bytes / 1024 / 1024:.2f} MiB")

    profiles = manifest.get("profiles", [])
    if [p.get("level") for p in profiles] != [0, 1, 2]:
        raise SystemExit("LOD profile levels mismatch")
    leaf = profiles[-1]
    if leaf.get("grid_size") != 257 or leaf.get("texture_size") != 1024:
        raise SystemExit("leaf profile does not preserve intended source detail")

    print(
        "streaming validation OK: "
        f"21 visual tiles (1/4/16), interaction={args.interaction.stat().st_size / 1024:.1f} KiB, "
        f"assets={asset_bytes / 1024 / 1024:.2f} MiB"
    )


if __name__ == "__main__":
    main()
