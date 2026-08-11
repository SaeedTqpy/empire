#!/usr/bin/env python3
"""Apply the small, deliberate Phase 3 changes to legacy Empire viewer files.

The rendering engine is intentionally still shared with upstream architecture.
This migration uses guarded exact replacements so CI fails if upstream code
moves underneath us instead of silently producing a half-applied scene profile.
Running it more than once is safe.
"""

from __future__ import annotations

from pathlib import Path


def replace_guarded(path: Path, old: str, new: str, *, all_matches: bool = False) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Phase 3 patch anchor missing in {path}: {old[:80]!r}")
    text = text.replace(old, new) if all_matches else text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def patch_engine() -> None:
    path = Path("src/three/engine.ts")
    replacements = [
        ("private rimIntensity = uniform(0.14);", "private rimIntensity = uniform(0.055);"),
        ("private contactOpacity = uniform(0.46);", "private contactOpacity = uniform(0.24);"),
        ("renderer.toneMappingExposure = 1.02;", "renderer.toneMappingExposure = 1.08;"),
        ("scene.fog = new THREE.Fog(0xf3ead9, 9, 26);", "scene.fog = new THREE.Fog(0xc7d7df, 7.5, 22);"),
        ("scene.environmentIntensity = 0.4;", "scene.environmentIntensity = 0.62;"),
        (
            "const hemi = new THREE.HemisphereLight(0xfff6e8, 0xc9b092, 0.18);",
            "const hemi = new THREE.HemisphereLight(0xdcebf4, 0x706b5c, 0.34);",
        ),
        (
            "const key = new THREE.DirectionalLight(0xfff4e6, 3.1);\n    key.position.set(3.0, 4.4, 2.6);",
            "const key = new THREE.DirectionalLight(0xfff3dc, 3.6);\n    key.position.set(4.5, 6.0, 2.8);",
        ),
        ("key.shadow.radius = 2.6;", "key.shadow.radius = 1.8;"),
        (
            "const fill = new THREE.DirectionalLight(0xd6e2f2, 0.22);",
            "const fill = new THREE.DirectionalLight(0xb8d0df, 0.30);",
        ),
        (
            "const rim = new THREE.DirectionalLight(0xffd39a, 0.72);",
            "const rim = new THREE.DirectionalLight(0xffe0ad, 0.32);",
        ),
        (
            "const bounce = new THREE.DirectionalLight(0xffe3c2, 0.16);",
            "const bounce = new THREE.DirectionalLight(0xc9c0a8, 0.12);",
        ),
        ("gm.colorNode = color(0xfaf3e6);", "gm.colorNode = color(0xbfc1b6);"),
        (
            "new THREE.MeshStandardMaterial({ color: 0xf6eddc, roughness: 1, metalness: 0 })",
            "new THREE.MeshStandardMaterial({ color: 0xb9baae, roughness: 1, metalness: 0 })",
        ),
        (
            'sky.addColorStop(0.0, "#fffdf6"); // zenith\n      sky.addColorStop(0.42, "#f7eedd");\n      sky.addColorStop(0.52, "#ead9be"); // horizon\n      sky.addColorStop(1.0, "#b6a184"); // floor bounce',
            'sky.addColorStop(0.0, "#9fc3da"); // zenith\n      sky.addColorStop(0.42, "#c6dce6");\n      sky.addColorStop(0.58, "#e7ece8"); // horizon haze\n      sky.addColorStop(1.0, "#8d8b79"); // terrain bounce',
        ),
        (
            'sun.addColorStop(0, "rgba(255,240,212,0.95)");\n      sun.addColorStop(1, "rgba(255,240,212,0)");',
            'sun.addColorStop(0, "rgba(255,244,214,0.88)");\n      sun.addColorStop(1, "rgba(255,244,214,0)");',
        ),
        (
            "[this.rimLight?.color, new THREE.Color(0xffd9a4).lerp(tint, 0.45)],",
            "[this.rimLight?.color, new THREE.Color(0xd2e4ee).lerp(tint, 0.32)],",
        ),
        (
            "[this.keyLight?.color, new THREE.Color(0xfff2e2).lerp(tint, 0.16)],",
            "[this.keyLight?.color, new THREE.Color(0xfff3dc).lerp(tint, 0.10)],",
        ),
        (
            "[this.bounceLight?.color, new THREE.Color(0xffe7cb).lerp(tint, 0.35)],",
            "[this.bounceLight?.color, new THREE.Color(0xc8c2ae).lerp(tint, 0.18)],",
        ),
        (
            "[this.rimColor.value as THREE.Color, new THREE.Color(0xffe8c8).lerp(tint, 0.4)],",
            "[this.rimColor.value as THREE.Color, new THREE.Color(0xdcebf2).lerp(tint, 0.28)],",
        ),
    ]
    for old, new in replacements:
        replace_guarded(path, old, new)

    # Contact shadow animation has three literal reset points in the legacy
    # choreography. Keep them coherent with the new lower terrain opacity.
    replace_guarded(path, "this.contactOpacity.value = 0.46;", "this.contactOpacity.value = 0.24;", all_matches=True)
    replace_guarded(path, "0.46 * Math.max", "0.24 * Math.max", all_matches=True)


def patch_viewer() -> None:
    path = Path("src/components/Viewer.tsx")
    old = """        <canvas ref={canvasRef} className=\"block h-full w-full touch-none\" aria-label={`3D model of the ${empire.dwelling}`} />\n        {/* holds the outgoing frame still while the next dwelling takes its\n"""
    new = """        <canvas ref={canvasRef} className=\"block h-full w-full touch-none\" aria-label={`3D model of the ${empire.dwelling}`} />\n        {empire.imageryAttribution && (\n          <div className=\"viewer-attribution\" aria-label=\"Satellite imagery attribution\">\n            {empire.imageryAttribution}\n          </div>\n        )}\n        {/* holds the outgoing frame still while the next dwelling takes its\n"""
    replace_guarded(path, old, new)

    replacements = [
        ('{ key: "labels", label: "Hotspot pins", icon: EyeIcon },', '{ key: "labels", label: "Peak markers", icon: EyeIcon },'),
        ('{ key: "grid", label: "Turntable grid", icon: GridIcon },', '{ key: "grid", label: "Terrain grid", icon: GridIcon },'),
        ('{ key: "xray", label: "X-ray section", icon: XrayIcon },', '{ key: "xray", label: "Terrain x-ray", icon: XrayIcon },'),
    ]
    for old_value, new_value in replacements:
        replace_guarded(path, old_value, new_value)


def main() -> None:
    patch_engine()
    patch_viewer()
    print("Phase 3 viewer code is applied")


if __name__ == "__main__":
    main()
