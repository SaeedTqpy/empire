#!/usr/bin/env python3
from pathlib import Path

path = Path("src/three/engine.ts")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: anchor not found")
    text = text.replace(old, new, 1)
    print(f"{label}: applied")


replace_once(
    'import type { CameraMode } from "@/types/viewer-camera";\n',
    'import type { CameraMode } from "@/types/viewer-camera";\nimport type { GeoRoutePoint, RouteMetrics, TerrainGeoReference } from "@/types/route";\n',
    "route type import",
)

replace_once(
    'const DOWN = new THREE.Vector3(0, -1, 0);\n',
    '''const DOWN = new THREE.Vector3(0, -1, 0);\nconst EARTH_RADIUS_M = 6_371_008.8;\n\nfunction geoDistanceM(a: GeoRoutePoint, b: GeoRoutePoint) {\n  const lat1 = THREE.MathUtils.degToRad(a.lat);\n  const lat2 = THREE.MathUtils.degToRad(b.lat);\n  const dLat = lat2 - lat1;\n  const dLon = THREE.MathUtils.degToRad(b.lon - a.lon);\n  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;\n  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));\n}\n''',
    "geo distance helper",
)

replace_once(
    '''export interface LoadedModel {\n  group: THREE.Group;\n  meshes: THREE.Mesh[];\n  size: THREE.Vector3;\n  empireId: string;\n}\n''',
    '''export interface LoadedModel {\n  group: THREE.Group;\n  meshes: THREE.Mesh[];\n  size: THREE.Vector3;\n  empireId: string;\n  normalizationScale: number;\n  normalizationOffset: THREE.Vector3;\n}\n''',
    "loaded model georef fields",
)

replace_once(
    '''  private userAutoRotate = false;\n  private reducedMotion = false;\n''',
    '''  private userAutoRotate = false;\n  private terrainGeoRef: TerrainGeoReference | null = null;\n  private pendingRoute: { points: GeoRoutePoint[]; color: string } | null = null;\n  private routeMesh: THREE.Mesh | null = null;\n  private routeMetrics: RouteMetrics | null = null;\n  private routeBounds: THREE.Box3 | null = null;\n  private routeVisible = true;\n  private reducedMotion = false;\n''',
    "route engine fields",
)

replace_once(
    '    return { group, meshes, size: nsize, empireId: empire.id };\n',
    '''    return {\n      group,\n      meshes,\n      size: nsize,\n      empireId: empire.id,\n      normalizationScale: s,\n      normalizationOffset: inner.position.clone(),\n    };\n''',
    "normalization transform export",
)

replace_once(
    '''    this.current = model;\n    this.occlusionCache.clear();\n    this.attach(model);\n    this.touchResidency(model.empireId);\n''',
    '''    this.clearRouteMesh();\n    this.current = model;\n    this.occlusionCache.clear();\n    this.attach(model);\n    this.touchResidency(model.empireId);\n    this.rebuildRouteOverlay();\n''',
    "rebuild route on model present",
)

