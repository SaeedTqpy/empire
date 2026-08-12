#!/usr/bin/env python3
"""Offline guardrails for the Phase 8 Damavand VHR contract.

This intentionally does not call any remote service. Network/source discovery
is handled by separate probes; this gate prevents later code changes from
quietly claiming a zoom/resolution beyond the source metadata we validated.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

DATA = Path("src/data/peaks/damavand.ts")
TEXT = DATA.read_text(encoding="utf-8")

EXPECTED_ITEM = "b4c5c1b59c4141c5b503335b5baa2df4"
EXPECTED_TEMPLATE_TOKEN = "/tile/22869/{level}/{row}/{col}"
EXPECTED_MAX_ZOOM = 18
EXPECTED_SOURCE_RES = 0.34
EXPECTED_SAMPLE_RES = 0.6
EXPECTED_BBOX = (52.0312477, 35.6338357, 52.1723191, 35.958038)
SUMMIT = (52.1097, 35.9513)


def capture(pattern: str) -> str:
    match = re.search(pattern, TEXT)
    if not match:
        raise SystemExit(f"Phase 8 contract missing pattern: {pattern}")
    return match.group(1)


item = capture(r'itemId:\s*"([^"]+)"')
max_zoom = int(capture(r"maxZoom:\s*(\d+)"))
source_res = float(capture(r"observedResolutionM:\s*([0-9.]+)"))
sample_res = float(capture(r"sampledResolutionM:\s*([0-9.]+)"))

bbox_match = re.search(r"coverageBboxWgs84:\s*\[([^\]]+)\]", TEXT)
if not bbox_match:
    raise SystemExit("Phase 8 coverage bbox is missing")
bbox = tuple(float(value.strip()) for value in bbox_match.group(1).split(","))

if item != EXPECTED_ITEM:
    raise SystemExit(f"Unexpected Wayback item: {item}")
if EXPECTED_TEMPLATE_TOKEN not in TEXT:
    raise SystemExit("Runtime tile template no longer matches the validated Wayback snapshot")
if max_zoom != EXPECTED_MAX_ZOOM:
    raise SystemExit(f"maxZoom must remain {EXPECTED_MAX_ZOOM}; got {max_zoom}")
if not math.isclose(source_res, EXPECTED_SOURCE_RES, abs_tol=1e-9):
    raise SystemExit(f"Observed source resolution changed: {source_res}")
if not math.isclose(sample_res, EXPECTED_SAMPLE_RES, abs_tol=1e-9):
    raise SystemExit(f"Sampled resolution changed: {sample_res}")
if len(bbox) != 4 or any(not math.isclose(a, b, abs_tol=1e-7) for a, b in zip(bbox, EXPECTED_BBOX)):
    raise SystemExit(f"Validated source bbox changed: {bbox}")

west, south, east, north = bbox
lon, lat = SUMMIT
if not (west <= lon <= east and south <= lat <= north):
    raise SystemExit("Validated VHR bbox no longer contains Damavand summit")

# Make accidental offline bundling obvious. This provider is runtime-only.
for path in Path("public").rglob("*"):
    if not path.is_file():
        continue
    lowered = path.name.lower()
    if "wayback" in lowered or "vantor" in lowered or "vivid" in lowered:
        raise SystemExit(f"Runtime-only VHR imagery must not be bundled under public/: {path}")

print(
    "Phase 8 contract OK: Wayback item, z18 cap, 0.34m source / 0.6m sampled metadata, "
    "validated summit coverage, no bundled VHR tiles."
)
