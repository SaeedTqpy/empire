from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 4 patch point not found: {label}")
    return text.replace(old, new, 1)


engine_path = Path("src/three/engine.ts")
viewer_path = Path("src/components/Viewer.tsx")
panel_path = Path("src/components/PeakInfoPanel.tsx")
type_path = Path("src/types/viewer-camera.ts")

engine = engine_path.read_text()
engine = replace_once(
    engine,
    'import type { Empire, Vec3 } from "@/types/empire";\n',
    'import type { Empire, Vec3 } from "@/types/empire";\nimport type { CameraMode } from "@/types/viewer-camera";\n',
    "CameraMode import",
)

engine = replace_once(
    engine,
    '  private camState = { az: -38, el: 34, dist: 2.6, tx: 0, ty: 0.4, tz: 0 };\n  private reducedMotion = false;\n',
    '''  private camState = { az: -38, el: 34, dist: 2.6, tx: 0, ty: 0.4, tz: 0 };\n  private cameraMode: CameraMode = "loading";\n  private cameraTl: gsap.core.Timeline | null = null;\n  private cameraTween: gsap.core.Tween | null = null;\n  private cameraInterrupted = false;\n  private userAutoRotate = false;\n  private reducedMotion = false;\n''',
    "camera state fields",
)

engine = replace_once(
    engine,
    '    controls.autoRotateSpeed = 0.9;\n    this.controls = controls;\n\n    this.scene.add(this.stage);\n',
    '''    controls.autoRotateSpeed = 0.9;\n    this.controls = controls;\n    controls.addEventListener("start", this.onDirectCameraInput);\n    controls.addEventListener("change", this.syncCamStateFromControls);\n    this.canvas.addEventListener("pointerdown", this.onDirectCameraInput, { passive: true });\n    this.canvas.addEventListener("wheel", this.onDirectCameraInput, { passive: true });\n\n    this.scene.add(this.stage);\n''',
    "camera input listeners",
)

camera_old = '''  private applyCam() {\n    if (!this.controls || !this.camera) return;\n    const { az, el, dist, tx, ty, tz } = this.camState;\n    const a = THREE.MathUtils.degToRad(az);\n    const e = THREE.MathUtils.degToRad(el);\n    const r = dist * Math.cos(e);\n    this.camera.position.set(tx + r * Math.sin(a), ty + dist * Math.sin(e), tz + r * Math.cos(a));\n    this.controls.target.set(tx, ty, tz);\n    this.controls.update();\n  }\n\n  flyTo(az: number, el: number, dist: number, ty: number, dur = 1.4, onDone?: () => void) {\n    const target = {\n      az,\n      el,\n      dist,\n      tx: 0,\n      ty,\n      tz: 0,\n    };\n    if (this.reducedMotion || dur <= 0.01) {\n      Object.assign(this.camState, target);\n      this.applyCam();\n      onDone?.();\n      return;\n    }\n    gsap.to(this.camState, {\n      ...target,\n      duration: dur,\n      ease: "power3.inOut",\n      onUpdate: () => this.applyCam(),\n      onComplete: onDone,\n    });\n  }\n'''

