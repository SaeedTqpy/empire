#!/usr/bin/env python3
"""Apply the native-detail terrain + extreme close-inspection viewer profile.

This migration sits on top of apply_ultra_detail_code.py. It makes the 1025
terrain grid visible at close range while keeping all values guarded and
idempotent for reproducible GitHub Actions builds.
"""

from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: source anchor not found in {path}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


replace_once(
    "src/three/engine.ts",
    '    this.camera = new THREE.PerspectiveCamera(38, 1, 0.015, 60);\n',
    '    this.camera = new THREE.PerspectiveCamera(38, 1, 0.002, 60);\n',
    "extreme camera near plane",
)

replace_once(
    "src/three/engine.ts",
    '''    controls.minDistance = 0.32;\n    controls.maxDistance = 6.5;\n    controls.zoomSpeed = 0.85;\n''',
    '''    controls.minDistance = 0.018;\n    controls.maxDistance = 6.5;\n    controls.zoomSpeed = 0.72;\n''',
    "extreme orbit zoom",
)

replace_once(
    "src/three/engine.ts",
    '''    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);\n    const MAX_PIXELS = 8_000_000;\n''',
    '''    const dpr = Math.min(window.devicePixelRatio || 1, 3);\n    const MAX_PIXELS = 12_000_000;\n''',
    "extreme render resolution budget",
)

replace_once(
    "src/data/peaks/damavand.ts",
    '    gridSize: 513,\n',
    '    gridSize: 1025,\n',
    "native-detail terrain metadata",
)

replace_once(
    "src/data/peaks/damavand.ts",
    '  modelPath: "/models/damavand.glb?v=ultra4k-sentinel-20260812",\n',
    '  modelPath: "/models/damavand.glb?v=extreme1025-4k-20260812",\n',
    "extreme-detail model cache token",
)

replace_once(
    "src/data/peaks/damavand.ts",
    '    thumbnail: "/img/peaks/damavand-sentinel.webp?v=ultra4k-sentinel-20260812",\n    hero: "/img/peaks/damavand-sentinel.webp?v=ultra4k-sentinel-20260812",\n',
    '    thumbnail: "/img/peaks/damavand-sentinel.webp?v=extreme1025-4k-20260812",\n    hero: "/img/peaks/damavand-sentinel.webp?v=extreme1025-4k-20260812",\n',
    "extreme-detail preview cache token",
)

print("Extreme native-detail terrain/viewer migration complete")
