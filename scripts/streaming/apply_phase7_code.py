#!/usr/bin/env python3
"""Apply the Phase 7 3D Tiles / LOD runtime migration.

The migration is guarded and idempotent so CI can rebuild the generated spatial
assets independently while the active mountain viewer keeps a deterministic
fallback to the canonical single GLB.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def write_new(path: str, content: str) -> None:
    target = ROOT / path
    if target.exists() and target.read_text(encoding="utf-8") == content:
        print(f"{path}: already up to date")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"{path}: written")


def replace_once(path: str, old: str, new: str, label: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: source anchor not found in {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


write_new(
    "src/types/streaming.ts",
    '''/** Phase 7 spatial terrain-streaming contracts. */
export interface TerrainStreamingConfig {
  enabled: boolean;
  tilesetPath: string;
  /** Lightweight whole-mountain mesh retained for routes, hotspots and fallback. */
  interactionModelPath: string;
  datasetVersion: string;
  /** Screen-space error target in CSS/render pixels. Lower means more detail. */
  targetSSE: number;
  maxDepth: number;
}

export type TerrainStreamingMode = "3d-tiles" | "fallback";

export interface TerrainStreamingStats {
  mode: TerrainStreamingMode;
  loading: boolean;
  progress: number;
  visibleTiles: number;
  activeTiles: number;
  loadedTiles: number;
  visibleDepth: number;
  maxDepth: number;
  failed: boolean;
}
''',
)

write_new(
    "src/three/terrain-streaming.ts",
    '''import * as THREE from "three";
import { TilesRenderer } from "3d-tiles-renderer/three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import type { TerrainStreamingConfig, TerrainStreamingStats } from "@/types/streaming";

interface ResolutionRenderer {
  getPixelRatio(): number;
  getSize(target: THREE.Vector2): THREE.Vector2;
}

/**
 * Small adapter around NASA/JPL's 3d-tiles-renderer.
 *
 * It owns only visual terrain. The ViewerEngine keeps its lightweight hidden
 * interaction mesh for deterministic route/hotspot projection, so spatial LOD
 * can evolve independently from product interaction semantics.
 */
export class TerrainTilesStreamer {
  readonly group: THREE.Group;

  private readonly tiles: TilesRenderer;
  private readonly camera: THREE.PerspectiveCamera;
  private readonly renderer: ResolutionRenderer;
  private readonly config: TerrainStreamingConfig;
  private readonly maxAnisotropy: number;
  private loadedModels = 0;
  private firstVisualSeen = false;
  private failed = false;
  private loading = true;
  private wireframe = false;
  private xray = false;
  private lastStatsAt = 0;

  onStats: ((stats: TerrainStreamingStats) => void) | null = null;
  onFirstVisual: (() => void) | null = null;
  onFatalError: ((error: Error) => void) | null = null;

  constructor(
    config: TerrainStreamingConfig,
    camera: THREE.PerspectiveCamera,
    renderer: ResolutionRenderer,
    maxAnisotropy: number,
  ) {
    this.config = config;
    this.camera = camera;
    this.renderer = renderer;
    this.maxAnisotropy = maxAnisotropy;

    const tiles = new TilesRenderer(config.tilesetPath);
    this.tiles = tiles;
    this.group = tiles.group;

    const nav = navigator as Navigator & { deviceMemory?: number };
    const memoryGb = nav.deviceMemory ?? 8;
    const constrained = memoryGb <= 4;
    tiles.errorTarget = constrained ? Math.max(4, config.targetSSE) : config.targetSSE;
    tiles.maxDepth = config.maxDepth;
    tiles.loadAncestors = true;
    tiles.loadSiblings = !constrained;
    tiles.maxTilesProcessed = constrained ? 48 : 96;
    tiles.downloadQueue.maxJobs = constrained ? 4 : 8;
    tiles.parseQueue.maxJobs = constrained ? 2 : 4;
    tiles.lruCache.minSize = constrained ? 8 : 16;
    tiles.lruCache.maxSize = constrained ? 36 : 72;
    tiles.lruCache.minBytesSize = constrained ? 48 * 1024 * 1024 : 96 * 1024 * 1024;
    tiles.lruCache.maxBytesSize = constrained ? 128 * 1024 * 1024 : 256 * 1024 * 1024;
    tiles.lruCache.unloadPercent = 0.18;

    const draco = new DRACOLoader(tiles.manager).setDecoderPath("/draco/gltf/");
    const gltf = new GLTFLoader(tiles.manager);
    gltf.setDRACOLoader(draco);
    tiles.manager.addHandler(/\\.gltf$/i, gltf);
    tiles.manager.addHandler(/\\.glb$/i, gltf);

    tiles.setCamera(camera);
    this.syncResolution();

    tiles.addEventListener("tiles-load-start", () => {
      this.loading = true;
      this.emitStats(true);
    });
    tiles.addEventListener("tiles-load-end", () => {
      this.loading = false;
      this.emitStats(true);
    });
    tiles.addEventListener("load-model", ({ scene }) => {
      this.loadedModels += 1;
      this.prepareScene(scene);
      if (!this.firstVisualSeen) {
        this.firstVisualSeen = true;
        this.onFirstVisual?.();
      }
      this.emitStats(true);
    });
    tiles.addEventListener("dispose-model", () => {
      this.loadedModels = Math.max(0, this.loadedModels - 1);
      this.emitStats(true);
    });
    tiles.addEventListener("load-error", ({ error }) => {
      if (!this.firstVisualSeen) {
        this.failed = true;
        this.loading = false;
        this.onFatalError?.(error);
      }
      this.emitStats(true);
    });
  }

  private tuneTexture(texture: THREE.Texture | null) {
    if (!texture) return;
    texture.anisotropy = this.maxAnisotropy;
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.generateMipmaps = true;
    texture.needsUpdate = true;
  }

  private prepareScene(scene: THREE.Object3D) {
    scene.traverse((object) => {
      if (!(object instanceof THREE.Mesh)) return;
      object.castShadow = true;
      object.receiveShadow = true;
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      for (const material of materials) {
        if (!(material instanceof THREE.MeshStandardMaterial)) continue;
        this.tuneTexture(material.map);
        this.tuneTexture(material.normalMap);
        this.tuneTexture(material.roughnessMap);
        this.tuneTexture(material.metalnessMap);
        this.tuneTexture(material.aoMap);
        material.wireframe = this.wireframe;
        material.transparent = this.xray;
        material.opacity = this.xray ? 0.42 : 1;
        material.depthWrite = !this.xray;
        material.needsUpdate = true;
      }
    });
  }

  syncResolution() {
    const size = this.renderer.getSize(new THREE.Vector2());
    const ratio = this.renderer.getPixelRatio();
    this.tiles.setResolution(this.camera, Math.max(1, size.x * ratio), Math.max(1, size.y * ratio));
  }

  update() {
    if (this.failed) return;
    this.camera.updateMatrixWorld();
    this.tiles.update();
    this.emitStats(false);
  }

  private emitStats(force: boolean) {
    const now = performance.now();
    if (!force && now - this.lastStatsAt < 180) return;
    this.lastStatsAt = now;

    let visibleDepth = 0;
    for (const tile of this.tiles.visibleTiles) {
      visibleDepth = Math.max(visibleDepth, tile.internal.depth);
    }
    this.onStats?.({
      mode: this.failed ? "fallback" : "3d-tiles",
      loading: this.loading,
      progress: this.tiles.loadProgress,
      visibleTiles: this.tiles.visibleTiles.size,
      activeTiles: this.tiles.activeTiles.size,
      loadedTiles: this.loadedModels,
      visibleDepth,
      maxDepth: this.config.maxDepth,
      failed: this.failed,
    });
  }

  private forEachMaterial(callback: (material: THREE.MeshStandardMaterial) => void) {
    this.tiles.forEachLoadedModel((scene) => {
      scene.traverse((object) => {
        if (!(object instanceof THREE.Mesh)) return;
        const materials = Array.isArray(object.material) ? object.material : [object.material];
        for (const material of materials) {
          if (material instanceof THREE.MeshStandardMaterial) callback(material);
        }
      });
    });
  }

  setWireframe(enabled: boolean) {
    this.wireframe = enabled;
    this.forEachMaterial((material) => {
      material.wireframe = enabled;
      material.needsUpdate = true;
    });
  }

  setXray(enabled: boolean) {
    this.xray = enabled;
    this.forEachMaterial((material) => {
      material.transparent = enabled;
      material.opacity = enabled ? 0.42 : 1;
      material.depthWrite = !enabled;
      material.needsUpdate = true;
    });
  }

  dispose() {
    this.tiles.deleteCamera(this.camera);
    this.tiles.dispose();
    this.group.removeFromParent();
  }
}
''',
)

replace_once(
    "src/types/peak.ts",
    'import type { PeakRoute } from "./route";\n',
    'import type { PeakRoute } from "./route";\nimport type { TerrainStreamingConfig } from "./streaming";\n',
    "Peak streaming type import",
)
replace_once(
    "src/types/peak.ts",
    '''  /** 1.0 means elevations are rendered in their real physical proportion. */\n  verticalExaggeration: number;\n  sourceLabel: string;\n''',
    '''  /** 1.0 means elevations are rendered in their real physical proportion. */\n  verticalExaggeration: number;\n  sourceLabel: string;\n  /** Phase 7 spatial LOD. The canonical model remains the full fallback. */\n  streaming?: TerrainStreamingConfig;\n''',
    "Peak terrain streaming contract",
)

replace_once(
    "src/types/empire.ts",
    '/** Empire Atlas — core data contracts.\n',
    'import type { TerrainStreamingConfig } from "./streaming";\n\n/** Empire Atlas — core data contracts.\n',
    "Viewer streaming type import",
)
replace_once(
    "src/types/empire.ts",
    '''  modelPath: string;\n  /** Optional public credit for imagery baked into the model. */\n''',
    '''  modelPath: string;\n  /** Optional Phase 7 spatial LOD configuration. */\n  streaming?: TerrainStreamingConfig;\n  /** Optional public credit for imagery baked into the model. */\n''',
    "Viewer streaming contract",
)

replace_once(
    "src/lib/peak-viewer-adapter.ts",
    '''    modelPath: peak.modelPath,\n    imageryAttribution: peak.terrain.imageryAttribution,\n''',
    '''    modelPath: peak.modelPath,\n    streaming: peak.terrain.streaming,\n    imageryAttribution: peak.terrain.imageryAttribution,\n''',
    "Peak adapter streaming mapping",
)

replace_once(
    "src/data/peaks/damavand.ts",
    '''    sourceLabel: "SRTM terrain + Copernicus Sentinel-2 imagery",\n  },\n''',
    '''    sourceLabel: "SRTM terrain + Copernicus Sentinel-2 imagery",\n    streaming: {\n      enabled: true,\n      tilesetPath: "/tiles/damavand/phase7-v1/tileset.json",\n      interactionModelPath: "/tiles/damavand/phase7-v1/interaction.glb",\n      datasetVersion: "phase7-v1",\n      targetSSE: 2.5,\n      maxDepth: 2,\n    },\n  },\n''',
    "Damavand streaming dataset",
)

replace_once(
    "src/three/engine.ts",
    'import type { GeoRoutePoint, RouteMetrics, TerrainGeoReference } from "@/types/route";\n',
    'import type { GeoRoutePoint, RouteMetrics, TerrainGeoReference } from "@/types/route";\nimport type { TerrainStreamingStats } from "@/types/streaming";\nimport { TerrainTilesStreamer } from "@/three/terrain-streaming";\n',
    "ViewerEngine streaming imports",
)
replace_once(
    "src/three/engine.ts",
    '''  private maxTextureAnisotropy = 8;\n  private ready = false;\n\n  onLoadProgress: ((pct: number) => void) | null = null;\n''',
    '''  private maxTextureAnisotropy = 8;\n  private terrainStreamer: TerrainTilesStreamer | null = null;\n  private streamingWireframe = false;\n  private streamingXray = false;\n  private ready = false;\n\n  onLoadProgress: ((pct: number) => void) | null = null;\n  onStreamingStats: ((stats: TerrainStreamingStats) => void) | null = null;\n''',
    "ViewerEngine streaming state",
)
replace_once(
    "src/three/engine.ts",
    '''    this.renderer.setPixelRatio(ratio);\n    this.renderer.setSize(w, h, false);\n    this.markShadowDirty(2);\n''',
    '''    this.renderer.setPixelRatio(ratio);\n    this.renderer.setSize(w, h, false);\n    this.terrainStreamer?.syncResolution();\n    this.markShadowDirty(2);\n''',
    "Streaming resolution sync",
)
replace_once(
    "src/three/engine.ts",
    '''    this.controls?.update();\n    // idle glow pulse — only worth computing while something is highlighted\n''',
    '''    this.controls?.update();\n    this.terrainStreamer?.update();\n    // idle glow pulse — only worth computing while something is highlighted\n''',
    "Streaming frame traversal",
)
replace_once(
    "src/three/engine.ts",
    '''  load(empire: Empire): Promise<LoadedModel> {\n    const cached = this.cache.get(empire.id);\n    if (cached) return cached;\n    const p = new Promise<LoadedModel>((resolve, reject) => {\n      this.loader.load(\n        empire.modelPath,\n''',
    '''  private streamingEnabled(empire: Empire) {\n    const queryDisabled = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("streaming") === "0";\n    return !queryDisabled && Boolean(empire.streaming?.enabled);\n  }\n\n  load(empire: Empire): Promise<LoadedModel> {\n    const cached = this.cache.get(empire.id);\n    if (cached) return cached;\n    const modelPath = this.streamingEnabled(empire) && empire.streaming\n      ? empire.streaming.interactionModelPath\n      : empire.modelPath;\n    const p = new Promise<LoadedModel>((resolve, reject) => {\n      this.loader.load(\n        modelPath,\n''',
    "Streaming interaction model load",
)
replace_once(
    "src/three/engine.ts",
    '''  /** Hand the stage over: `model` becomes the current dwelling. Recently\n   *  seen dwellings stay parsed and resident, so switching back to one is\n   *  instant instead of a fresh download, re-parse and re-snap. */\n  present(model: LoadedModel) {\n    const old = this.current;\n    if (old && old.empireId !== model.empireId) this.stage.remove(old.group);\n    this.clearRouteMesh();\n    this.geoHotspotLocal.clear();\n    this.current = model;\n    this.occlusionCache.clear();\n    this.attach(model);\n    this.touchResidency(model.empireId);\n    this.rebuildRouteOverlay();\n  }\n''',
    '''  private stopTerrainStreaming() {\n    this.terrainStreamer?.dispose();\n    this.terrainStreamer = null;\n  }\n\n  private startTerrainStreaming(model: LoadedModel, empire: Empire) {\n    this.stopTerrainStreaming();\n    if (!this.streamingEnabled(empire) || !empire.streaming) {\n      model.meshes.forEach((mesh) => { mesh.visible = true; });\n      return;\n    }\n\n    const streamer = new TerrainTilesStreamer(\n      empire.streaming,\n      this.camera,\n      this.renderer,\n      this.maxTextureAnisotropy,\n    );\n    this.terrainStreamer = streamer;\n    streamer.group.scale.setScalar(model.normalizationScale);\n    streamer.group.position.copy(model.normalizationOffset);\n    model.group.add(streamer.group);\n    streamer.setWireframe(this.streamingWireframe);\n    streamer.setXray(this.streamingXray);\n    streamer.onStats = (stats) => this.onStreamingStats?.(stats);\n    streamer.onFirstVisual = () => {\n      // The proxy stays in the scene graph for BVH/raycast interaction, but it\n      // no longer contributes fragments once streamed terrain is available.\n      model.meshes.forEach((mesh) => { mesh.visible = false; });\n      this.markShadowDirty(2);\n    };\n    streamer.onFatalError = (error) => {\n      console.error("terrain streaming failed; keeping canonical proxy fallback", error);\n      model.meshes.forEach((mesh) => { mesh.visible = true; });\n      this.stopTerrainStreaming();\n      this.onStreamingStats?.({\n        mode: "fallback", loading: false, progress: 1, visibleTiles: 0,\n        activeTiles: 0, loadedTiles: 0, visibleDepth: 0,\n        maxDepth: empire.streaming?.maxDepth ?? 0, failed: true,\n      });\n    };\n    streamer.syncResolution();\n  }\n\n  /** Hand the stage over: `model` becomes the current mountain. */\n  present(model: LoadedModel, empire?: Empire) {\n    const old = this.current;\n    if (old && old.empireId !== model.empireId) this.stage.remove(old.group);\n    this.stopTerrainStreaming();\n    this.clearRouteMesh();\n    this.geoHotspotLocal.clear();\n    this.current = model;\n    this.occlusionCache.clear();\n    model.meshes.forEach((mesh) => { mesh.visible = true; });\n    this.attach(model);\n    this.touchResidency(model.empireId);\n    this.rebuildRouteOverlay();\n    if (empire) this.startTerrainStreaming(model, empire);\n  }\n''',
    "Streaming visual terrain lifecycle",
)
replace_once(
    "src/three/engine.ts",
    '      this.present(next);\n      onMidpoint?.();\n',
    '      this.present(next, empire);\n      onMidpoint?.();\n',
    "Streaming transition handover",
)
replace_once(
    "src/three/engine.ts",
    '''  setWireframe(on: boolean) {\n    if (on && this.current && !this.wireOverlay) {\n''',
    '''  setWireframe(on: boolean) {\n    this.streamingWireframe = on;\n    if (this.terrainStreamer) {\n      this.terrainStreamer.setWireframe(on);\n      return;\n    }\n    if (on && this.current && !this.wireOverlay) {\n''',
    "Streaming wireframe mode",
)
replace_once(
    "src/three/engine.ts",
    '''  setXray(on: boolean) {\n    if (!this.current) return;\n''',
    '''  setXray(on: boolean) {\n    this.streamingXray = on;\n    if (this.terrainStreamer) {\n      this.terrainStreamer.setXray(on);\n      return;\n    }\n    if (!this.current) return;\n''',
    "Streaming xray mode",
)
replace_once(
    "src/three/engine.ts",
    '''  dispose() {\n    this.disposed = true;\n    this.clearRouteMesh();\n''',
    '''  dispose() {\n    this.disposed = true;\n    this.stopTerrainStreaming();\n    this.clearRouteMesh();\n''',
    "Streaming disposal",
)

replace_once(
    "src/components/Viewer.tsx",
    'import type { PeakRoute, RouteDocument, RouteMetrics, TerrainManifestDocument } from "@/types/route";\n',
    'import type { PeakRoute, RouteDocument, RouteMetrics, TerrainManifestDocument } from "@/types/route";\nimport type { TerrainStreamingStats } from "@/types/streaming";\n',
    "Viewer streaming stats import",
)
replace_once(
    "src/components/Viewer.tsx",
    '''  const [routeImported, setRouteImported] = useState(false);\n  const requestRef = useRef(0);\n''',
    '''  const [routeImported, setRouteImported] = useState(false);\n  const [streamingStats, setStreamingStats] = useState<TerrainStreamingStats | null>(null);\n  const requestRef = useRef(0);\n''',
    "Viewer streaming stats state",
)
replace_once(
    "src/components/Viewer.tsx",
    '''      engine.onLoadProgress = (pct) => {\n        setLoading((l) => (l ? { ...l, pct } : null));\n      };\n      setEngineReady(true);\n''',
    '''      engine.onLoadProgress = (pct) => {\n        setLoading((l) => (l ? { ...l, pct } : null));\n      };\n      engine.onStreamingStats = setStreamingStats;\n      setEngineReady(true);\n''',
    "Viewer streaming event bridge",
)
replace_once(
    "src/components/Viewer.tsx",
    '''        {empire.imageryAttribution && (\n          <div className="viewer-attribution" aria-label="Satellite imagery attribution">\n            {empire.imageryAttribution}\n          </div>\n        )}\n      </div>\n''',
    '''        {empire.imageryAttribution && (\n          <div className="viewer-attribution" aria-label="Satellite imagery attribution">\n            {empire.imageryAttribution}\n          </div>\n        )}\n        {streamingStats && (\n          <div\n            className={`streaming-status ${streamingStats.failed ? "is-fallback" : ""}`}\n            aria-live="polite"\n            title="Camera-driven spatial level of detail"\n          >\n            <span className="streaming-status__dot" />\n            {streamingStats.mode === "3d-tiles"\n              ? `3D Tiles · LOD ${streamingStats.visibleDepth}/${streamingStats.maxDepth} · ${streamingStats.visibleTiles} visible${streamingStats.loading ? " · loading" : ""}`\n              : "Terrain fallback · streaming unavailable"}\n          </div>\n        )}\n      </div>\n''',
    "Viewer streaming status UI",
)

css_path = ROOT / "src/terrain.css"
css = css_path.read_text(encoding="utf-8")
css_block = '''\n\n/* Phase 7 spatial 3D Tiles status */\n.streaming-status {\n  position: absolute;\n  left: 10px;\n  bottom: 8px;\n  z-index: 19;\n  display: inline-flex;\n  align-items: center;\n  gap: 6px;\n  border: 1px solid rgb(255 255 255 / 0.38);\n  border-radius: 999px;\n  background: rgb(28 43 49 / 0.54);\n  padding: 5px 8px;\n  color: rgb(248 251 250 / 0.9);\n  font-size: 9px;\n  font-weight: 700;\n  line-height: 1;\n  letter-spacing: 0.025em;\n  backdrop-filter: blur(6px);\n  pointer-events: none;\n}\n\n.streaming-status__dot {\n  width: 6px;\n  height: 6px;\n  border-radius: 999px;\n  background: #82c9a3;\n  box-shadow: 0 0 0 3px rgb(130 201 163 / 0.16);\n}\n\n.streaming-status.is-fallback .streaming-status__dot {\n  background: #e2a45e;\n  box-shadow: 0 0 0 3px rgb(226 164 94 / 0.16);\n}\n\n@media (max-width: 639px) {\n  .streaming-status {\n    left: 7px;\n    bottom: 6px;\n    max-width: 48%;\n    overflow: hidden;\n    font-size: 8px;\n    text-overflow: ellipsis;\n    white-space: nowrap;\n  }\n}\n'''
if "/* Phase 7 spatial 3D Tiles status */" not in css:
    css_path.write_text(css + css_block, encoding="utf-8")
    print("Phase 7 streaming CSS: applied")
else:
    print("Phase 7 streaming CSS: already applied")

print("Phase 7 spatial streaming runtime migration complete")