camera_new = '''  private applyCam() {\n    if (!this.controls || !this.camera) return;\n    const { az, el, dist, tx, ty, tz } = this.camState;\n    const a = THREE.MathUtils.degToRad(az);\n    const e = THREE.MathUtils.degToRad(el);\n    const r = dist * Math.cos(e);\n    this.camera.position.set(tx + r * Math.sin(a), ty + dist * Math.sin(e), tz + r * Math.cos(a));\n    this.controls.target.set(tx, ty, tz);\n    this.controls.update();\n  }\n\n  /** OrbitControls owns the camera during direct manipulation. Mirror that\n   * pose back into the authored camera state so the next zoom/focus/reset\n   * continues from exactly where the visitor left the camera. */\n  private syncCamStateFromControls = () => {\n    if (!this.controls || !this.camera) return;\n    const target = this.controls.target;\n    const offset = this.camera.position.clone().sub(target);\n    const dist = Math.max(0.0001, offset.length());\n    this.camState.tx = target.x;\n    this.camState.ty = target.y;\n    this.camState.tz = target.z;\n    this.camState.dist = dist;\n    this.camState.az = THREE.MathUtils.radToDeg(Math.atan2(offset.x, offset.z));\n    this.camState.el = THREE.MathUtils.radToDeg(Math.asin(THREE.MathUtils.clamp(offset.y / dist, -1, 1)));\n  };\n\n  private killCameraMotion() {\n    this.cameraTl?.kill();\n    this.cameraTween?.kill();\n    this.cameraTl = null;\n    this.cameraTween = null;\n  }\n\n  /** First direct interaction wins immediately over any authored camera move. */\n  private onDirectCameraInput = () => {\n    if (this.cameraMode === "intro" || this.cameraMode === "cinematic" || this.cameraMode === "focus") {\n      this.stopCinematic();\n    }\n  };\n\n  getCameraMode(): CameraMode {\n    return this.cameraMode;\n  }\n\n  stopCinematic() {\n    this.cameraInterrupted = true;\n    this.killCameraMotion();\n    this.cameraMode = "manual";\n    if (this.controls) this.controls.autoRotate = this.userAutoRotate;\n    this.syncCamStateFromControls();\n  }\n\n  /** One authored arrival, then one restrained orbit. It never fights input:\n   * pointer/touch/wheel/keyboard interaction hands control to the user at once. */\n  playPeakIntro(empire: Empire) {\n    if (!this.current || !this.controls) return;\n\n    this.killCameraMotion();\n    this.cameraInterrupted = false;\n    this.controls.autoRotate = false;\n\n    const h = this.current.size.y;\n    const heroDist = THREE.MathUtils.clamp(\n      this.fitDistance(empire),\n      this.controls.minDistance + 0.02,\n      this.controls.maxDistance - 0.02,\n    );\n    const heroTy = empire.camera.targetY * h + 0.05;\n    const hero = {\n      az: empire.camera.azimuth,\n      el: empire.camera.elevation,\n      dist: heroDist,\n      tx: 0,\n      ty: heroTy,\n      tz: 0,\n    };\n\n    if (this.reducedMotion) {\n      Object.assign(this.camState, hero);\n      this.applyCam();\n      this.cameraMode = "manual";\n      this.controls.autoRotate = this.userAutoRotate;\n      return;\n    }\n\n    this.cameraMode = "intro";\n    Object.assign(this.camState, {\n      az: hero.az - 28,\n      el: THREE.MathUtils.clamp(hero.el - 10, 14, 58),\n      dist: Math.min(this.controls.maxDistance - 0.02, Math.max(hero.dist * 1.55, hero.dist + 0.75)),\n      tx: 0,\n      ty: hero.ty - h * 0.08,\n      tz: 0,\n    });\n    this.applyCam();\n\n    this.cameraTl = gsap.timeline({\n      onComplete: () => {\n        this.cameraTl = null;\n        if (!this.cameraInterrupted) this.playCinematicOrbit(empire);\n      },\n      onInterrupt: () => {\n        this.cameraTl = null;\n      },\n    });\n    this.cameraTl.to(this.camState, {\n      ...hero,\n      duration: 2.45,\n      ease: "power3.out",\n      onUpdate: () => this.applyCam(),\n    });\n  }\n\n  playCinematicOrbit(empire: Empire) {\n    if (!this.current || !this.controls || this.reducedMotion || this.cameraInterrupted) {\n      if (this.controls) this.controls.autoRotate = this.userAutoRotate;\n      this.cameraMode = "manual";\n      return;\n    }\n\n    this.killCameraMotion();\n    this.cameraMode = "cinematic";\n    this.controls.autoRotate = false;\n\n    const baseAz = empire.camera.azimuth;\n    const baseEl = empire.camera.elevation;\n    const baseDist = THREE.MathUtils.clamp(\n      this.fitDistance(empire),\n      this.controls.minDistance + 0.02,\n      this.controls.maxDistance - 0.02,\n    );\n\n    this.cameraTl = gsap.timeline({\n      onComplete: () => {\n        this.cameraTl = null;\n        if (!this.cameraInterrupted) {\n          this.cameraMode = "manual";\n          this.controls.autoRotate = this.userAutoRotate;\n        }\n      },\n      onInterrupt: () => {\n        this.cameraTl = null;\n      },\n    });\n\n    this.cameraTl\n      .to(this.camState, {\n        az: baseAz + 10,\n        el: baseEl + 1.5,\n        dist: baseDist * 1.02,\n        duration: 2.35,\n        ease: "sine.inOut",\n        onUpdate: () => this.applyCam(),\n      })\n      .to(this.camState, {\n        az: baseAz - 7,\n        el: baseEl + 0.5,\n        dist: baseDist,\n        duration: 2.35,\n        ease: "sine.inOut",\n        onUpdate: () => this.applyCam(),\n      })\n      .to(this.camState, {\n        az: baseAz,\n        el: baseEl,\n        dist: baseDist,\n        duration: 1.45,\n        ease: "power2.out",\n        onUpdate: () => this.applyCam(),\n      });\n  }\n\n  flyTo(az: number, el: number, dist: number, ty: number, dur = 1.4, onDone?: () => void) {\n    this.killCameraMotion();\n    const target = {\n      az,\n      el,\n      dist,\n      tx: 0,\n      ty,\n      tz: 0,\n    };\n    if (this.reducedMotion || dur <= 0.01) {\n      Object.assign(this.camState, target);\n      this.applyCam();\n      onDone?.();\n      return;\n    }\n    this.cameraTween = gsap.to(this.camState, {\n      ...target,\n      duration: dur,\n      ease: "power3.inOut",\n      onUpdate: () => this.applyCam(),\n      onComplete: () => {\n        this.cameraTween = null;\n        onDone?.();\n      },\n      onInterrupt: () => {\n        this.cameraTween = null;\n      },\n    });\n  }\n'''
engine = replace_once(engine, camera_old, camera_new, "camera system")

