#!/usr/bin/env python3
"""Apply the lossless 4K imagery + close-inspection viewer profile.

This migration is deliberately guarded and idempotent. It upgrades the image
pipeline without inventing detail beyond the 10 m Sentinel-2 source, and makes
that extra real texture detail visible through higher-quality sampling and a
closer camera.
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


# ---------------------------------------------------------------------------
# Lossless 4K authoring master. The final delivery texture remains WebP, but
# we avoid JPEG -> WebP double-lossy encoding before it gets there.
# ---------------------------------------------------------------------------
replace_once(
    "scripts/imagery/build_sentinel_texture.py",
    '    image = Image.fromarray(np.rint(display * 255.0).astype(np.uint8), mode="RGB")\n',
    '    image = Image.fromarray(np.rint(display * 255.0).astype(np.uint8))\n',
    "Pillow RGB construction",
)

replace_once(
    "scripts/imagery/build_sentinel_texture.py",
    '''    args.texture.parent.mkdir(parents=True, exist_ok=True)\n    image.save(args.texture, format="JPEG", quality=int(output["jpeg_quality"]), optimize=True, progressive=True)\n''',
    '''    args.texture.parent.mkdir(parents=True, exist_ok=True)\n    master_format = str(output.get("master_format", "png")).lower()\n    if master_format != "png":\n        raise SystemExit(f"Unsupported ultra-detail master format: {master_format}")\n    image.save(args.texture, format="PNG", optimize=True, compress_level=6)\n''',
    "lossless imagery master",
)

replace_once(
    "scripts/imagery/build_sentinel_texture.py",
    '''        "texture": {\n            "width": width,\n            "height": height,\n            "format": "image/jpeg",\n            "coverage_percent": round(coverage * 100.0, 4),\n''',
    '''        "texture": {\n            "width": width,\n            "height": height,\n            "master_format": "image/png",\n            "embedded_format": "image/webp",\n            "webp_quality": int(output["webp_quality"]),\n            "ground_resolution_m_approx": round(float(terrain["extent_km"]) * 1000.0 / width, 4),\n            "coverage_percent": round(coverage * 100.0, 4),\n''',
    "imagery quality manifest",
)

replace_once(
    "scripts/imagery/build_sentinel_texture.py",
    '''            "residual_nodata": "GDAL fillnodata after >=97% real source coverage",\n            "color": config["color"],\n''',
    '''            "residual_nodata": "GDAL fillnodata after >=97% real source coverage",\n            "authoring_master": "lossless PNG before final WebP encoding",\n            "detail_policy": "native-detail preservation; no AI/synthetic super-resolution",\n            "color": config["color"],\n''',
    "imagery detail policy",
)

# ---------------------------------------------------------------------------
# Viewer: expose the 4K texture instead of leaving quality on the table.
# ---------------------------------------------------------------------------
replace_once(
    "src/three/engine.ts",
    '  private reducedMotion = false;\n',
    '  private reducedMotion = false;\n  private maxTextureAnisotropy = 8;\n',
    "texture anisotropy state",
)

replace_once(
    "src/three/engine.ts",
    '''    await renderer.init();\n    this.renderer = renderer;\n\n    const scene = new THREE.Scene();\n''',
    '''    await renderer.init();\n    this.renderer = renderer;\n    const caps = (renderer as any).capabilities;\n    const reportedAnisotropy = caps?.getMaxAnisotropy?.();\n    this.maxTextureAnisotropy = Number.isFinite(reportedAnisotropy)\n      ? Math.max(1, Math.min(16, reportedAnisotropy))\n      : 8;\n\n    const scene = new THREE.Scene();\n''',
    "runtime anisotropy capability",
)

replace_once(
    "src/three/engine.ts",
    '    this.camera = new THREE.PerspectiveCamera(38, 1, 0.05, 60);\n',
    '    this.camera = new THREE.PerspectiveCamera(38, 1, 0.015, 60);\n',
    "close zoom camera near plane",
)

replace_once(
    "src/three/engine.ts",
    '''    controls.dampingFactor = 0.06;\n    controls.minDistance = 1.1;\n    controls.maxDistance = 6.5;\n''',
    '''    controls.dampingFactor = 0.06;\n    controls.minDistance = 0.32;\n    controls.maxDistance = 6.5;\n    controls.zoomSpeed = 0.85;\n    controls.zoomToCursor = true;\n''',
    "close inspection orbit controls",
)

replace_once(
    "src/three/engine.ts",
    '''    const dpr = Math.min(window.devicePixelRatio || 1, 2);\n    const MAX_PIXELS = 3_500_000;\n''',
    '''    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);\n    const MAX_PIXELS = 8_000_000;\n''',
    "ultra render resolution budget",
)

replace_once(
    "src/three/engine.ts",
    '''  /** TSL rim-light: a soft warm fresnel edge so the architecture reads\n   *  against the parchment backdrop. Falls back silently to the\n   *  original material if node patching fails. */\n  private applyRim(mesh: THREE.Mesh) {\n''',
    '''  private tuneTexture(texture: THREE.Texture | null) {\n    if (!texture) return;\n    texture.anisotropy = this.maxTextureAnisotropy;\n    texture.minFilter = THREE.LinearMipmapLinearFilter;\n    texture.magFilter = THREE.LinearFilter;\n    texture.generateMipmaps = true;\n    texture.needsUpdate = true;\n  }\n\n  /** TSL rim-light: a soft warm fresnel edge so the architecture reads\n   *  against the parchment backdrop. Falls back silently to the\n   *  original material if node patching fails. */\n  private applyRim(mesh: THREE.Mesh) {\n''',
    "high quality texture sampling helper",
)

replace_once(
    "src/three/engine.ts",
    '''      const src = mesh.material as THREE.MeshStandardMaterial;\n      const nm = new THREE.MeshStandardNodeMaterial();\n      nm.color = src.color ? src.color.clone() : new THREE.Color(0xffffff);\n      nm.map = src.map ?? null;\n''',
    '''      const src = mesh.material as THREE.MeshStandardMaterial;\n      this.tuneTexture(src.map ?? null);\n      this.tuneTexture(src.normalMap ?? null);\n      this.tuneTexture((src as any).roughnessMap ?? null);\n      this.tuneTexture((src as any).metalnessMap ?? null);\n      this.tuneTexture((src as any).aoMap ?? null);\n      const nm = new THREE.MeshStandardNodeMaterial();\n      nm.color = src.color ? src.color.clone() : new THREE.Color(0xffffff);\n      nm.map = src.map ?? null;\n''',
    "apply high quality texture sampling",
)

# Cache-bust the generated GLB after the 4K publish.
replace_once(
    "src/data/peaks/damavand.ts",
    '  modelPath: "/models/damavand.glb?v=phase3-sentinel-20260812",\n',
    '  modelPath: "/models/damavand.glb?v=ultra4k-sentinel-20260812",\n',
    "4K Damavand model cache token",
)

print("Ultra-detail imagery/viewer migration complete")