route_methods = r'''
  /* ── geospatial route system ──────────────────────────────────── */
  setTerrainGeoReference(reference: TerrainGeoReference) {
    this.terrainGeoRef = reference;
    return this.rebuildRouteOverlay();
  }

  setGeoRoute(points: GeoRoutePoint[], color = "#ef5b32"): RouteMetrics | null {
    this.pendingRoute = { points: points.map((point) => ({ ...point })), color };
    return this.rebuildRouteOverlay();
  }

  refreshRoute(): RouteMetrics | null {
    return this.rebuildRouteOverlay();
  }

  getRouteMetrics(): RouteMetrics | null {
    return this.routeMetrics;
  }

  setRouteVisible(visible: boolean) {
    this.routeVisible = visible;
    if (this.routeMesh) this.routeMesh.visible = visible;
  }

  clearRoute() {
    this.pendingRoute = null;
    this.routeMetrics = null;
    this.routeBounds = null;
    this.clearRouteMesh();
  }

  private clearRouteMesh() {
    if (!this.routeMesh) return;
    this.routeMesh.parent?.remove(this.routeMesh);
    this.routeMesh.geometry.dispose();
    const materials = Array.isArray(this.routeMesh.material) ? this.routeMesh.material : [this.routeMesh.material];
    materials.forEach((material) => material.dispose());
    this.routeMesh = null;
  }

  private densifyGeoRoute(points: GeoRoutePoint[], spacingM = 55): GeoRoutePoint[] {
    if (points.length < 2) return points;
    const dense: GeoRoutePoint[] = [{ ...points[0] }];
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1];
      const b = points[i];
      const steps = Math.max(1, Math.ceil(geoDistanceM(a, b) / spacingM));
      for (let step = 1; step <= steps; step++) {
        const t = step / steps;
        const bothElevation = Number.isFinite(a.elevationM) && Number.isFinite(b.elevationM);
        dense.push({
          lat: THREE.MathUtils.lerp(a.lat, b.lat, t),
          lon: THREE.MathUtils.lerp(a.lon, b.lon, t),
          elevationM: bothElevation ? THREE.MathUtils.lerp(a.elevationM!, b.elevationM!, t) : undefined,
          name: step === steps ? b.name : undefined,
        });
      }
    }
    return dense;
  }

  private routePointToSurface(point: GeoRoutePoint) {
    const model = this.current;
    const reference = this.terrainGeoRef;
    if (!model || !reference) return null;

    const centerLatRad = THREE.MathUtils.degToRad(reference.centerLat);
    const xPhysical = EARTH_RADIUS_M * Math.cos(centerLatRad) * THREE.MathUtils.degToRad(point.lon - reference.centerLon);
    const zPhysical = EARTH_RADIUS_M * THREE.MathUtils.degToRad(point.lat - reference.centerLat);
    const x = xPhysical * model.normalizationScale + model.normalizationOffset.x;
    const z = zPhysical * model.normalizationScale + model.normalizationOffset.z;

    model.group.updateMatrixWorld(true);
    const originLocal = new THREE.Vector3(x, model.size.y + 0.55, z);
    const originWorld = model.group.localToWorld(originLocal.clone());
    const ray = new THREE.Raycaster(originWorld, DOWN, 0, model.size.y + 1.2);
    ray.firstHitOnly = true;
    const hit = ray.intersectObjects(model.meshes, false)[0];
    if (!hit) return null;

    const local = model.group.worldToLocal(hit.point.clone());
    const elevationM =
      (local.y - model.normalizationOffset.y) / model.normalizationScale + reference.baseElevationM;
    // Eight physical metres is enough to avoid z-fighting without making the
    // route look detached from a 30 km terrain model.
    local.y += 8 * model.normalizationScale;
    return { local, elevationM, point };
  }

  private rebuildRouteOverlay(): RouteMetrics | null {
    this.clearRouteMesh();
    this.routeBounds = null;
    this.routeMetrics = null;
    const model = this.current;
    const route = this.pendingRoute;
    if (!model || !route || !this.terrainGeoRef || route.points.length < 2) return null;

    const dense = this.densifyGeoRoute(route.points);
    const projected = dense
      .map((point) => this.routePointToSurface(point))
      .filter((value): value is NonNullable<typeof value> => value !== null);
    if (projected.length < 2) return null;

    const localPoints = projected.map((item) => item.local);
    const path = new THREE.CurvePath<THREE.Vector3>();
    for (let i = 1; i < localPoints.length; i++) {
      path.add(new THREE.LineCurve3(localPoints[i - 1], localPoints[i]));
    }

    const routeRadius = Math.max(0.0008, 22 * model.normalizationScale);
    const tubularSegments = Math.min(1400, Math.max(80, localPoints.length * 2));
    const geometry = new THREE.TubeGeometry(path, tubularSegments, routeRadius, 6, false);
    const material = new THREE.MeshBasicMaterial({
      color: new THREE.Color(route.color),
      transparent: true,
      opacity: 0.96,
      depthTest: true,
      depthWrite: false,
      toneMapped: false,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = "peak-route-overlay";
    mesh.renderOrder = 6;
    mesh.visible = this.routeVisible;
    model.group.add(mesh);
    this.routeMesh = mesh;
    this.routeBounds = new THREE.Box3().setFromPoints(localPoints);

    let distanceM = 0;
    for (let i = 1; i < projected.length; i++) {
      distanceM += geoDistanceM(projected[i - 1].point, projected[i].point);
    }

    const elevations = projected.map((item) => item.elevationM);
    const smooth = elevations.map((_, index) => {
      const from = Math.max(0, index - 2);
      const to = Math.min(elevations.length, index + 3);
      let total = 0;
      for (let i = from; i < to; i++) total += elevations[i];
      return total / (to - from);
    });
    let ascent = 0;
    let descent = 0;
    for (let i = 1; i < smooth.length; i++) {
      const delta = smooth[i] - smooth[i - 1];
      if (Math.abs(delta) < 0.8) continue;
      if (delta > 0) ascent += delta;
      else descent -= delta;
    }

    this.routeMetrics = {
      distanceKm: distanceM / 1000,
      ascentM: ascent,
      descentM: descent,
      minElevationM: Math.min(...smooth),
      maxElevationM: Math.max(...smooth),
      sampledPoints: projected.length,
    };
    return this.routeMetrics;
  }

  focusRoute() {
    if (!this.routeBounds || !this.current || !this.controls) return;
    this.stopCinematic();
    this.killCameraMotion();
    this.cameraMode = "focus";
    this.cameraInterrupted = true;
    this.controls.autoRotate = false;

    const center = this.routeBounds.getCenter(new THREE.Vector3());
    const size = this.routeBounds.getSize(new THREE.Vector3());
    const radius = Math.max(0.22, Math.hypot(size.x, size.z) * 0.5, size.y * 0.65);
    const tan = Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2);
    const distance = THREE.MathUtils.clamp(
      (radius / Math.max(0.2, tan)) * 1.6,
      this.controls.minDistance + 0.02,
      this.controls.maxDistance - 0.02,
    );

    this.cameraTween = gsap.to(this.camState, {
      tx: center.x,
      ty: center.y,
      tz: center.z,
      dist: distance,
      el: 37,
      duration: this.reducedMotion ? 0 : 1.25,
      ease: "power3.inOut",
      onUpdate: () => this.applyCam(),
      onComplete: () => {
        this.cameraTween = null;
        this.cameraMode = "manual";
        this.controls.autoRotate = this.userAutoRotate;
      },
      onInterrupt: () => {
        this.cameraTween = null;
      },
    });
  }

'''

marker = "  /* ── camera system ─────────────────────────────────────────────── */\n"
if "setTerrainGeoReference(reference: TerrainGeoReference)" not in text:
    if marker not in text:
        raise SystemExit("route methods: camera marker not found")
    text = text.replace(marker, route_methods + marker, 1)
    print("route methods: applied")
else:
    print("route methods: already applied")

replace_once(
    '''  dispose() {\n    this.disposed = true;\n''',
    '''  dispose() {\n    this.disposed = true;\n    this.clearRouteMesh();\n''',
    "route dispose",
)

path.write_text(text, encoding="utf-8")