engine = replace_once(
    engine,
    '''  focusAnchor(anchor: Vec3, empire: Empire, dur = 1.2) {\n    if (!this.current) return;\n    const world = this.anchorToWorld(anchor);\n    const az = this.camState.az;\n    gsap.to(this.camState, {\n      dist: this.fitDistance(empire, 0.62),\n      tx: world.x * 0.72,\n      ty: world.y * 0.72 + 0.06,\n      tz: world.z * 0.72,\n      az,\n      duration: this.reducedMotion ? 0 : dur,\n      ease: "power3.inOut",\n      onUpdate: () => this.applyCam(),\n    });\n  }\n''',
    '''  focusAnchor(anchor: Vec3, empire: Empire, dur = 1.2) {\n    if (!this.current) return;\n    this.killCameraMotion();\n    this.cameraInterrupted = true;\n    this.cameraMode = "focus";\n    if (this.controls) this.controls.autoRotate = false;\n    const world = this.anchorToWorld(anchor);\n    const az = this.camState.az;\n    this.cameraTween = gsap.to(this.camState, {\n      dist: this.fitDistance(empire, 0.62),\n      tx: world.x * 0.72,\n      ty: world.y * 0.72 + 0.06,\n      tz: world.z * 0.72,\n      az,\n      duration: this.reducedMotion ? 0 : dur,\n      ease: "power3.inOut",\n      onUpdate: () => this.applyCam(),\n      onComplete: () => {\n        this.cameraTween = null;\n        this.cameraMode = "manual";\n        if (this.controls) this.controls.autoRotate = this.userAutoRotate;\n      },\n      onInterrupt: () => {\n        this.cameraTween = null;\n      },\n    });\n  }\n\n  resetPeakView(empire: Empire, animate = true) {\n    this.stopCinematic();\n    this.cameraInterrupted = true;\n    this.cameraMode = "manual";\n    this.frameEmpire(empire, animate);\n  }\n''',
    "focus and reset",
)

engine = replace_once(
    engine,
    '''  setAutoRotate(on: boolean) {\n    if (!this.controls) return;\n    this.controls.autoRotate = on;\n  }\n''',
    '''  setAutoRotate(on: boolean) {\n    this.userAutoRotate = on;\n    if (!this.controls) return;\n    if (on && (this.cameraMode === "intro" || this.cameraMode === "cinematic" || this.cameraMode === "focus")) {\n      this.stopCinematic();\n    }\n    this.controls.autoRotate = on;\n  }\n''',
    "manual orbit",
)

