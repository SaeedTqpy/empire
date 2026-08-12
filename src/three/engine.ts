/**
 * ViewerEngine — the museum-quality 3D stage for the Empire Atlas.
 *
 * Renderer: three.js WebGPURenderer (WebGPU where available, WebGL2 fallback),
 * with TSL node materials for atmosphere, contact shadow, rim light and the
 * selection glow. Models are normalized into a consistent museum frame and
 * occluded markers use BVH-accelerated raycasts.
 */
import * as THREE from "three/webgpu";
import {
  color,
  float,
  normalView,
  positionLocal,
  positionViewDirection,
  smoothstep,
  uniform,
} from "three/tsl";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from "three-mesh-bvh";
import gsap from "gsap";
import type { Empire, Hotspot, Vec3 } from "@/types/empire";
import type { CameraMode } from "@/types/viewer-camera";
import type { GeoRoutePoint, RouteMetrics, TerrainGeoReference } from "@/types/route";

THREE.Mesh.prototype.raycast = acceleratedRaycast;
(THREE.BufferGeometry.prototype as any).computeBoundsTree = computeBoundsTree;
(THREE.BufferGeometry.prototype as any).disposeBoundsTree = disposeBoundsTree;

/** dwellings kept parsed in memory at once (~2MB of source geometry each) */
const MAX_RESIDENT = 6;
const TARGET_SIZE = 2.0; // normalized model footprint, world units
const UP = new THREE.Vector3(0, 1, 0);
const DOWN = new THREE.Vector3(0, -1, 0);
const EARTH_RADIUS_M = 6_371_008.8;

