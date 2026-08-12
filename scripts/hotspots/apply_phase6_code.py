#!/usr/bin/env python3
"""Apply Phase 6 geo-aware mountain hotspots and peak UI.

The migration is intentionally idempotent and validates exact source anchors
before rewriting the large ViewerEngine/Viewer files.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


def replace_once(rel: str, old: str, new: str, label: str) -> None:
    text = read(rel)
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: source anchor not found in {rel}")
    write(rel, text.replace(old, new, 1))
    print(f"{label}: applied")


def append_once(rel: str, marker: str, payload: str, label: str) -> None:
    text = read(rel)
    if marker in text:
        print(f"{label}: already applied")
        return
    write(rel, text.rstrip() + "\n\n" + payload.strip() + "\n")
    print(f"{label}: applied")


# ---------------------------------------------------------------------------
# Peak domain: geographic marker metadata becomes first-class.
# ---------------------------------------------------------------------------
replace_once(
    "src/types/peak.ts",
    '''export interface PeakHotspot {
  id: string;
  title: string;
  short: string;
  detail: string;
  category: PeakHotspotCategory;
  anchor: Vec3;
  focus?: number;
}''',
    '''export interface PeakHotspot {
  id: string;
  title: string;
  short: string;
  detail: string;
  category: PeakHotspotCategory;
  /** Optional legacy normalized fallback for non-georeferenced models. */
  anchor?: Vec3;
  /** Preferred Phase 6 placement: WGS84 lat/lon raycast onto the terrain. */
  coordinates?: PeakCoordinates;
  /** Reference metadata only; rendered Y comes from the DEM surface. */
  elevationM?: number;
  sourceLabel?: string;
  focus?: number;
}''',
    "peak hotspot geo contract",
)

# ---------------------------------------------------------------------------
# Temporary legacy viewer boundary: allow mountain categories + geo payload.
# ---------------------------------------------------------------------------
replace_once(
    "src/types/empire.ts",
    '  category: "structure" | "roof" | "court" | "entrance" | "interior" | "artifact-zone" | "facade";',
    '  category: "structure" | "roof" | "court" | "entrance" | "interior" | "artifact-zone" | "facade" | "summit" | "shelter" | "landmark" | "hazard" | "water" | "route";',
    "viewer hotspot categories",
)
replace_once(
    "src/types/empire.ts",
    '''  anchor: Vec3;
  /** Which kind of surface the pin belongs on.''',
    '''  anchor: Vec3;
  /** Phase 6 geographic placement for real terrain peaks. */
  geo?: { lat: number; lon: number; elevationM?: number; sourceLabel?: string };
  /** Which kind of surface the pin belongs on.''',
    "viewer hotspot geo payload",
)

# ---------------------------------------------------------------------------
# Peak -> viewer adapter: preserve Peak semantics across the legacy boundary.
# ---------------------------------------------------------------------------
replace_once(
    "src/lib/peak-viewer-adapter.ts",
    'import type { Peak } from "@/types/peak";',
    'import type { Peak, PeakHotspot, Vec3 } from "@/types/peak";',
    "adapter imports",
)
replace_once(
    "src/lib/peak-viewer-adapter.ts",
    '''/**
 * Temporary phase-1 boundary between the new Peak domain and the untouched
 * Empire viewer engine. Keeping the adapter here lets the domain migrate
 * cleanly without destabilizing the rendering stack before the DEM arrives.
 */
export function peakToViewerModel(peak: Peak): Empire {''',
    '''const EARTH_RADIUS_M = 6_371_008.8;

function hotspotFallbackAnchor(peak: Peak, hotspot: PeakHotspot): Vec3 {
  if (hotspot.anchor) return hotspot.anchor;
  if (!hotspot.coordinates) return [0.5, 0.5, 0.5];
  const extentM = peak.terrain.extentKm * 1000;
  const centerLatRad = (peak.coordinates.lat * Math.PI) / 180;
  const eastM = EARTH_RADIUS_M * Math.cos(centerLatRad) * (((hotspot.coordinates.lon - peak.coordinates.lon) * Math.PI) / 180);
  const northM = EARTH_RADIUS_M * (((hotspot.coordinates.lat - peak.coordinates.lat) * Math.PI) / 180);
  const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
  return [clamp01(0.5 + eastM / extentM), 0.5, clamp01(0.5 + northM / extentM)];
}

/**
 * Temporary compatibility boundary while the old viewer types are retired.
 * Peak semantics, including Phase 6 geo markers, stay intact across it.
 */
export function peakToViewerModel(peak: Peak): Empire {''',
    "adapter fallback projection",
)
replace_once(
    "src/lib/peak-viewer-adapter.ts",
    '''      category: "structure",
      anchor: hotspot.anchor,
      focus: hotspot.focus,''',
    '''      category: hotspot.category,
      anchor: hotspotFallbackAnchor(peak, hotspot),
      geo: hotspot.coordinates
        ? {
            lat: hotspot.coordinates.lat,
            lon: hotspot.coordinates.lon,
            elevationM: hotspot.elevationM,
            sourceLabel: hotspot.sourceLabel,
          }
        : undefined,
      focus: hotspot.focus,''',
    "adapter hotspot mapping",
)

# ---------------------------------------------------------------------------
# Damavand dataset uses a dedicated marker module.
# ---------------------------------------------------------------------------
replace_once(
    "src/data/peaks/damavand.ts",
    'import type { Peak } from "@/types/peak";',
    'import type { Peak } from "@/types/peak";\nimport { damavandHotspots } from "./damavand-hotspots";',
    "Damavand hotspot import",
)
replace_once(
    "src/data/peaks/damavand.ts",
    '''  // Geo-aware hotspots are added once route projection is introduced.
  hotspots: [],''',
    '''  // Phase 6 markers use WGS84 coordinates and are raycast onto the DEM.
  hotspots: damavandHotspots,''',
    "Damavand hotspot data",
)

# ---------------------------------------------------------------------------
# ViewerEngine: cached WGS84 -> normalized DEM surface projection.
# ---------------------------------------------------------------------------
replace_once(
    "src/three/engine.ts",
    'import type { Empire, Vec3 } from "@/types/empire";',
    'import type { Empire, Hotspot, Vec3 } from "@/types/empire";',
    "engine hotspot type import",
)
replace_once(
    "src/three/engine.ts",
    '''  private routeBounds: THREE.Box3 | null = null;
  private routeVisible = true;''',
    '''  private routeBounds: THREE.Box3 | null = null;
  private routeVisible = true;
  /** Geo marker positions are static for a loaded DEM; resolve each once. */
  private geoHotspotLocal = new Map<string, THREE.Vector3>();
  private hotspotRay = new THREE.Raycaster();''',
    "engine geo hotspot fields",
)
replace_once(
    "src/three/engine.ts",
    '''    this.clearRouteMesh();
    this.current = model;
    this.occlusionCache.clear();''',
    '''    this.clearRouteMesh();
    this.geoHotspotLocal.clear();
    this.current = model;
    this.occlusionCache.clear();''',
    "clear geo marker cache on model present",
)
replace_once(
    "src/three/engine.ts",
    '''  setTerrainGeoReference(reference: TerrainGeoReference) {
    this.terrainGeoRef = reference;
    return this.rebuildRouteOverlay();
  }''',
    '''  setTerrainGeoReference(reference: TerrainGeoReference) {
    this.terrainGeoRef = reference;
    this.geoHotspotLocal.clear();
    return this.rebuildRouteOverlay();
  }''',
    "clear geo marker cache on georef",
)
replace_once(
    "src/three/engine.ts",
    '''  anchorToWorld(anchor: Vec3, out = new THREE.Vector3()): THREE.Vector3 {
    if (!this.current) return out.set(0, 0, 0);
    const cached = this.snapped.get(`${this.current.empireId}:${anchor.join(",")}`);
    if (cached) out.copy(cached);
    else this.boxAnchor(anchor, this.current, out);
    return this.current.group.localToWorld(out);
  }

  project(world: THREE.Vector3, w: number, h: number): AnchorProjection {''',
    '''  anchorToWorld(anchor: Vec3, out = new THREE.Vector3()): THREE.Vector3 {
    if (!this.current) return out.set(0, 0, 0);
    const cached = this.snapped.get(`${this.current.empireId}:${anchor.join(",")}`);
    if (cached) out.copy(cached);
    else this.boxAnchor(anchor, this.current, out);
    return this.current.group.localToWorld(out);
  }

  private resolveGeoHotspotLocal(hotspot: Hotspot): THREE.Vector3 | null {
    const model = this.current;
    const reference = this.terrainGeoRef;
    if (!model || !reference || !hotspot.geo) return null;
    const key = `${model.empireId}:${hotspot.id}:${hotspot.geo.lat.toFixed(7)}:${hotspot.geo.lon.toFixed(7)}`;
    const cached = this.geoHotspotLocal.get(key);
    if (cached) return cached;

    const centerLatRad = THREE.MathUtils.degToRad(reference.centerLat);
    const xPhysical = EARTH_RADIUS_M * Math.cos(centerLatRad) * THREE.MathUtils.degToRad(hotspot.geo.lon - reference.centerLon);
    const zPhysical = EARTH_RADIUS_M * THREE.MathUtils.degToRad(hotspot.geo.lat - reference.centerLat);
    const x = xPhysical * model.normalizationScale + model.normalizationOffset.x;
    const z = zPhysical * model.normalizationScale + model.normalizationOffset.z;

    model.group.updateMatrixWorld(true);
    const originLocal = new THREE.Vector3(x, model.size.y + 0.55, z);
    const originWorld = model.group.localToWorld(originLocal.clone());
    this.hotspotRay.set(originWorld, DOWN);
    this.hotspotRay.near = 0;
    this.hotspotRay.far = model.size.y + 1.2;
    this.hotspotRay.firstHitOnly = true;
    const hit = this.hotspotRay.intersectObjects(model.meshes, false)[0];
    if (!hit) return null;

    const local = model.group.worldToLocal(hit.point.clone());
    // Marker pin: a small physical lift from the DEM surface, independent of
    // normalized presentation scale.
    local.y += 18 * model.normalizationScale;
    this.geoHotspotLocal.set(key, local.clone());
    return local;
  }

  hotspotToWorld(hotspot: Hotspot, out = new THREE.Vector3()): THREE.Vector3 {
    if (!this.current) return out.set(0, 0, 0);
    const geoLocal = this.resolveGeoHotspotLocal(hotspot);
    if (geoLocal) {
      out.copy(geoLocal);
      return this.current.group.localToWorld(out);
    }
    return this.anchorToWorld(hotspot.anchor, out);
  }

  project(world: THREE.Vector3, w: number, h: number): AnchorProjection {''',
    "engine geo hotspot surface projection",
)
replace_once(
    "src/three/engine.ts",
    '''  focusAnchor(anchor: Vec3, empire: Empire, dur = 1.2) {
    if (!this.current) return;
    this.killCameraMotion();
    this.cameraInterrupted = true;
    this.cameraMode = "focus";
    if (this.controls) this.controls.autoRotate = false;
    const world = this.anchorToWorld(anchor);
    const az = this.camState.az;
    this.cameraTween = gsap.to(this.camState, {
      dist: this.fitDistance(empire, 0.62),
      tx: world.x * 0.72,
      ty: world.y * 0.72 + 0.06,
      tz: world.z * 0.72,
      az,
      duration: this.reducedMotion ? 0 : dur,
      ease: "power3.inOut",
      onUpdate: () => this.applyCam(),
      onComplete: () => {
        this.cameraTween = null;
        this.cameraMode = "manual";
        if (this.controls) this.controls.autoRotate = this.userAutoRotate;
      },
      onInterrupt: () => {
        this.cameraTween = null;
      },
    });
  }

  resetPeakView(empire: Empire, animate = true) {''',
    '''  focusAnchor(anchor: Vec3, empire: Empire, dur = 1.2) {
    if (!this.current) return;
    this.killCameraMotion();
    this.cameraInterrupted = true;
    this.cameraMode = "focus";
    if (this.controls) this.controls.autoRotate = false;
    const world = this.anchorToWorld(anchor);
    const az = this.camState.az;
    this.cameraTween = gsap.to(this.camState, {
      dist: this.fitDistance(empire, 0.62),
      tx: world.x * 0.72,
      ty: world.y * 0.72 + 0.06,
      tz: world.z * 0.72,
      az,
      duration: this.reducedMotion ? 0 : dur,
      ease: "power3.inOut",
      onUpdate: () => this.applyCam(),
      onComplete: () => {
        this.cameraTween = null;
        this.cameraMode = "manual";
        if (this.controls) this.controls.autoRotate = this.userAutoRotate;
      },
      onInterrupt: () => {
        this.cameraTween = null;
      },
    });
  }

  focusHotspot(hotspot: Hotspot, empire: Empire, dur = 1.15) {
    if (!this.current) return;
    this.killCameraMotion();
    this.cameraInterrupted = true;
    this.cameraMode = "focus";
    if (this.controls) this.controls.autoRotate = false;
    const world = this.hotspotToWorld(hotspot);
    const focus = THREE.MathUtils.clamp(hotspot.focus ?? 1, 0.72, 1.2);
    const margin = THREE.MathUtils.clamp(0.68 / focus, 0.48, 0.8);
    this.cameraTween = gsap.to(this.camState, {
      dist: THREE.MathUtils.clamp(this.fitDistance(empire, margin), this.controls.minDistance, this.controls.maxDistance),
      tx: world.x,
      ty: world.y + 0.035,
      tz: world.z,
      az: this.camState.az,
      el: THREE.MathUtils.clamp(this.camState.el, 24, 58),
      duration: this.reducedMotion ? 0 : dur,
      ease: "power3.inOut",
      onUpdate: () => this.applyCam(),
      onComplete: () => {
        this.cameraTween = null;
        this.cameraMode = "manual";
        if (this.controls) this.controls.autoRotate = this.userAutoRotate;
      },
      onInterrupt: () => {
        this.cameraTween = null;
      },
    });
  }

  resetPeakView(empire: Empire, animate = true) {''',
    "engine geo hotspot focus",
)
replace_once(
    "src/three/engine.ts",
    '''  setHighlight(anchor: Vec3 | null) {
    if (!this.glowShell) return;
    if (anchor === null) {
      this.glowShell.visible = false;
      return;
    }
    const world = this.anchorToWorld(anchor);
    this.glowShell.position.copy(this.stage.worldToLocal(world.clone()));
    this.glowShell.visible = true;
  }

  setReducedMotion(v: boolean) {''',
    '''  setHighlight(anchor: Vec3 | null) {
    if (!this.glowShell) return;
    if (anchor === null) {
      this.glowShell.visible = false;
      return;
    }
    const world = this.anchorToWorld(anchor);
    this.glowShell.scale.setScalar(1);
    this.glowShell.position.copy(this.stage.worldToLocal(world.clone()));
    this.glowShell.visible = true;
  }

  setHotspotHighlight(hotspot: Hotspot | null) {
    if (!this.glowShell) return;
    if (!hotspot) {
      this.glowShell.visible = false;
      return;
    }
    const world = this.hotspotToWorld(hotspot);
    this.glowShell.scale.setScalar(hotspot.geo ? 0.34 : 1);
    this.glowShell.position.copy(this.stage.worldToLocal(world.clone()));
    this.glowShell.visible = true;
  }

  setReducedMotion(v: boolean) {''',
    "engine geo hotspot highlight",
)

# ---------------------------------------------------------------------------
# Hotspot overlay: category filtering + geo-aware world positions.
# ---------------------------------------------------------------------------
replace_once(
    "src/components/HotspotLayer.tsx",
    '''  visible: boolean;
}''',
    '''  visible: boolean;
  categoryFilter: string | null;
}''',
    "HotspotLayer filter prop",
)
replace_once(
    "src/components/HotspotLayer.tsx",
    '''  onActivate,
  visible,
}: Props) {''',
    '''  onActivate,
  visible,
  categoryFilter,
}: Props) {''',
    "HotspotLayer filter destructure",
)
replace_once(
    "src/components/HotspotLayer.tsx",
    '''  /* world positions, allocated once per empire and rewritten in place */
  const anchors = useMemo(
    () => empire.hotspots.map((hs) => ({ id: hs.id, world: new THREE.Vector3() })),
    [empire],
  );''',
    '''  const visibleHotspots = useMemo(
    () => (categoryFilter ? empire.hotspots.filter((hotspot) => hotspot.category === categoryFilter) : empire.hotspots),
    [empire, categoryFilter],
  );

  /* world positions, allocated once per visible marker and rewritten in place */
  const anchors = useMemo(
    () => visibleHotspots.map((hs) => ({ id: hs.id, world: new THREE.Vector3() })),
    [visibleHotspots],
  );''',
    "HotspotLayer filtered marker list",
)
replace_once(
    "src/components/HotspotLayer.tsx",
    '''      for (let i = 0; i < empire.hotspots.length; i++) {
        const hs = empire.hotspots[i];''',
    '''      for (let i = 0; i < visibleHotspots.length; i++) {
        const hs = visibleHotspots[i];''',
    "HotspotLayer filtered frame loop",
)
replace_once(
    "src/components/HotspotLayer.tsx",
    '        const world = engine.anchorToWorld(hs.anchor, anchors[i].world);',
    '        const world = engine.hotspotToWorld(hs, anchors[i].world);',
    "HotspotLayer geo projection",
)
replace_once(
    "src/components/HotspotLayer.tsx",
    '''  }, [engine, empire, anchors, activeId, hoverId, visible]);''',
    '''  }, [engine, visibleHotspots, anchors, activeId, hoverId, visible]);''',
    "HotspotLayer frame dependencies",
)
replace_once(
    "src/components/HotspotLayer.tsx",
    '  const hovered = empire.hotspots.find((h) => h.id === hoverId) ?? null;',
    '  const hovered = visibleHotspots.find((h) => h.id === hoverId) ?? null;',
    "HotspotLayer filtered tooltip",
)
replace_once(
    "src/components/HotspotLayer.tsx",
    '      aria-label="Architectural markers"',
    '      aria-label="Mountain markers"',
    "HotspotLayer aria label",
)
replace_once(
    "src/components/HotspotLayer.tsx",
    '''      {empire.hotspots.map((hs) => (
        <button
          key={hs.id}
          className="hs-pin"
          data-hs={hs.id}''',
    '''      {visibleHotspots.map((hs) => (
        <button
          key={hs.id}
          className="hs-pin"
          data-hs={hs.id}
          data-category={hs.category}''',
    "HotspotLayer category pin data",
)

# ---------------------------------------------------------------------------
# Viewer: mountain marker filter, geo focus, richer marker detail, remove the
# remaining Artifacts/Timeline museum controls.
# ---------------------------------------------------------------------------
replace_once(
    "src/components/Viewer.tsx",
    '''  VaseIcon,
  TimelineIcon,
''',
    '',
    "remove legacy viewer icon imports",
)
replace_once(
    "src/components/Viewer.tsx",
    '''  onArtifacts: () => void;
  onTimeline: () => void;
''',
    '',
    "remove legacy viewer props",
)
replace_once(
    "src/components/Viewer.tsx",
    '''  onFocusHandled,
  onArtifacts,
  onTimeline,
  onPrefetchReady,''',
    '''  onFocusHandled,
  onPrefetchReady,''',
    "remove legacy viewer destructure",
)
replace_once(
    "src/components/Viewer.tsx",
    '''  const [tipVisible, setTipVisible] = useState(true);
  const [routeMetrics, setRouteMetrics] = useState<RouteMetrics | null>(null);''',
    '''  const [tipVisible, setTipVisible] = useState(true);
  const [hotspotFilter, setHotspotFilter] = useState<string | null>(null);
  const [routeMetrics, setRouteMetrics] = useState<RouteMetrics | null>(null);''',
    "viewer marker filter state",
)
replace_once(
    "src/components/Viewer.tsx",
    '''  const activeHs = empire.hotspots.find((h) => h.id === activeId) ?? null;
  const builtInRoute = routes[0] ?? null;''',
    '''  const activeHs = empire.hotspots.find((h) => h.id === activeId) ?? null;
  const hotspotCategories = [...new Set(empire.hotspots.map((hotspot) => hotspot.category))];
  const builtInRoute = routes[0] ?? null;''',
    "viewer marker categories",
)
replace_once(
    "src/components/Viewer.tsx",
    '''      setActiveId(null);
      setHoverId(null);
      setMarkersVisible(false);''',
    '''      setActiveId(null);
      setHoverId(null);
      setHotspotFilter(null);
      setMarkersVisible(false);''',
    "reset marker filter on peak change",
)
replace_once(
    "src/components/Viewer.tsx",
    '''    if (activeHs) {
      engine.focusAnchor(activeHs.anchor, empire);
      engine.setHighlight(activeHs.anchor);
    } else {
      engine.setHighlight(null);
    }''',
    '''    if (activeHs) {
      engine.focusHotspot(activeHs, empire);
      engine.setHotspotHighlight(activeHs);
    } else {
      engine.setHotspotHighlight(null);
    }''',
    "viewer geo marker focus",
)
replace_once(
    "src/components/Viewer.tsx",
    '''        onActivate={setActiveId}
        visible={markersVisible && layers.labels}
      />''',
    '''        onActivate={setActiveId}
        visible={markersVisible && layers.labels}
        categoryFilter={hotspotFilter}
      />

      {empire.hotspots.length > 0 && (
        <div className="hotspot-filter" role="group" aria-label="Filter mountain markers">
          <button
            className={`hotspot-filter__chip ${hotspotFilter === null ? "is-on" : ""}`}
            onClick={() => {
              setActiveId(null);
              setHoverId(null);
              setHotspotFilter(null);
            }}
          >
            All <span>{empire.hotspots.length}</span>
          </button>
          {hotspotCategories.map((category) => (
            <button
              key={category}
              data-category={category}
              className={`hotspot-filter__chip ${hotspotFilter === category ? "is-on" : ""}`}
              onClick={() => {
                setActiveId(null);
                setHoverId(null);
                setHotspotFilter(hotspotFilter === category ? null : category);
              }}
            >
              {category.replace("-", " ")}
            </button>
          ))}
        </div>
      )}''',
    "viewer marker category filter",
)
replace_once(
    "src/components/Viewer.tsx",
    '''          <button className="tool-btn" onClick={onArtifacts}>
            <VaseIcon />
            <span>Artifacts</span>
          </button>
          <button className="tool-btn" onClick={onTimeline}>
            <TimelineIcon />
            <span>Timeline</span>
          </button>
''',
    '',
    "remove museum toolbar controls",
)
replace_once(
    "src/components/Viewer.tsx",
    '''        <div
          className="atlas-card absolute bottom-4 left-1/2 z-30 w-[min(430px,calc(100%-140px))] -translate-x-1/2 !rounded-2xl p-4"
          role="dialog"
          aria-label={activeHs.title}
        >''',
    '''        <div
          className="atlas-card hotspot-detail absolute bottom-4 left-1/2 z-30 w-[min(460px,calc(100%-140px))] -translate-x-1/2 !rounded-2xl p-4"
          data-category={activeHs.category}
          role="dialog"
          aria-label={activeHs.title}
        >''',
    "marker detail category styling",
)
replace_once(
    "src/components/Viewer.tsx",
    '''          <p className="font-display mt-2 text-[0.98rem] italic leading-snug text-ink-muted">{activeHs.short}</p>
          <p className="mt-2 text-[0.86rem] leading-relaxed text-ink-soft">{activeHs.detail}</p>
        </div>''',
    '''          <p className="font-display mt-2 text-[0.98rem] italic leading-snug text-ink-muted">{activeHs.short}</p>
          {activeHs.geo && (
            <div className="hotspot-detail__meta">
              <div>
                <span>Reference elevation</span>
                <strong>{activeHs.geo.elevationM ? `${activeHs.geo.elevationM.toLocaleString()} m` : "DEM surface"}</strong>
              </div>
              <div>
                <span>Coordinates</span>
                <strong>{activeHs.geo.lat.toFixed(5)}, {activeHs.geo.lon.toFixed(5)}</strong>
              </div>
            </div>
          )}
          <p className="mt-2 text-[0.86rem] leading-relaxed text-ink-soft">{activeHs.detail}</p>
          {activeHs.geo?.sourceLabel && <p className="hotspot-detail__source">Source: {activeHs.geo.sourceLabel}</p>}
        </div>''',
    "marker detail geo metadata",
)
replace_once(
    "src/components/Viewer.tsx",
    '''            The route is clamped to the DEM. Import a GPX to compare your own track in 3D.''',
    '''            Click a mountain marker to fly to its real DEM position. Use the chips above to isolate summits, shelters, water, landmarks and hazards.''',
    "viewer Phase 6 tip",
)
replace_once(
    "src/components/Viewer.tsx",
    '''            <p className="loading-fact font-display mt-3 text-[0.85rem] italic text-ink-muted">Preparing terrain, imagery and route layers…</p>''',
    '''            <p className="loading-fact font-display mt-3 text-[0.85rem] italic text-ink-muted">Preparing terrain, imagery, routes and mountain markers…</p>''',
    "viewer Phase 6 loading copy",
)

# App no longer passes museum-only callbacks.
replace_once(
    "src/App.tsx",
    '''            onFocusHandled={() => undefined}
            onArtifacts={() => undefined}
            onTimeline={() => undefined}
          />''',
    '''            onFocusHandled={() => undefined}
          />''',
    "App viewer props cleanup",
)

# Peak panel status copy.
replace_once(
    "src/components/PeakInfoPanel.tsx",
    '''Real terrain + Sentinel-2 · cinematic camera · 3D routes + local GPX import.''',
    '''Real terrain + Sentinel-2 · cinematic camera · 3D routes · geo-aware mountain markers.''',
    "PeakInfoPanel Phase 6 status",
)

# ---------------------------------------------------------------------------
# Phase 6 UI — category-coded pins, compact filter and richer detail card.
# ---------------------------------------------------------------------------
append_once(
    "src/terrain.css",
    "/* Phase 6 geo-aware mountain markers */",
    '''/* Phase 6 geo-aware mountain markers */
.hotspot-filter {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 31;
  display: flex;
  max-width: min(72%, 620px);
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  pointer-events: auto;
}

.hotspot-filter__chip {
  border: 1px solid rgb(255 255 255 / 0.56);
  border-radius: 999px;
  background: rgb(36 52 58 / 0.62);
  padding: 6px 9px;
  color: rgb(248 250 248 / 0.9);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1;
  text-transform: uppercase;
  backdrop-filter: blur(7px);
  transition: transform 160ms ease, background 160ms ease, border-color 160ms ease;
}

.hotspot-filter__chip:hover,
.hotspot-filter__chip.is-on {
  transform: translateY(-1px);
  border-color: rgb(255 255 255 / 0.9);
  background: rgb(29 44 49 / 0.86);
}

.hotspot-filter__chip span {
  margin-left: 3px;
  opacity: 0.65;
}

.hs-pin[data-category="summit"] .core { background: #f6b73c; }
.hs-pin[data-category="shelter"] .core { background: #4c8fbd; }
.hs-pin[data-category="landmark"] .core { background: #9b72c7; }
.hs-pin[data-category="hazard"] .core { background: #d9584c; }
.hs-pin[data-category="water"] .core { background: #38a3c7; }
.hs-pin[data-category="route"] .core { background: #dd7d3c; }

.hotspot-detail {
  border-top-width: 3px;
  border-top-color: #788c94;
}
.hotspot-detail[data-category="summit"] { border-top-color: #f6b73c; }
.hotspot-detail[data-category="shelter"] { border-top-color: #4c8fbd; }
.hotspot-detail[data-category="landmark"] { border-top-color: #9b72c7; }
.hotspot-detail[data-category="hazard"] { border-top-color: #d9584c; }
.hotspot-detail[data-category="water"] { border-top-color: #38a3c7; }
.hotspot-detail[data-category="route"] { border-top-color: #dd7d3c; }

.hotspot-detail__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.hotspot-detail__meta > div {
  min-width: 0;
  border: 1px solid rgb(104 119 123 / 0.2);
  border-radius: 10px;
  background: rgb(255 255 255 / 0.3);
  padding: 8px 10px;
}

.hotspot-detail__meta span,
.hotspot-detail__meta strong {
  display: block;
}

.hotspot-detail__meta span {
  color: rgb(84 97 100 / 0.76);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.hotspot-detail__meta strong {
  margin-top: 3px;
  overflow: hidden;
  color: rgb(37 48 50 / 0.94);
  font-size: 12px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotspot-detail__source {
  margin-top: 10px;
  border-top: 1px solid rgb(104 119 123 / 0.18);
  padding-top: 8px;
  color: rgb(84 97 100 / 0.68);
  font-size: 10px;
  line-height: 1.35;
}

@media (max-width: 639px) {
  .hotspot-filter {
    top: 8px;
    right: 8px;
    left: 72px;
    max-width: none;
    gap: 4px;
  }

  .hotspot-filter__chip {
    padding: 5px 7px;
    font-size: 8px;
  }

  .hotspot-detail__meta {
    grid-template-columns: 1fr;
  }
}''',
    "Phase 6 marker UI styles",
)

print("Phase 6 hotspot migration complete")
