import { memo, useEffect, useMemo, useRef } from "react";
import * as THREE from "three/webgpu";
import gsap from "gsap";
import type { Empire } from "@/types/empire";
import type { ViewerEngine } from "@/three/engine";

interface Props {
  engine: ViewerEngine | null;
  empire: Empire;
  containerRef: React.RefObject<HTMLDivElement | null>;
  activeId: string | null;
  hoverId: string | null;
  onHover: (id: string | null) => void;
  onActivate: (id: string | null) => void;
  visible: boolean;
  categoryFilter: string | null;
}

const TIP_W = 224;
const TIP_GAP = 18;

/** Pins fixed to the dwelling itself. Each marker tracks its anchor on the
 *  mesh — scaling with depth and dimming when the geometry hides it — and
 *  the annotation stays out of the way until the visitor hovers a pin.
 *
 *  The per-frame path is deliberately allocation-free and layout-read-free:
 *  element handles are captured by ref, the stage size comes from a
 *  ResizeObserver rather than getBoundingClientRect, world vectors are reused,
 *  and a class is only written when it actually changes. */
export const HotspotLayer = memo(function HotspotLayer({
  engine,
  empire,
  containerRef,
  activeId,
  hoverId,
  onHover,
  onActivate,
  visible,
  categoryFilter,
}: Props) {
  const tipRef = useRef<HTMLDivElement>(null);
  const pinRefs = useRef(new Map<string, HTMLElement>());
  const size = useRef({ w: 0, h: 0 });
  const lastState = useRef(new Map<string, number>());

  const visibleHotspots = useMemo(
    () => (categoryFilter ? empire.hotspots.filter((hotspot) => hotspot.category === categoryFilter) : empire.hotspots),
    [empire, categoryFilter],
  );

  /* world positions, allocated once per visible marker and rewritten in place */
  const anchors = useMemo(
    () => visibleHotspots.map((hs) => ({ id: hs.id, world: new THREE.Vector3() })),
    [visibleHotspots],
  );

  /* stage size is read on resize, never per frame */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const read = () => {
      size.current.w = el.clientWidth;
      size.current.h = el.clientHeight;
    };
    read();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, [containerRef, visible]);

  /* per-frame projection of every pin, plus the single hover tooltip */
  useEffect(() => {
    if (!engine || !visible) return;
    engine.queueOcclusion(anchors);
    const off = engine.onFrame(() => {
      const { w, h } = size.current;
      if (!w || !h) return;

      for (let i = 0; i < visibleHotspots.length; i++) {
        const hs = visibleHotspots[i];
        const el = pinRefs.current.get(hs.id);
        if (!el) continue;
        // one world-space resolve per pin per frame, shared with occlusion
        const world = engine.hotspotToWorld(hs, anchors[i].world);
        const p = engine.project(world, w, h);
        const occluded = p.behindCamera || engine.isOccluded(hs.id);
        const isActive = activeId === hs.id;
        const isHover = hoverId === hs.id;

        // perspective: near pins read larger, far pins recede
        const depth = THREE.MathUtils.clamp(engine.cameraDistance / Math.max(0.001, p.distance), 0.72, 1.28);
        el.style.transform = `translate3d(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px, 0) scale(${depth.toFixed(2)})`;

        // classes and z-order only touch the DOM when something changed
        const dim = !!activeId && !isActive;
        const z = isHover || isActive ? 34 : THREE.MathUtils.clamp(Math.round(30 - p.distance * 3), 1, 30);
        const sig = (occluded ? 1 : 0) | (isActive ? 2 : 0) | (isHover ? 4 : 0) | (dim ? 8 : 0) | (z << 4);
        if (lastState.current.get(hs.id) !== sig) {
          lastState.current.set(hs.id, sig);
          el.classList.toggle("is-occluded", occluded);
          el.classList.toggle("is-active", isActive);
          el.classList.toggle("is-hover", isHover);
          el.classList.toggle("is-dim", dim);
          el.style.zIndex = String(z);
        }

        // the tooltip rides the hovered pin, flipping to stay in frame
        if (isHover && !occluded) {
          const tip = tipRef.current;
          if (tip) {
            const th = tip.offsetHeight || 78;
            const flipDown = p.y - TIP_GAP - th < 6;
            const tx = Math.min(Math.max(p.x - TIP_W / 2, 8), Math.max(8, w - TIP_W - 8));
            const ty = flipDown ? p.y + TIP_GAP : p.y - TIP_GAP - th;
            tip.style.transform = `translate3d(${tx.toFixed(1)}px, ${ty.toFixed(1)}px, 0)`;
            tip.style.setProperty("--arrow-x", `${THREE.MathUtils.clamp(p.x - tx, 16, TIP_W - 16).toFixed(0)}px`);
            tip.classList.toggle("is-below", flipDown);
          }
        }
      }
    });
    return () => {
      off();
    };
  }, [engine, visibleHotspots, anchors, activeId, hoverId, visible]);

  /* pins arrive as the dwelling settles */
  useEffect(() => {
    if (!visible) return;
    const rm =
      window.matchMedia("(prefers-reduced-motion: reduce)").matches || document.body.classList.contains("rm");
    if (rm) return;
    const items = [...pinRefs.current.values()];
    if (!items.length) return;
    const tw = gsap.fromTo(
      items,
      { opacity: 0 },
      { opacity: 1, duration: 0.5, stagger: 0.06, ease: "power2.out", delay: 0.3, clearProps: "opacity" },
    );
    return () => {
      tw.kill();
    };
  }, [empire.id, visible]);

  const hovered = visibleHotspots.find((h) => h.id === hoverId) ?? null;

  return (
    /* kept mounted while hidden so the pins fade with the dwelling rather
       than popping out on the first frame of a swap */
    <div
      className={`hs-layer pointer-events-none absolute inset-0 z-20 ${visible ? "" : "is-hidden"}`}
      aria-hidden={!visible}
      aria-label="Mountain markers"
    >
      {visibleHotspots.map((hs) => (
        <button
          key={hs.id}
          className="hs-pin"
          data-hs={hs.id}
          data-category={hs.category}
          ref={(el) => {
            if (el) pinRefs.current.set(hs.id, el);
            else {
              pinRefs.current.delete(hs.id);
              lastState.current.delete(hs.id);
            }
          }}
          aria-label={`${hs.title}: ${hs.short}`}
          aria-pressed={activeId === hs.id}
          onMouseEnter={() => onHover(hs.id)}
          onMouseLeave={() => onHover(null)}
          onFocus={() => onHover(hs.id)}
          onBlur={() => onHover(null)}
          onClick={() => onActivate(activeId === hs.id ? null : hs.id)}
        >
          <span className="pulse" />
          <span className="rim" />
          <span className="core" />
        </button>
      ))}

      <div
        ref={tipRef}
        className={`hs-tip ${hovered ? "is-shown" : ""}`}
        role="tooltip"
        aria-hidden={!hovered}
        style={{ width: TIP_W }}
      >
        {hovered && (
          <>
            <span className="cat">{hovered.category.replace("-", " ")}</span>
            <span className="t">{hovered.title}</span>
            <span className="d">{hovered.short}</span>
            <span className="hint">Click to explore</span>
          </>
        )}
      </div>
    </div>
  );
});