function geoDistanceM(a: GeoRoutePoint, b: GeoRoutePoint) {
  const lat1 = THREE.MathUtils.degToRad(a.lat);
  const lat2 = THREE.MathUtils.degToRad(b.lat);
  const dLat = lat2 - lat1;
  const dLon = THREE.MathUtils.degToRad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

export interface AnchorProjection {
  x: number;
  y: number;
  /** distance from camera to the anchor, world units (drives depth scaling) */
  distance: number;
  behindCamera: boolean;
  occluded: boolean;
}

export interface LoadedModel {
  group: THREE.Group;
  meshes: THREE.Mesh[];
  size: THREE.Vector3;
  empireId: string;
  normalizationScale: number;
  normalizationOffset: THREE.Vector3;
}

type FrameCallback = () => void;

/** Top-surface heights over a model's footprint, in model-local units. */
interface HeightField {
  n: number;
  y: Float32Array;
  min: number;
  max: number;
}

export class ViewerEngine {
  private canvas: HTMLCanvasElement;
  private renderer!: THREE.WebGPURenderer;
  private scene!: THREE.Scene;
  private camera!: THREE.PerspectiveCamera;
  private controls!: OrbitControls;
  private loader: GLTFLoader;
  private manager: THREE.LoadingManager;

  private stage = new THREE.Group(); // holds the model group
  private current: LoadedModel | null = null;
  private cache = new Map<string, Promise<LoadedModel>>();
  private frameCbs = new Set<FrameCallback>();
  private raycaster = new THREE.Raycaster();
  private glowShell: THREE.Mesh | null = null;
  private glowPulse = uniform(0.6);
  private rimColor = uniform(new THREE.Color(0xffe8c8));
  private rimIntensity = uniform(0.055);
  private wireOverlay: THREE.Mesh | null = null;
  private grid: THREE.PolarGridHelper | null = null;
  /* lighting rig — kept as fields so an empire swap can re-tint it */
  private keyLight!: THREE.DirectionalLight;
  private rimLight!: THREE.DirectionalLight;
  private bounceLight!: THREE.DirectionalLight;
  private envTex: THREE.Texture | null = null;
  private contact: THREE.Mesh | null = null;
  private contactOpacity = uniform(0.24);
  private occlusionTimer = 0;
  private occlusionCache = new Map<string, boolean>();
  /** anchors resolved onto the mesh surface, keyed empireId:anchor */
  private snapped = new Map<string, THREE.Vector3>();
  /** per-model top-surface height fields, built once on first use */
  private fields = new Map<string, HeightField>();
  /** empire ids by recency; the tail is evicted once past MAX_RESIDENT */
  private lru: string[] = [];
  /** the swap currently playing, so a new request can interrupt it */
  private activeTl: gsap.core.Timeline | null = null;
  private activeResolve: (() => void) | null = null;
  /** waiting beneath the parchment, attached but not yet handed over */
  private staged: LoadedModel | null = null;
  private clock = new THREE.Clock();
  private disposed = false;
  /** frames of shadow-map refresh still owed (see renderer.shadowMap.autoUpdate) */
  private shadowDirty = 2;
  /** models retired mid-transition; freed once the animation is over */
  private retired: LoadedModel[] = [];
  private resizeObs: ResizeObserver | null = null;
  /** throwaway target used to warm a model's pipelines off-screen */
  private warmTarget: THREE.RenderTarget | null = null;
  private projScratch = new THREE.Vector3();
  private occScratch = new THREE.Vector3();
  private camState = { az: -38, el: 34, dist: 2.6, tx: 0, ty: 0.4, tz: 0 };
  private cameraMode: CameraMode = "loading";
  private cameraTl: gsap.core.Timeline | null = null;
  private cameraTween: gsap.core.Tween | null = null;
  private cameraInterrupted = false;
  private userAutoRotate = false;
  private terrainGeoRef: TerrainGeoReference | null = null;
  private pendingRoute: { points: GeoRoutePoint[]; color: string } | null = null;
  private routeMesh: THREE.Mesh | null = null;
  private routeMetrics: RouteMetrics | null = null;
  private routeBounds: THREE.Box3 | null = null;
  private routeVisible = true;
  /** Geo marker positions are static for a loaded DEM; resolve each once. */
  private geoHotspotLocal = new Map<string, THREE.Vector3>();
  private hotspotRay = new THREE.Raycaster();
  private reducedMotion = false;
  private maxTextureAnisotropy = 8;
  private ready = false;

  onLoadProgress: ((pct: number) => void) | null = null;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.manager = new THREE.LoadingManager();
    this.manager.onProgress = (_u, loaded, total) => {
      if (this.onLoadProgress && total > 0) this.onLoadProgress(Math.round((loaded / total) * 100));
    };
    const draco = new DRACOLoader(this.manager).setDecoderPath("/draco/gltf/");
    this.loader = new GLTFLoader(this.manager);
    this.loader.setDRACOLoader(draco);
  }

  async init() {
    const renderer = new THREE.WebGPURenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      forceWebGL: true,
    });
    // the stage backdrop is painted in CSS, not in the scene: filmic tone
    // mapping would drain the warmth out of a rendered parchment gradient
    renderer.setClearColor(0x000000, 0);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    await renderer.init();
    this.renderer = renderer;
    const caps = (renderer as any).capabilities;
    const reportedAnisotropy = caps?.getMaxAnisotropy?.();
    this.maxTextureAnisotropy = Number.isFinite(reportedAnisotropy)
      ? Math.max(1, Math.min(16, reportedAnisotropy))
      : 8;

    const scene = new THREE.Scene();
    this.scene = scene;

    scene.fog = new THREE.Fog(0xc7d7df, 7.5, 22);

    this.camera = new THREE.PerspectiveCamera(38, 1, 0.002, 60);
    this.camera.position.set(-1.7, 1.6, 2.4);

    // ── Image-based light: a warm gallery dome so PBR surfaces pick up
    //    sky above / parchment floor bounce instead of flat directional light ──
    this.envTex = this.buildEnvironment();
    if (this.envTex) {
      scene.environment = this.envTex;
      // enough ambient to fill shadow, not so much that everything goes flat
      scene.environmentIntensity = 0.62;
    }

    // ── Lighting: hard sun over soft ambient. The ambient terms stay low so
    //    that form reads through shadow rather than washing out. ──
    const hemi = new THREE.HemisphereLight(0xdcebf4, 0x706b5c, 0.34);
    scene.add(hemi);

    const key = new THREE.DirectionalLight(0xfff3dc, 3.6);
    key.position.set(4.5, 6.0, 2.8);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = -2.2;
    key.shadow.camera.right = 2.2;
    key.shadow.camera.top = 2.2;
    key.shadow.camera.bottom = -2.2;
    key.shadow.camera.near = 0.5;
    key.shadow.camera.far = 14;
    key.shadow.bias = -0.00016;
    key.shadow.normalBias = 0.018;
    // tight penumbra — architecture wants crisp eaves, not a haze
    key.shadow.radius = 1.8;
    // Orbiting moves the camera, not the building, so the shadow map is only
    // redrawn when the geometry actually changes — the biggest per-frame win.
    key.shadow.autoUpdate = false;
    key.shadow.needsUpdate = true;
    scene.add(key);
    this.keyLight = key;

    // cool sky fill opposite the key — keeps shadow sides from going muddy
    const fill = new THREE.DirectionalLight(0xb8d0df, 0.30);
    fill.position.set(-3.6, 2.1, -1.7);
    scene.add(fill);

    // warm back rim — separates the silhouette from the parchment backdrop
    const rim = new THREE.DirectionalLight(0xffe0ad, 0.32);
    rim.position.set(-2.1, 2.7, -3.7);
    scene.add(rim);
    this.rimLight = rim;

    // floor bounce — a soft upward warmth under eaves and colonnades
    const bounce = new THREE.DirectionalLight(0xc9c0a8, 0.12);
    bounce.position.set(0.5, -2.0, 2.4);
    scene.add(bounce);
    this.bounceLight = bounce;

    // ── Ground: a parchment disc that dissolves into the backdrop, so the
    //    dwelling reads as resting on paper rather than on a visible slab ──
    let ground: THREE.Mesh;
    try {
      const gm = new THREE.MeshStandardNodeMaterial({ roughness: 1, metalness: 0, transparent: true });
      gm.colorNode = color(0xbfc1b6);
      gm.opacityNode = smoothstep(0.62, 0.98, positionLocal.xy.length().div(4.2)).oneMinus();
      ground = new THREE.Mesh(new THREE.CircleGeometry(4.2, 96), gm);
    } catch {
      ground = new THREE.Mesh(
        new THREE.CircleGeometry(9, 72),
        new THREE.MeshStandardMaterial({ color: 0xb9baae, roughness: 1, metalness: 0 }),
      );
    }
    ground.rotation.x = -Math.PI / 2;
    // a hair below the dwellings, whose own base slab sits at y=0: coplanar
    // surfaces z-fight, and the shimmer shows up whenever the camera moves
    ground.position.y = -0.014;
    ground.receiveShadow = true;
    scene.add(ground);

    try {
      const shadowMat = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false });
      const d = positionLocal.xy.length().div(1.35);
      shadowMat.colorNode = color(0x2b1f14);
      shadowMat.opacityNode = smoothstep(0.05, 0.88, d).oneMinus().mul(this.contactOpacity);
      const contact = new THREE.Mesh(new THREE.CircleGeometry(1.35, 64), shadowMat);
      contact.rotation.x = -Math.PI / 2;
      contact.position.y = -0.007;
      contact.renderOrder = 1;
      this.contact = contact;
      this.stage.add(contact);
    } catch {
      /* standard shadow map remains as fallback */
    }

    // ── Selection glow shell (TSL fresnel, additive) ──
    try {
      const glowMat = new THREE.MeshBasicNodeMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
      });
      const fres = float(1.0).sub(normalView.dot(positionViewDirection).clamp(0, 1)).pow(1.8);
      glowMat.colorNode = color(0xd98a4a);
      glowMat.opacityNode = fres.mul(this.glowPulse).mul(0.85);
      this.glowShell = new THREE.Mesh(new THREE.SphereGeometry(0.16, 32, 24), glowMat);
      this.glowShell.visible = false;
      this.glowShell.renderOrder = 3;
      this.stage.add(this.glowShell);
    } catch {
      this.glowShell = null;
    }

    // ── Polar grid (museum turntable reference) ──
    this.grid = new THREE.PolarGridHelper(1.6, 12, 6, 48, 0xc9b797, 0xdccdb2);
    (this.grid.material as THREE.Material).transparent = true;
    (this.grid.material as THREE.Material).opacity = 0.35;
    this.grid.visible = false;
    this.stage.add(this.grid);

    // ── Controls ──
    const controls = new OrbitControls(this.camera, this.canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.minDistance = 0.018;
    controls.maxDistance = 6.5;
    controls.zoomSpeed = 0.72;
    controls.zoomToCursor = true;
    controls.maxPolarAngle = Math.PI * 0.52;
    controls.minPolarAngle = Math.PI * 0.12;
    controls.autoRotateSpeed = 0.9;
    this.controls = controls;
    controls.addEventListener("start", this.onDirectCameraInput);
    controls.addEventListener("change", this.syncCamStateFromControls);
    this.canvas.addEventListener("pointerdown", this.onDirectCameraInput, { passive: true });
    this.canvas.addEventListener("wheel", this.onDirectCameraInput, { passive: true });

    this.scene.add(this.stage);
    this.resize();
    window.addEventListener("resize", this.resize);
    // the stage can also change height without a window resize (page layout,
    // panel growth), so watch the canvas host directly
    if (typeof ResizeObserver !== "undefined" && this.canvas.parentElement) {
      this.resizeObs = new ResizeObserver(() => this.resize());
      this.resizeObs.observe(this.canvas.parentElement);
    }
    this.ready = true;
    this.loop();
  }

  /** A hand-painted equirectangular gallery dome: warm ivory sky, a soft
   *  key-side glow, and a parchment floor that bounces back into the model.
   *  Cheap to build (64×32 canvas) and gives node materials real IBL. */
  private buildEnvironment(): THREE.Texture | null {
    try {
      const c = document.createElement("canvas");
      c.width = 64;
      c.height = 32;
      const ctx = c.getContext("2d");
      if (!ctx) return null;
      const sky = ctx.createLinearGradient(0, 0, 0, 32);
      sky.addColorStop(0.0, "#9fc3da"); // zenith
      sky.addColorStop(0.42, "#c6dce6");
      sky.addColorStop(0.58, "#e7ece8"); // horizon haze
      sky.addColorStop(1.0, "#8d8b79"); // terrain bounce
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, 64, 32);
      // warm sun patch on the key side
      const sun = ctx.createRadialGradient(46, 5, 0, 46, 5, 22);
      sun.addColorStop(0, "rgba(255,244,214,0.88)");
      sun.addColorStop(1, "rgba(255,244,214,0)");
      ctx.fillStyle = sun;
      ctx.fillRect(0, 0, 64, 32);
      const tex = new THREE.CanvasTexture(c);
      tex.mapping = THREE.EquirectangularReflectionMapping;
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.needsUpdate = true;
      return tex;
    } catch {
      return null;
    }
  }

  /** Warm the rig toward an empire's accent colour — Byzantine gold reads
   *  differently from Inca stone, and the light should say so. */
  setTint(hex: string, dur = 1.1) {
    const tint = new THREE.Color(hex);
    const targets: [THREE.Color | undefined, THREE.Color][] = [
      [this.rimLight?.color, new THREE.Color(0xd2e4ee).lerp(tint, 0.32)],
      [this.keyLight?.color, new THREE.Color(0xfff3dc).lerp(tint, 0.10)],
      [this.bounceLight?.color, new THREE.Color(0xc8c2ae).lerp(tint, 0.18)],
      [this.rimColor.value as THREE.Color, new THREE.Color(0xdcebf2).lerp(tint, 0.28)],
    ];
    targets.forEach(([src, to]) => {
      if (!src) return;
      if (this.reducedMotion || dur <= 0.01) src.copy(to);
      else gsap.to(src, { r: to.r, g: to.g, b: to.b, duration: dur, ease: "power2.inOut" });
    });
  }

  /**
   * Tip a dwelling about the hinge line running along the rear edge of its
   * base — the edge furthest from the camera — so it falls backwards away
   * from the room rather than toward it.
   *
   * Rotating about that edge rather than the model's own origin is what keeps
   * every part of it above the floor for the whole arc: at -90° the building
   * lies flat *behind* the hinge, so it never dips through the ground plane
   * and never throws the shadow acne a floor intersection causes.
   */
  /** Ask for the shadow map to be redrawn over the next few frames. */
  private markShadowDirty(frames = 2) {
    this.shadowDirty = Math.max(this.shadowDirty, frames);
  }

  private resize = () => {
    const parent = this.canvas.parentElement;
    if (!parent || !this.renderer) return;
    const w = parent.clientWidth;
    const h = parent.clientHeight;
    if (w < 2 || h < 2) return;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    // Resolution budget: full DPR on modest canvases, scaled back on large
    // ones so a retina 2× never asks for more fragments than it can afford.
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const MAX_PIXELS = 12_000_000;
    const wanted = w * h * dpr * dpr;
    const ratio = wanted > MAX_PIXELS ? Math.max(1, dpr * Math.sqrt(MAX_PIXELS / wanted)) : dpr;
    this.renderer.setPixelRatio(ratio);
    this.renderer.setSize(w, h, false);
    this.markShadowDirty(2);
  };

  private loop = () => {
    if (this.disposed) return;
    requestAnimationFrame(this.loop);
    const dt = this.clock.getDelta();
    this.controls?.update();
    // idle glow pulse — only worth computing while something is highlighted
    if (this.glowShell?.visible) {
      this.glowPulse.value = 0.55 + Math.sin(performance.now() * 0.0024) * 0.25;
    }
    // throttled occlusion refresh
    this.occlusionTimer += dt;
    if (this.occlusionTimer > 0.14) {
      this.occlusionTimer = 0;
      this.refreshOcclusion();
    }
    this.frameCbs.forEach((cb) => cb());
    if (this.shadowDirty > 0) {
      this.shadowDirty--;
      if (this.keyLight) this.keyLight.shadow.needsUpdate = true;
    }
    this.renderer.render(this.scene, this.camera);
  };

  /* ── model loading & normalization ─────────────────────────────── */
  load(empire: Empire): Promise<LoadedModel> {
    const cached = this.cache.get(empire.id);
    if (cached) return cached;
    const p = new Promise<LoadedModel>((resolve, reject) => {
      this.loader.load(
        empire.modelPath,
        (gltf) => {
          try {
            const model = this.normalize(gltf.scene, empire);
            // resolve the pins here, while nothing is animating: the height
            // field costs several hundred raycasts and would otherwise hitch
            // the very first frames of the swap
            this.snapAnchors(model, empire);
            // and warm the GPU before the dwelling is ever shown — compiling
            // its pipelines and uploading its textures is what made the first
            // frame of a cold swap drop
            this.warm(model).then(() => resolve(model));
          } catch (e) {
            reject(e);
          }
        },
        undefined,
        reject,
      );
    });
    this.cache.set(empire.id, p);
    return p;
  }

  /** Compile a model's shaders and upload its textures while it is still
   *  off-stage, so its first visible frame costs nothing extra. */
  private async warm(model: LoadedModel) {
    if (!this.renderer) return;
    try {
      // Compile against the live scene for lighting context, but WITHOUT
      // putting the model in it: this await spans many frames, and a model
      // sitting in the scene graph across it would be drawn on top of the
      // dwelling currently on stage — which is what flashed on hover.
      await this.renderer.compileAsync(model.group, this.camera, this.scene);

      // The shadow-depth pipeline needs a real render with the model casting.
      // Everything from here to the removal is synchronous — no await — so no
      // visible frame can ever catch the model in the scene.
      this.warmTarget ??= new THREE.RenderTarget(16, 16);
      model.group.position.set(0, 0, 0);
      this.renderer.setRenderTarget(this.warmTarget);
      this.scene.add(model.group);
      if (this.keyLight) this.keyLight.shadow.needsUpdate = true;
      this.renderer.render(this.scene, this.camera);
      this.scene.remove(model.group);
      // and redraw the shadow map for the real scene, so the warm pass leaves
      // no trace of itself for the next on-screen frame to pick up
      if (this.keyLight) this.keyLight.shadow.needsUpdate = true;
      this.renderer.render(this.scene, this.camera);
    } catch {
      /* warming is an optimisation; a failure just means the first frame pays */
    } finally {
      this.renderer?.setRenderTarget(null);
      this.scene.remove(model.group);
      model.group.position.set(0, 0, 0);
      this.markShadowDirty(2);
    }
  }

  preload(empire: Empire) {
    if (!this.cache.has(empire.id)) this.load(empire).catch(() => undefined);
  }

  private normalize(sceneObj: THREE.Group, empire: Empire): LoadedModel {
    const group = new THREE.Group();
    const inner = sceneObj;
    group.add(inner);

    const box = new THREE.Box3().setFromObject(inner);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());

    const maxXZ = Math.max(size.x, size.z) || 1;
    const s = TARGET_SIZE / maxXZ;
    inner.scale.setScalar(s);
    // recenter: footprint center to origin, base to y=0
    inner.position.set(-center.x * s, -box.min.y * s, -center.z * s);

    const meshes: THREE.Mesh[] = [];
    inner.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) {
        const m = o as THREE.Mesh;
        m.castShadow = true;
        m.receiveShadow = true;
        const geo = m.geometry as THREE.BufferGeometry;
        if (!(geo as any).boundsTree) {
          // indirect keeps the index buffer as authored instead of reordering
          // it, and fatter leaves mean far less tree to build — this runs on
          // the main thread during load, and our query load is tiny (one snap
          // pass plus four occlusion rays a few times a second)
          (geo as any).computeBoundsTree({ indirect: true, maxLeafTris: 24 });
        }
        this.applyRim(m);
        meshes.push(m);
      }
    });

    const nsize = size.clone().multiplyScalar(s);
    return {
      group,
      meshes,
      size: nsize,
      empireId: empire.id,
      normalizationScale: s,
      normalizationOffset: inner.position.clone(),
    };
  }

  private tuneTexture(texture: THREE.Texture | null) {
    if (!texture) return;
    texture.anisotropy = this.maxTextureAnisotropy;
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.generateMipmaps = true;
    texture.needsUpdate = true;
  }

  /** TSL rim-light: a soft warm fresnel edge so the architecture reads
   *  against the parchment backdrop. Falls back silently to the
   *  original material if node patching fails. */
  private applyRim(mesh: THREE.Mesh) {
    try {
      const src = mesh.material as THREE.MeshStandardMaterial;
      this.tuneTexture(src.map ?? null);
      this.tuneTexture(src.normalMap ?? null);
      this.tuneTexture((src as any).roughnessMap ?? null);
      this.tuneTexture((src as any).metalnessMap ?? null);
      this.tuneTexture((src as any).aoMap ?? null);
      const nm = new THREE.MeshStandardNodeMaterial();
      nm.color = src.color ? src.color.clone() : new THREE.Color(0xffffff);
      nm.map = src.map ?? null;
      nm.normalMap = src.normalMap ?? null;
      nm.roughnessMap = (src as any).roughnessMap ?? null;
      nm.metalnessMap = (src as any).metalnessMap ?? null;
      nm.aoMap = (src as any).aoMap ?? null;
      nm.roughness = Math.min(1, (src.roughness ?? 0.9) * 1.02);
      nm.metalness = Math.min(0.25, src.metalness ?? 0);
      const fres = float(1.0).sub(normalView.dot(positionViewDirection).clamp(0, 1)).pow(2.6);
      nm.emissiveNode = fres.mul(this.rimColor).mul(this.rimIntensity);
      mesh.material = nm;
    } catch {
      /* keep original material */
    }
  }

  /** Present a loaded model (assumes transition choreography is driven by caller). */
  /** Put a model on the turntable. The outgoing one is retired separately,
   *  so both can be on stage together while they pass each other under the
   *  floor. */
  attach(model: LoadedModel) {
    if (!model.group.parent) this.stage.add(model.group);
    // the contact shadow hugs whatever footprint is on the turntable
    if (this.contact) {
      const spread = Math.max(model.size.x, model.size.z) / 2;
      this.contact.scale.setScalar(Math.max(0.4, spread * 0.92));
    }
    this.markShadowDirty(1);
  }

  /** Hand the stage over: `model` becomes the current dwelling. Recently
   *  seen dwellings stay parsed and resident, so switching back to one is
   *  instant instead of a fresh download, re-parse and re-snap. */
  present(model: LoadedModel) {
    const old = this.current;
    if (old && old.empireId !== model.empireId) this.stage.remove(old.group);
    this.clearRouteMesh();
    this.geoHotspotLocal.clear();
    this.current = model;
    this.occlusionCache.clear();
    this.attach(model);
    this.touchResidency(model.empireId);
    this.rebuildRouteOverlay();
  }

  /** Mark an empire as most-recently-used and evict past the residency cap.
   *  Evicted models are queued, never freed mid-animation. */
  private touchResidency(id: string) {
    this.lru = [id, ...this.lru.filter((x) => x !== id)];
    while (this.lru.length > MAX_RESIDENT) {
      const drop = this.lru.pop();
      if (!drop || drop === this.current?.empireId) continue;
      const p = this.cache.get(drop);
      this.cache.delete(drop);
      this.fields.delete(drop);
      p?.then((m) => {
        if (m !== this.current) {
          this.stage.remove(m.group);
          this.retired.push(m);
        }
      }).catch(() => undefined);
    }
  }

  /** Free everything retired by the last swap. Called once the stage is still. */
  private flushRetired() {
    const list = this.retired;
    this.retired = [];
    list.forEach((m) => {
      if (m !== this.current) this.disposeModel(m);
    });
  }

  /**
   * The exhibit exchange. The outgoing dwelling descends straight through the
   * stage floor and the new one rises out of the same spot — no dissolve.
   * Fading the materials meant turning off depth writes, which let you see
   * clean through the building into its own interior and read as a corrupted
   * model; sinking behind an opaque floor keeps the geometry solid the whole
   * way. `onMidpoint` fires at the handover, when the panels should flip.
   */
  /**
   * The exchange, played as a turntable spin. The dwelling on stage spins up
   * about its own axis, and at the point where it is turning fastest — where
   * the eye cannot resolve which building it is looking at — the next one
   * takes over the same rotation and carries it, decelerating, round to rest.
   *
   * Nothing leaves the ground, so there is no floor plane to cut a colonnade
   * or an open courtyard in half, no surface to withdraw, and no moment where
   * the stage is empty. The dwelling casts its shadow throughout, and the
   * shadow turns with it.
   */
  transition(next: LoadedModel, empire: Empire, opts: { instant?: boolean; onMidpoint?: () => void } = {}): Promise<void> {
    const { onMidpoint } = opts;
    const instant = opts.instant || this.reducedMotion;

    // ── interrupt whatever is in flight, wherever it happens to be ──
    this.activeTl?.kill();
    this.activeTl = null;
    this.activeResolve?.();
    this.activeResolve = null;
    if (this.staged && this.staged !== next && this.staged !== this.current) {
      this.stage.remove(this.staged.group);
    }
    this.staged = null;

    const old = this.current !== next ? this.current : null;

    /** where the baton passes, and where the spin comes to rest — a whole
     *  number of turns, so the dwelling lands back on its own bearing */
    const HANDOVER = 210;
    const REST = 720;

    const stand = () => {
      next.group.scale.setScalar(1);
      next.group.rotation.set(0, 0, 0);
      next.group.position.set(0, 0, 0);
    };

    const handover = () => {
      this.present(next);
      onMidpoint?.();
      this.setTint(empire.tint, 1.0);
      this.frameEmpire(empire, !instant);
    };

    if (instant) {
      stand();
      this.contactOpacity.value = 0.24;
      handover();
      return Promise.resolve();
    }

    // one shared state, so the rotation the outgoing dwelling built up is the
    // rotation the incoming one continues — the spin never breaks stride
    const spin = { deg: old ? THREE.MathUtils.radToDeg(old.group.rotation.y) : HANDOVER, hop: 0 };
    const applyTo = (m: LoadedModel) => {
      m.group.rotation.set(0, THREE.MathUtils.degToRad(spin.deg), 0);
      m.group.position.set(0, spin.hop, 0);
      // it lightens on its footing as it comes up to speed
      this.contactOpacity.value = 0.24 * Math.max(0.35, 1 - spin.hop / (m.size.y * 0.09));
    };

    const tl = gsap.timeline();
    this.activeTl = tl;

    // ── winding up ──
    if (old) {
      tl.to(spin, {
        deg: HANDOVER,
        hop: old.size.y * 0.06,
        duration: 0.44,
        ease: "power2.in",
        onUpdate: () => applyTo(old),
      }, 0);
    }

    // ── the baton passes at full speed ──
    const at = old ? 0.44 : 0;
    tl.add(() => {
      stand();
      applyTo(next);
      handover();
    }, at);

    // ── and unwinds to rest on its own bearing ──
    tl.to(spin, {
      deg: REST,
      hop: 0,
      duration: 1.05,
      ease: "power3.out",
      onUpdate: () => applyTo(next),
    }, at);

    // the dwelling is turning, so the shadow keeps pace for the length of it
    tl.eventCallback("onUpdate", () => this.markShadowDirty(1));

    return new Promise<void>((resolve) => {
      this.activeResolve = resolve;
      tl.eventCallback("onComplete", () => {
        this.activeTl = null;
        this.activeResolve = null;
        this.staged = null;
        stand();
        this.contactOpacity.value = 0.24;
        this.flushRetired();
        this.markShadowDirty(2);
        resolve();
      });
    });
  }

  get currentModel() {
    return this.current;
  }

  private disposeModel(m: LoadedModel) {
    m.meshes.forEach((mesh) => {
      (mesh.geometry as any).disposeBoundsTree?.();
      mesh.geometry.dispose();
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      mats.forEach((mm: any) => {
        ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap"].forEach((k) => mm[k]?.dispose?.());
        mm.dispose?.();
      });
    });
  }

  private disposeCached(id: string) {
    const p = this.cache.get(id);
    if (!p) return;
    this.cache.delete(id);
    p.then((m) => {
      if (m !== this.current) this.disposeModel(m);
    }).catch(() => undefined);
  }

  /* ── anchor projection & occlusion ─────────────────────────────── */

  /** Raw anchor position: normalised box space → model-local units. */
  private boxAnchor(anchor: Vec3, model: LoadedModel, out = new THREE.Vector3(), bias = true) {
    const { size } = model;
    out.set((anchor[0] - 0.5) * size.x, anchor[1] * size.y, (anchor[2] - 0.5) * size.z);
    if (!bias) return out;
    // sit the pin *on* the skin: a hair off the surface, pushed away from the
    // model core so it never z-fights, but close enough to read as attached
    const off = out.clone().sub(new THREE.Vector3(0, size.y * 0.45, 0));
    if (off.lengthSq() > 1e-6) out.add(off.normalize().multiplyScalar(0.022));
    return out;
  }

  /**
   * Land on the topmost surface at the anchor's footprint position, dropping
   * in from above the whole model. Starting above rather than at the anchor's
   * own height is what makes this reliable: over open sky it finds the
   * courtyard floor, over built mass it finds the roof, and it can never
   * start underneath the surface it was meant to land on. A few nearby
   * samples cover holes in the geometry — a basin, a light well.
   */
  /**
   * Top-surface height field over the model's footprint, sampled once by
   * dropping rays from above. It is what lets a pin find "the roof" or "the
   * courtyard" on a dwelling whose shape the data knows nothing about.
   */
  private heightField(model: LoadedModel, ray: THREE.Raycaster): HeightField {
    const cached = this.fields.get(model.empireId);
    if (cached) return cached;
    const n = 20;
    const y = new Float32Array(n * n).fill(NaN);
    let min = Infinity;
    let max = -Infinity;
    const top = model.size.y + 0.15;
    const probe = new THREE.Vector3();
    for (let j = 0; j < n; j++) {
      for (let i = 0; i < n; i++) {
        probe.set(((i + 0.5) / n - 0.5) * model.size.x, top, ((j + 0.5) / n - 0.5) * model.size.z);
        ray.set(model.group.localToWorld(probe), DOWN);
        ray.far = model.size.y + 0.6;
        const hit = ray.intersectObjects(model.meshes, false)[0];
        if (!hit) continue;
        const h = model.group.worldToLocal(hit.point.clone()).y;
        y[j * n + i] = h;
        if (h < min) min = h;
        if (h > max) max = h;
      }
    }
    const field: HeightField = { n, y, min, max };
    this.fields.set(model.empireId, field);
    return field;
  }

  /**
   * Choose the cell of the height field that best answers "roof" or "court",
   * breaking ties by nearness to the authored anchor so the data still says
   * *which* roof or *which* corner of the court is meant.
   */
  private pickCell(model: LoadedModel, field: HeightField, anchor: Vec3, kind: "roof" | "court", eye: THREE.Vector3, ray: THREE.Raycaster) {
    const { n, y, min, max } = field;
    const range = Math.max(1e-4, max - min);
    const roof = kind === "roof";
    // a roof must be near the top of the mass; a court near the bottom
    const limit = roof ? max - range * 0.2 : min + range * 0.32;
    const cellAt = (idx: number) =>
      new THREE.Vector3(
        ((idx % n) + 0.5) / n - 0.5,
        0,
        (Math.floor(idx / n) + 0.5) / n - 0.5,
      ).multiply(new THREE.Vector3(model.size.x, 0, model.size.z)).setY(y[idx] + 0.024);

    for (const central of roof ? [false] : [true, false]) {
      const cands: { idx: number; d: number }[] = [];
      for (let j = 0; j < n; j++) {
        for (let i = 0; i < n; i++) {
          const h = y[j * n + i];
          if (Number.isNaN(h)) continue;
          if (roof ? h < limit : h > limit) continue;
          const cx = (i + 0.5) / n;
          const cz = (j + 0.5) / n;
          // an enclosed court sits inside the footprint, never on its lip
          if (central && (cx < 0.24 || cx > 0.76 || cz < 0.24 || cz > 0.76)) continue;
          cands.push({ idx: j * n + i, d: (cx - anchor[0]) ** 2 + (cz - anchor[2]) ** 2 });
        }
      }
      if (!cands.length) continue;
      cands.sort((p, q) => p.d - q.d);
      // walk out from the anchor and take the first candidate in clear view,
      // so a pin never lands correctly but out of sight behind a roofline
      for (const c of cands.slice(0, 40)) {
        const local = cellAt(c.idx);
        if (this.isVisibleFrom(eye, model.group.localToWorld(local.clone()), model, ray)) return local;
      }
      return cellAt(cands[0].idx);
    }
    return null;
  }

  /**
   * Come in horizontally from outside and stop on the outer skin. Sampling
   * matters more here: a single ray aimed at an arch or window opening sails
   * straight through the building and lands on a far interior wall, so the
   * bundle keeps whichever hit is nearest the outside.
   */
  private castIn(model: LoadedModel, local: THREE.Vector3, ray: THREE.Raycaster, eye: THREE.Vector3) {
    const outward = local.clone().setY(0);
    if (outward.lengthSq() < 1e-6) outward.set(0, 0, 1);
    outward.normalize();
    const reach = Math.max(model.size.x, model.size.z) + 0.8;
    const side = new THREE.Vector3().crossVectors(outward, UP).normalize();
    const step = Math.max(model.size.x, model.size.z) * 0.05;
    const ring = [[0, 0], [step, 0], [-step, 0], [0, step], [0, -step], [step * 2, 0]];
    let best: THREE.Intersection | undefined;
    let bestSeen = false;
    // every hit, not just the first — the nearest surface is often the top of
    // a low garden wall or podium, and a pin named for a facade belongs on an
    // upright face, so flat-topped hits are skipped
    ray.firstHitOnly = false;
    for (const [du, ds] of ring) {
      const at = local.clone().addScaledVector(UP, du).addScaledVector(side, ds);
      const target = model.group.localToWorld(at.clone());
      const start = model.group.localToWorld(at.addScaledVector(outward, reach));
      ray.set(start, target.sub(start).normalize());
      ray.far = reach * 2.2;
      for (const hit of ray.intersectObjects(model.meshes, false)) {
        if (!hit.face) continue;
        const n = hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
        if (Math.abs(n.y) > 0.6) continue; // a floor or a coping, not a wall
        if (n.dot(ray.ray.direction) > 0) continue; // back face of a far wall
        const seen = this.isVisibleFrom(eye, hit.point, model, ray);
        ray.firstHitOnly = false;
        if (!best || (seen && !bestSeen) || (seen === bestSeen && hit.distance < best.distance)) {
          best = hit;
          bestSeen = seen;
        }
        break;
      }
    }
    ray.firstHitOnly = true;
    return best;
  }

  /**
   * Anchors are authored against the bounding box, so one placed at the top
   * of the box can hang in the air over a lower roofline. Drop each pin onto
   * the first surface below it — within a short search, so anchors that are
   * already on stone (or deliberately inside a courtyard) are left alone.
   */
  /** Where the camera comes to rest for this empire, computed before the
   *  fly-to has run — used to prefer pins the visitor can actually see. */
  private restingCamera(empire: Empire, model: LoadedModel) {
    const h = model.size.y;
    const dist = this.fitDistance(empire, 1.3, model);
    const a = THREE.MathUtils.degToRad(empire.camera.azimuth);
    const e = THREE.MathUtils.degToRad(empire.camera.elevation);
    const r = dist * Math.cos(e);
    return new THREE.Vector3(r * Math.sin(a), empire.camera.targetY * h + 0.05 + dist * Math.sin(e), r * Math.cos(a));
  }

  /** Is this world point in clear view from `from`, or is the building in the way? */
  private isVisibleFrom(from: THREE.Vector3, point: THREE.Vector3, model: LoadedModel, ray: THREE.Raycaster) {
    const dir = point.clone().sub(from);
    const dist = dir.length();
    ray.set(from, dir.normalize());
    ray.far = Math.max(0.01, dist - 0.06);
    ray.firstHitOnly = true;
    return ray.intersectObjects(model.meshes, false).length === 0;
  }

  private snapAnchors(model: LoadedModel, empire: Empire) {
    // Snapping happens at the handover, when the dwelling is still lowered and
    // scaled down mid-dissolve. Every ray here — height field, wall probes,
    // visibility — has to describe where things will *come to rest*, so the
    // group is put in its final pose for the duration.
    const g = model.group;
    const pose = { p: g.position.clone(), s: g.scale.clone(), r: g.rotation.clone() };
    g.position.set(0, 0, 0);
    g.scale.setScalar(1);
    g.rotation.set(0, 0, 0);
    g.updateMatrixWorld(true);

    const ray = new THREE.Raycaster();
    ray.firstHitOnly = true;
    const eye = this.restingCamera(empire, model);
    empire.hotspots.forEach((hs) => {
      const key = `${empire.id}:${hs.anchor.join(",")}`;
      if (this.snapped.has(key)) return;
      const local = this.boxAnchor(hs.anchor, model, new THREE.Vector3(), false);

      if (hs.snap === "roof" || hs.snap === "court") {
        const cell = this.pickCell(model, this.heightField(model, ray), hs.anchor, hs.snap, eye, ray);
        this.snapped.set(key, cell ?? this.boxAnchor(hs.anchor, model));
        return;
      }

      const hit = this.castIn(model, local, ray, eye);
      if (!hit) {
        // nothing to attach to — fall back to the authored position
        this.snapped.set(key, this.boxAnchor(hs.anchor, model));
        return;
      }
      // lift the pin just clear of the wall it landed on
      const normal = hit.face
        ? hit.face.normal.clone().transformDirection(hit.object.matrixWorld)
        : UP.clone();
      const p = hit.point.clone().addScaledVector(normal, 0.024);
      this.snapped.set(key, model.group.worldToLocal(p));
    });

    g.position.copy(pose.p);
    g.scale.copy(pose.s);
    g.rotation.copy(pose.r);
    g.updateMatrixWorld(true);
  }

  anchorToWorld(anchor: Vec3, out = new THREE.Vector3()): THREE.Vector3 {
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

  project(world: THREE.Vector3, w: number, h: number): AnchorProjection {
    const v = this.projScratch.copy(world);
    const distance = v.distanceTo(this.camera.position);
    v.project(this.camera);
    return {
      x: (v.x * 0.5 + 0.5) * w,
      y: (-v.y * 0.5 + 0.5) * h,
      distance,
      behindCamera: v.z > 1,
      occluded: false,
    };
  }

  /** camera→target distance; the reference depth for pin scaling */
  get cameraDistance() {
    return this.camState.dist;
  }

  private refreshOcclusion() {
    this.occlusionCache.clear();
    if (!this.current) return;
    const camPos = this.camera.position;
    this.raycaster.firstHitOnly = true;
    this._pendingOcclusion?.forEach(({ id, world }) => {
      const dir = this.occScratch.copy(world).sub(camPos);
      const dist = dir.length();
      this.raycaster.set(camPos, dir.normalize());
      // pins rest on the mesh skin, so stop just short of the surface —
      // anything the ray still hits is genuinely in front of the pin
      this.raycaster.far = Math.max(0.01, dist - 0.05);
      const hits = this.raycaster.intersectObjects(this.current!.meshes, false);
      this.occlusionCache.set(id, hits.length > 0);
    });
  }

  private _pendingOcclusion: { id: string; world: THREE.Vector3 }[] | null = null;
  queueOcclusion(list: { id: string; world: THREE.Vector3 }[]) {
    this._pendingOcclusion = list;
  }
  isOccluded(id: string) {
    return this.occlusionCache.get(id) ?? false;
  }


  /* ── geospatial route system ──────────────────────────────────── */
  setTerrainGeoReference(reference: TerrainGeoReference) {
    this.terrainGeoRef = reference;
    this.geoHotspotLocal.clear();
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

  /* ── camera system ─────────────────────────────────────────────── */
  private applyCam() {
    if (!this.controls || !this.camera) return;
    const { az, el, dist, tx, ty, tz } = this.camState;
    const a = THREE.MathUtils.degToRad(az);
    const e = THREE.MathUtils.degToRad(el);
    const r = dist * Math.cos(e);
    this.camera.position.set(tx + r * Math.sin(a), ty + dist * Math.sin(e), tz + r * Math.cos(a));
    this.controls.target.set(tx, ty, tz);
    this.controls.update();
  }

  /** OrbitControls owns the camera during direct manipulation. Mirror that
   * pose back into the authored camera state so the next zoom/focus/reset
   * continues from exactly where the visitor left the camera. */
  private syncCamStateFromControls = () => {
    if (!this.controls || !this.camera) return;
    const target = this.controls.target;
    const offset = this.camera.position.clone().sub(target);
    const dist = Math.max(0.0001, offset.length());
    this.camState.tx = target.x;
    this.camState.ty = target.y;
    this.camState.tz = target.z;
    this.camState.dist = dist;
    this.camState.az = THREE.MathUtils.radToDeg(Math.atan2(offset.x, offset.z));
    this.camState.el = THREE.MathUtils.radToDeg(Math.asin(THREE.MathUtils.clamp(offset.y / dist, -1, 1)));
  };

  private killCameraMotion() {
    this.cameraTl?.kill();
    this.cameraTween?.kill();
    this.cameraTl = null;
    this.cameraTween = null;
  }

  /** First direct interaction wins immediately over any authored camera move. */
  private onDirectCameraInput = () => {
    if (this.cameraMode === "intro" || this.cameraMode === "cinematic" || this.cameraMode === "focus") {
      this.stopCinematic();
    }
  };

  getCameraMode(): CameraMode {
    return this.cameraMode;
  }

  stopCinematic() {
    this.cameraInterrupted = true;
    this.killCameraMotion();
    this.cameraMode = "manual";
    if (this.controls) this.controls.autoRotate = this.userAutoRotate;
    this.syncCamStateFromControls();
  }

  /** One authored arrival, then one restrained orbit. It never fights input:
   * pointer/touch/wheel/keyboard interaction hands control to the user at once. */
  playPeakIntro(empire: Empire) {
    if (!this.current || !this.controls) return;

    this.killCameraMotion();
    this.cameraInterrupted = false;
    this.controls.autoRotate = false;

    const h = this.current.size.y;
    const heroDist = THREE.MathUtils.clamp(
      this.fitDistance(empire),
      this.controls.minDistance + 0.02,
      this.controls.maxDistance - 0.02,
    );
    const heroTy = empire.camera.targetY * h + 0.05;
    const hero = {
      az: empire.camera.azimuth,
      el: empire.camera.elevation,
      dist: heroDist,
      tx: 0,
      ty: heroTy,
      tz: 0,
    };

    if (this.reducedMotion) {
      Object.assign(this.camState, hero);
      this.applyCam();
      this.cameraMode = "manual";
      this.controls.autoRotate = this.userAutoRotate;
      return;
    }

    this.cameraMode = "intro";
    Object.assign(this.camState, {
      az: hero.az - 28,
      el: THREE.MathUtils.clamp(hero.el - 10, 14, 58),
      dist: Math.min(this.controls.maxDistance - 0.02, Math.max(hero.dist * 1.55, hero.dist + 0.75)),
      tx: 0,
      ty: hero.ty - h * 0.08,
      tz: 0,
    });
    this.applyCam();

    this.cameraTl = gsap.timeline({
      onComplete: () => {
        this.cameraTl = null;
        if (!this.cameraInterrupted) this.playCinematicOrbit(empire);
      },
      onInterrupt: () => {
        this.cameraTl = null;
      },
    });
    this.cameraTl.to(this.camState, {
      ...hero,
      duration: 2.45,
      ease: "power3.out",
      onUpdate: () => this.applyCam(),
    });
  }

  playCinematicOrbit(empire: Empire) {
    if (!this.current || !this.controls || this.reducedMotion || this.cameraInterrupted) {
      if (this.controls) this.controls.autoRotate = this.userAutoRotate;
      this.cameraMode = "manual";
      return;
    }

    this.killCameraMotion();
    this.cameraMode = "cinematic";
    this.controls.autoRotate = false;

    const baseAz = empire.camera.azimuth;
    const baseEl = empire.camera.elevation;
    const baseDist = THREE.MathUtils.clamp(
      this.fitDistance(empire),
      this.controls.minDistance + 0.02,
      this.controls.maxDistance - 0.02,
    );

    this.cameraTl = gsap.timeline({
      onComplete: () => {
        this.cameraTl = null;
        if (!this.cameraInterrupted) {
          this.cameraMode = "manual";
          this.controls.autoRotate = this.userAutoRotate;
        }
      },
      onInterrupt: () => {
        this.cameraTl = null;
      },
    });

    this.cameraTl
      .to(this.camState, {
        az: baseAz + 10,
        el: baseEl + 1.5,
        dist: baseDist * 1.02,
        duration: 2.35,
        ease: "sine.inOut",
        onUpdate: () => this.applyCam(),
      })
      .to(this.camState, {
        az: baseAz - 7,
        el: baseEl + 0.5,
        dist: baseDist,
        duration: 2.35,
        ease: "sine.inOut",
        onUpdate: () => this.applyCam(),
      })
      .to(this.camState, {
        az: baseAz,
        el: baseEl,
        dist: baseDist,
        duration: 1.45,
        ease: "power2.out",
        onUpdate: () => this.applyCam(),
      });
  }

  flyTo(az: number, el: number, dist: number, ty: number, dur = 1.4, onDone?: () => void) {
    this.killCameraMotion();
    const target = {
      az,
      el,
      dist,
      tx: 0,
      ty,
      tz: 0,
    };
    if (this.reducedMotion || dur <= 0.01) {
      Object.assign(this.camState, target);
      this.applyCam();
      onDone?.();
      return;
    }
    this.cameraTween = gsap.to(this.camState, {
      ...target,
      duration: dur,
      ease: "power3.inOut",
      onUpdate: () => this.applyCam(),
      onComplete: () => {
        this.cameraTween = null;
        onDone?.();
      },
      onInterrupt: () => {
        this.cameraTween = null;
      },
    });
  }

  /** Distance at which the dwelling sits inside the frame with museum
   *  breathing room on every side, whatever the viewport aspect. Uses the
   *  footprint half-diagonal so the framing survives a full orbit. */
  private fitDistance(empire: Empire, margin = 1.3, model = this.current) {
    if (!model) return 3.6;
    const { size } = model;
    const radius = Math.hypot(size.x, size.z) * 0.5;
    const vFov = THREE.MathUtils.degToRad(this.camera.fov);
    const tan = Math.tan(vFov / 2);
    const aspect = this.camera.aspect || 1;
    const forHeight = size.y * 0.5 / tan;
    const forWidth = radius / (tan * aspect);
    return Math.max(forHeight, forWidth, radius) * margin * empire.camera.dist;
  }

  frameEmpire(empire: Empire, animate = true, onDone?: () => void) {
    if (!this.current) return;
    const h = this.current.size.y;
    this.flyTo(
      empire.camera.azimuth,
      empire.camera.elevation,
      this.fitDistance(empire),
      empire.camera.targetY * h + 0.05,
      animate ? 1.5 : 0,
      onDone,
    );
  }

  focusAnchor(anchor: Vec3, empire: Empire, dur = 1.2) {
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

  resetPeakView(empire: Empire, animate = true) {
    this.stopCinematic();
    this.cameraInterrupted = true;
    this.cameraMode = "manual";
    this.frameEmpire(empire, animate);
  }

  /* ── modes ─────────────────────────────────────────────────────── */
  setPanMode(on: boolean) {
    if (!this.controls) return;
    this.controls.mouseButtons = {
      LEFT: on ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN,
    };
    this.controls.touches = on
      ? { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_PAN }
      : { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
  }

  setAutoRotate(on: boolean) {
    this.userAutoRotate = on;
    if (!this.controls) return;
    if (on && (this.cameraMode === "intro" || this.cameraMode === "cinematic" || this.cameraMode === "focus")) {
      this.stopCinematic();
    }
    this.controls.autoRotate = on;
  }

  setGrid(on: boolean) {
    if (this.grid) this.grid.visible = on;
  }

  /** Anything that changes what casts or receives shadow must say so. */
  private afterMaterialChange() {
    this.markShadowDirty(3);
  }

  setWireframe(on: boolean) {
    if (on && this.current && !this.wireOverlay) {
      const src = this.current.meshes[0];
      if (src) {
        const mat = new THREE.MeshBasicMaterial({ wireframe: true, color: 0x8c452c, transparent: true, opacity: 0.28 });
        this.wireOverlay = new THREE.Mesh(src.geometry, mat);
        this.wireOverlay.position.copy(src.position);
        this.wireOverlay.quaternion.copy(src.quaternion);
        this.wireOverlay.scale.copy(src.scale);
        this.current.group.add(this.wireOverlay);
      }
    }
    this.afterMaterialChange();
    if (this.wireOverlay) {
      this.wireOverlay.visible = on;
      if (!on && this.wireOverlay.parent) {
        this.wireOverlay.parent.remove(this.wireOverlay);
        (this.wireOverlay.material as THREE.Material).dispose();
        this.wireOverlay = null;
      }
    }
  }

  setXray(on: boolean) {
    if (!this.current) return;
    this.current.meshes.forEach((m) => {
      const mat = m.material as any;
      mat.transparent = on;
      mat.opacity = on ? 0.42 : 1;
      mat.depthWrite = !on;
      mat.needsUpdate = true;
    });
    this.afterMaterialChange();
  }

  zoomBy(factor: number) {
    this.stopCinematic();
    const d = THREE.MathUtils.clamp(this.camState.dist * factor, this.controls.minDistance, this.controls.maxDistance);
    this.cameraTween = gsap.to(this.camState, {
      dist: d,
      duration: this.reducedMotion ? 0 : 0.4,
      ease: "power2.out",
      onUpdate: () => this.applyCam(),
      onComplete: () => {
        this.cameraTween = null;
      },
    });
  }

  /** keyboard orbit support */
  nudge(dAz: number, dEl: number) {
    this.stopCinematic();
    this.camState.az += dAz;
    this.camState.el = THREE.MathUtils.clamp(this.camState.el + dEl, 10, 82);
    this.applyCam();
  }

  setHighlight(anchor: Vec3 | null) {
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

  setReducedMotion(v: boolean) {
    this.reducedMotion = v;
    if (v && (this.cameraMode === "intro" || this.cameraMode === "cinematic")) {
      this.stopCinematic();
    }
  }

  onFrame(cb: FrameCallback) {
    this.frameCbs.add(cb);
    return () => this.frameCbs.delete(cb);
  }

  get readyState() {
    return this.ready;
  }

  dispose() {
    this.disposed = true;
    this.clearRouteMesh();
    this.killCameraMotion();
    window.removeEventListener("resize", this.resize);
    this.controls?.removeEventListener("start", this.onDirectCameraInput);
    this.controls?.removeEventListener("change", this.syncCamStateFromControls);
    this.canvas.removeEventListener("pointerdown", this.onDirectCameraInput);
    this.canvas.removeEventListener("wheel", this.onDirectCameraInput);
    this.resizeObs?.disconnect();
    this.flushRetired();
    if (this.current) this.disposeModel(this.current);
    this.cache.forEach((_v, id) => this.disposeCached(id));
    this.envTex?.dispose();
    this.warmTarget?.dispose();
    this.controls?.dispose();
    this.renderer?.dispose();
  }
}
