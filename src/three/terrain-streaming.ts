import * as THREE from "three";
import { TilesRenderer } from "3d-tiles-renderer/three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import type {
  DetailImageryStatus,
  TerrainStreamingConfig,
  TerrainStreamingStats,
} from "@/types/streaming";
import { createDamavandVhrOverlay } from "@/three/damavand-vhr-overlay";

interface ResolutionRenderer {
  getPixelRatio(): number;
  getSize(target: THREE.Vector2): THREE.Vector2;
}

/**
 * Adapter around NASA/JPL's 3d-tiles-renderer.
 *
 * Visual terrain streams independently from the hidden interaction mesh used
 * by routes/hotspots. Phase 8 optionally registers a runtime-only high-detail
 * image overlay; the source remains remote and is never bundled into tiles.
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
  private detailImageryStatus: DetailImageryStatus = "off";

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
    tiles.manager.addHandler(/\.gltf$/i, gltf);
    tiles.manager.addHandler(/\.glb$/i, gltf);

    const detailConfig = config.detailImagery;
    const detailDisabled =
      typeof window !== "undefined" && new URLSearchParams(window.location.search).get("detail") === "0";

    if (detailConfig?.enabled && !detailDisabled) {
      this.detailImageryStatus = "initializing";
      try {
        const { overlay, plugin } = createDamavandVhrOverlay(detailConfig, renderer);
        tiles.registerPlugin(plugin);
        void overlay
          .whenReady()
          .then(() => {
            if (this.detailImageryStatus === "initializing") {
              this.detailImageryStatus = "active";
              this.emitStats(true);
            }
          })
          .catch((error: unknown) => {
            console.warn("high-detail imagery initialization failed; keeping Sentinel fallback", error);
            this.detailImageryStatus = "error";
            this.emitStats(true);
          });
      } catch (error) {
        console.warn("high-detail imagery plugin unavailable; keeping Sentinel fallback", error);
        this.detailImageryStatus = "error";
      }
    }

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
    tiles.addEventListener("load-error", (event) => {
      // ImageOverlayPlugin adds an `overlay` property to the same event. A VHR
      // fetch failure must never kill the terrain: the embedded Sentinel-2
      // material remains a complete visual fallback.
      const isOverlayError = Object.prototype.hasOwnProperty.call(event, "overlay");
      if (isOverlayError) {
        this.detailImageryStatus = "error";
        console.warn("high-detail imagery tile failed; keeping Sentinel fallback", event.error);
        this.emitStats(true);
        return;
      }

      if (!this.firstVisualSeen) {
        this.failed = true;
        this.loading = false;
        this.onFatalError?.(event.error);
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
    const detail = this.config.detailImagery;
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
      detailImageryStatus: this.detailImageryStatus,
      detailImageryLabel: detail?.sourceLabel,
      detailImageryResolutionM: detail?.sampledResolutionM,
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
