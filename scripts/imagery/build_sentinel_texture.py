#!/usr/bin/env python3
"""Build a north-up true-colour texture aligned to the Phase 2 terrain UVs.

The script searches the public Earth Search STAC catalogue for low-cloud
Sentinel-2 Collection 1 L2A COGs, reprojects RGB into the exact WGS84 terrain
bbox, masks cloud/shadow pixels with SCL when available, and composites the
best observations until the requested area is covered.

Texture contract (matching the Damavand terrain GLB):
  image left   = west
  image right  = east
  image top    = north
  image bottom = south
  glTF UV      = (0,0) upper-left per glTF 2.0
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image, ImageEnhance, ImageFilter
from rasterio.enums import Resampling
from rasterio.fill import fillnodata
from rasterio.transform import from_bounds
from rasterio.warp import reproject

BAD_SCL = np.array([0, 1, 3, 7, 8, 9, 10], dtype=np.int16)
RGB_ASSET_KEYS = {
    "red": ("red", "B04", "red-jp2"),
    "green": ("green", "B03", "green-jp2"),
    "blue": ("blue", "B02", "blue-jp2"),
}
SCL_KEYS = ("scl", "SCL", "scl-jp2")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--texture", required=True, type=Path)
    parser.add_argument("--preview", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def post_json(url: str, payload: dict[str, Any], attempts: int = 4) -> dict[str, Any]:
    encoded = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/geo+json, application/json",
            "User-Agent": "iran-3d-peaks-imagery-builder/1.0",
        },
        method="POST",
    )
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"STAC request failed after {attempts} attempts: {error}")


def pick_asset(item: dict[str, Any], keys: tuple[str, ...]) -> tuple[str, dict[str, Any]]:
    assets = item.get("assets", {})
    for key in keys:
        asset = assets.get(key)
        if asset and asset.get("href"):
            return key, asset
    available = ", ".join(sorted(assets))
    raise KeyError(f"None of {keys} found on {item.get('id')}; assets: {available}")


def asset_scale_offset(asset: dict[str, Any]) -> tuple[float, float]:
    bands = asset.get("raster:bands") or []
    band = bands[0] if bands else {}
    scale = float(band.get("scale", 1.0))
    offset = float(band.get("offset", 0.0))
    return scale, offset


def read_reprojected(
    asset: dict[str, Any],
    width: int,
    height: int,
    dst_transform: rasterio.Affine,
    *,
    resampling: Resampling,
) -> np.ndarray:
    href = asset["href"]
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with rasterio.open(href) as src:
                out = np.full((height, width), np.nan, dtype=np.float32)
                reproject(
                    source=rasterio.band(src, 1),
                    destination=out,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    src_nodata=src.nodata,
                    dst_transform=dst_transform,
                    dst_crs="EPSG:4326",
                    dst_nodata=np.nan,
                    resampling=resampling,
                    num_threads=2,
                )
                return out
        except Exception as exc:  # remote COG reads may need a retry
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Unable to read COG {href}: {last_error}")


def reflectance(asset: dict[str, Any], values: np.ndarray) -> np.ndarray:
    scale, offset = asset_scale_offset(asset)
    result = values * scale + offset
    finite = result[np.isfinite(result)]
    # Some STAC assets expose raw DN without an explicit raster scale.
    if finite.size and scale == 1.0 and float(np.nanpercentile(finite, 95)) > 2.0:
        result = values * 0.0001 + offset
    return result.astype(np.float32, copy=False)


def scene_record(item: dict[str, Any], cloud: float, asset_keys: dict[str, str]) -> dict[str, Any]:
    props = item.get("properties", {})
    return {
        "id": item.get("id"),
        "datetime": props.get("datetime"),
        "cloud_cover": cloud,
        "platform": props.get("platform"),
        "mgrs_grid": props.get("grid:code"),
        "assets": asset_keys,
    }


def tone_map(rgb: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    color = config["color"]
    gain = float(color["gain"])
    black = float(color["black_point"])
    gamma = float(color["gamma"])
    saturation = float(color["saturation"])
    contrast = float(color["contrast"])

    rgb = np.clip(rgb * gain - black, 0.0, 1.0)
    rgb = np.power(rgb, 1.0 / max(gamma, 1e-4))
    luminance = np.sum(rgb * np.array([0.2126, 0.7152, 0.0722], dtype=np.float32), axis=2, keepdims=True)
    rgb = luminance + (rgb - luminance) * saturation
    rgb = (rgb - 0.5) * contrast + 0.5
    return np.clip(rgb, 0.0, 1.0)


def repair_residual_nodata(composite: np.ndarray) -> np.ndarray:
    """Interpolate the tiny reprojection/cloud-mask seams left after compositing.

    The quality gate is evaluated *before* this function. This is intentionally
    not a way to rescue a poor source scene: only a composite with >=97% real
    valid coverage reaches here. GDAL's fillnodata then closes narrow tile-edge
    and reprojection seams using nearby valid reflectance values.
    """

    valid = np.all(np.isfinite(composite), axis=2)
    if valid.all():
        return composite

    mask = valid.astype(np.uint8)
    repaired = composite.copy()
    for band_index in range(3):
        band = repaired[:, :, band_index]
        work = np.where(np.isfinite(band), band, 0.0).astype(np.float32)
        repaired[:, :, band_index] = fillnodata(
            work,
            mask=mask,
            max_search_distance=256,
            smoothing_iterations=1,
        )

    # A no-data strip touching the outer raster edge can remain outside the
    # interpolation envelope. Extend the nearest valid edge values inward only
    # as a final boundary repair; this is bounded by the already-enforced 97%
    # real-data coverage threshold above.
    for _ in range(16):
        missing = ~np.all(np.isfinite(repaired), axis=2)
        if not missing.any():
            return repaired
        total = np.zeros_like(repaired, dtype=np.float32)
        count = np.zeros(repaired.shape[:2], dtype=np.uint8)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            shifted = np.roll(repaired, (dy, dx), axis=(0, 1))
            neighbour_valid = np.all(np.isfinite(shifted), axis=2)
            if dy == -1:
                neighbour_valid[-1, :] = False
            elif dy == 1:
                neighbour_valid[0, :] = False
            if dx == -1:
                neighbour_valid[:, -1] = False
            elif dx == 1:
                neighbour_valid[:, 0] = False
            total[neighbour_valid] += shifted[neighbour_valid]
            count[neighbour_valid] += 1
        fill = missing & (count > 0)
        if not fill.any():
            break
        repaired[fill] = total[fill] / count[fill, None]

    if not np.all(np.isfinite(repaired)):
        raise SystemExit("Satellite texture still contains no-data after bounded repair")
    return repaired


def main() -> None:
    args = parse_args()
    config = load_json(args.config)
    terrain = load_json(Path(config["terrain_manifest"]))
    bbox = terrain["bbox_wgs84"]
    west, south, east, north = (bbox["west"], bbox["south"], bbox["east"], bbox["north"])

    output = config["output"]
    width = int(output["width"])
    height = int(output["height"])
    dst_transform = from_bounds(west, south, east, north, width, height)

    source = config["source"]
    payload = {
        "collections": [source["collection"]],
        "bbox": [west, south, east, north],
        "datetime": source["datetime"],
        "limit": int(source["max_candidates"]),
        "query": {"eo:cloud_cover": {"lte": float(source["max_cloud_cover"]) }},
        "sortby": [
            {"field": "properties.eo:cloud_cover", "direction": "asc"},
            {"field": "properties.datetime", "direction": "desc"},
        ],
    }
    catalog = post_json(source["stac_url"], payload)
    items = catalog.get("features", [])
    if not items:
        raise SystemExit("No Sentinel-2 candidates found for Damavand imagery window")

    # Rasterio/GDAL settings for public Cloud Optimized GeoTIFF range reads.
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.tiff")
    os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")
    os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")

    composite = np.full((height, width, 3), np.nan, dtype=np.float32)
    covered = np.zeros((height, width), dtype=bool)
    used: list[dict[str, Any]] = []

    for item in items:
        props = item.get("properties", {})
        cloud = float(props.get("eo:cloud_cover") or 100.0)
        try:
            asset_keys: dict[str, str] = {}
            bands: list[np.ndarray] = []
            for common in ("red", "green", "blue"):
                key, asset = pick_asset(item, RGB_ASSET_KEYS[common])
                asset_keys[common] = key
                raw = read_reprojected(asset, width, height, dst_transform, resampling=Resampling.bilinear)
                bands.append(reflectance(asset, raw))

            rgb = np.stack(bands, axis=2)
            valid = np.all(np.isfinite(rgb), axis=2)

            try:
                scl_key, scl_asset = pick_asset(item, SCL_KEYS)
                asset_keys["scl"] = scl_key
                scl = read_reprojected(scl_asset, width, height, dst_transform, resampling=Resampling.nearest)
                scl_int = np.where(np.isfinite(scl), np.rint(scl), -1).astype(np.int16)
                valid &= ~np.isin(scl_int, BAD_SCL)
            except (KeyError, RuntimeError):
                # C1 scenes normally include SCL; retaining a fallback keeps a
                # clear low-cloud observation usable if metadata is incomplete.
                pass

            take = valid & ~covered
            if not np.any(take):
                continue
            composite[take] = rgb[take]
            covered[take] = True
            used.append(scene_record(item, cloud, asset_keys))

            coverage = float(covered.mean())
            print(f"used {item.get('id')} cloud={cloud:.2f}% coverage={coverage:.4%}", flush=True)
            if coverage >= 0.995:
                break
        except (KeyError, RuntimeError) as exc:
            print(f"skipping {item.get('id')}: {exc}", flush=True)

    coverage = float(covered.mean())
    if coverage < 0.97:
        raise SystemExit(f"Satellite composite coverage too low: {coverage:.2%}")

    composite = repair_residual_nodata(composite)

    display = tone_map(composite, config)
    image = Image.fromarray(np.rint(display * 255.0).astype(np.uint8))
    image = image.filter(ImageFilter.UnsharpMask(radius=0.8, percent=55, threshold=3))

    args.texture.parent.mkdir(parents=True, exist_ok=True)
    master_format = str(output.get("master_format", "png")).lower()
    if master_format != "png":
        raise SystemExit(f"Unsupported ultra-detail master format: {master_format}")
    image.save(args.texture, format="PNG", optimize=True, compress_level=6)

    preview_width = int(output["preview_width"])
    preview_height = max(1, round(image.height * preview_width / image.width))
    preview = image.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
    preview = ImageEnhance.Sharpness(preview).enhance(1.08)
    args.preview.parent.mkdir(parents=True, exist_ok=True)
    preview.save(args.preview, format="WEBP", quality=int(output["preview_quality"]), method=6)

    manifest = {
        "schema_version": 1,
        "peak_id": config["id"],
        "source": source,
        "bbox_wgs84": bbox,
        "texture": {
            "width": width,
            "height": height,
            "master_format": "image/png",
            "embedded_format": "image/webp",
            "webp_quality": int(output["webp_quality"]),
            "ground_resolution_m_approx": round(float(terrain["extent_km"]) * 1000.0 / width, 4),
            "coverage_percent": round(coverage * 100.0, 4),
            "orientation": "north-up; west-left; east-right; south-bottom",
            "embedded_in_model": "/models/damavand.glb",
        },
        "preview": "/img/peaks/damavand-sentinel.webp",
        "scenes": used,
        "processing": {
            "rgb": "Sentinel-2 B04/B03/B02 surface reflectance",
            "reprojection": "EPSG:4326 exact terrain bbox",
            "cloud_mask": "SCL classes 0,1,3,7,8,9,10 when available",
            "residual_nodata": "GDAL fillnodata after >=97% real source coverage",
            "authoring_master": "lossless PNG before final WebP encoding",
            "detail_policy": "native-detail preservation; no AI/synthetic super-resolution",
            "color": config["color"],
        },
        "attribution": source["attribution"],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"wrote {args.texture} ({args.texture.stat().st_size / 1024 / 1024:.2f} MiB), "
        f"coverage={coverage:.2%}, scenes={len(used)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