engine = replace_once(
    engine,
    '''  zoomBy(factor: number) {\n    const d = THREE.MathUtils.clamp(this.camState.dist * factor, this.controls.minDistance, this.controls.maxDistance);\n    gsap.to(this.camState, { dist: d, duration: 0.4, ease: "power2.out", onUpdate: () => this.applyCam() });\n  }\n\n  /** keyboard orbit support */\n  nudge(dAz: number, dEl: number) {\n    this.camState.az += dAz;\n    this.camState.el = THREE.MathUtils.clamp(this.camState.el + dEl, 10, 82);\n    this.applyCam();\n  }\n''',
    '''  zoomBy(factor: number) {\n    this.stopCinematic();\n    const d = THREE.MathUtils.clamp(this.camState.dist * factor, this.controls.minDistance, this.controls.maxDistance);\n    this.cameraTween = gsap.to(this.camState, {\n      dist: d,\n      duration: this.reducedMotion ? 0 : 0.4,\n      ease: "power2.out",\n      onUpdate: () => this.applyCam(),\n      onComplete: () => {\n        this.cameraTween = null;\n      },\n    });\n  }\n\n  /** keyboard orbit support */\n  nudge(dAz: number, dEl: number) {\n    this.stopCinematic();\n    this.camState.az += dAz;\n    this.camState.el = THREE.MathUtils.clamp(this.camState.el + dEl, 10, 82);\n    this.applyCam();\n  }\n''',
    "manual zoom and keyboard orbit",
)

engine = replace_once(
    engine,
    '''  setReducedMotion(v: boolean) {\n    this.reducedMotion = v;\n  }\n''',
    '''  setReducedMotion(v: boolean) {\n    this.reducedMotion = v;\n    if (v && (this.cameraMode === "intro" || this.cameraMode === "cinematic")) {\n      this.stopCinematic();\n    }\n  }\n''',
    "reduced motion",
)

engine = replace_once(
    engine,
    '''  dispose() {\n    this.disposed = true;\n    window.removeEventListener("resize", this.resize);\n    this.resizeObs?.disconnect();\n''',
    '''  dispose() {\n    this.disposed = true;\n    this.killCameraMotion();\n    window.removeEventListener("resize", this.resize);\n    this.controls?.removeEventListener("start", this.onDirectCameraInput);\n    this.controls?.removeEventListener("change", this.syncCamStateFromControls);\n    this.canvas.removeEventListener("pointerdown", this.onDirectCameraInput);\n    this.canvas.removeEventListener("wheel", this.onDirectCameraInput);\n    this.resizeObs?.disconnect();\n''',
    "camera listener cleanup",
)

engine_path.write_text(engine)

viewer = viewer_path.read_text()
viewer = replace_once(
    viewer,
    '''      if (token !== requestRef.current) return; // superseded mid-animation\n\n      setMarkersVisible(true);\n''',
    '''      if (token !== requestRef.current) return; // superseded mid-animation\n\n      // The first peak arrives through a deliberate flight + short orbit. Any\n      // direct interaction cancels it immediately inside ViewerEngine.\n      if (opts.initial) engine.playPeakIntro(next);\n\n      setMarkersVisible(true);\n''',
    "initial cinematic wiring",
)
viewer = replace_once(
    viewer,
    '    engineRef.current?.frameEmpire(empire, true);\n',
    '    engineRef.current?.resetPeakView(empire, true);\n',
    "reset camera wiring",
)
viewer_path.write_text(viewer)

panel = panel_path.read_text()
panel = panel.replace(
    'Real Damavand DEM and satellite texture arrive in phases 2–3.',
    'Real terrain + Sentinel-2 imagery · cinematic camera enabled.',
)
panel_path.write_text(panel)

type_path.parent.mkdir(parents=True, exist_ok=True)
type_path.write_text('export type CameraMode = "loading" | "intro" | "cinematic" | "manual" | "focus";\n')

print("Phase 4 cinematic camera code is applied")
