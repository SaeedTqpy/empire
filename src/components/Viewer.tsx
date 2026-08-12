import { memo, useCallback, useEffect, useRef, useState } from "react";
import type { Empire } from "@/types/empire";
import type { PeakRoute, RouteDocument, RouteMetrics, TerrainManifestDocument } from "@/types/route";
import { EMPIRES } from "@/data";
import { parseGpx } from "@/lib/gpx";
import { ViewerEngine } from "@/three/engine";
import { HotspotLayer } from "./HotspotLayer";
import { RoutePanel } from "./RoutePanel";
import {
  RotateIcon,
  ZoomInIcon,
  ZoomOutIcon,
  PanIcon,
  LayersIcon,
  VaseIcon,
  TimelineIcon,
  ResetIcon,
  BulbIcon,
  CloseIcon,
  GridIcon,
  WireIcon,
  XrayIcon,
  EyeIcon,
  CheckIcon,
} from "./icons";

interface ViewerProps {
  empire: Empire;
  routes: PeakRoute[];
  terrainManifestPath: string;
  onSwap: (e: Empire) => void;
  reducedMotion: boolean;
  animating: boolean;
  focusHotspot: string | null;
  onFocusHandled: () => void;
  onArtifacts: () => void;
  onTimeline: () => void;
  onPrefetchReady?: (prefetch: (e: Empire) => void) => void;
}

type ToolMode = "rotate" | "pan";
type LayerKey = "labels" | "routes" | "grid" | "wire" | "xray";

export const Viewer = memo(function Viewer({
  empire,
  routes,
  terrainManifestPath,
  onSwap,
  reducedMotion,
  animating,
  focusHotspot,
  onFocusHandled,
  onArtifacts,
  onTimeline,
  onPrefetchReady,
}: ViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<ViewerEngine | null>(null);
  const currentEmpireRef = useRef<Empire | null>(null);
  const builtInRouteRef = useRef<RouteDocument | null>(null);
  const [engineReady, setEngineReady] = useState(false);
  const [markersVisible, setMarkersVisible] = useState(false);
  const [loading, setLoading] = useState<{ name: string; pct: number } | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [tool, setTool] = useState<ToolMode>("rotate");
  const [layersOpen, setLayersOpen] = useState(false);
  const layersRef = useRef<HTMLDivElement>(null);
  const [layers, setLayers] = useState({ labels: true, routes: true, grid: false, wire: false, xray: false });
  const [tipVisible, setTipVisible] = useState(true);
  const [routeMetrics, setRouteMetrics] = useState<RouteMetrics | null>(null);
  const [routeName, setRouteName] = useState(routes[0]?.name ?? "Mountain route");
  const [routeImported, setRouteImported] = useState(false);
  const requestRef = useRef(0);
  const loadingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activeHs = empire.hotspots.find((h) => h.id === activeId) ?? null;
  const builtInRoute = routes[0] ?? null;

  /* ── engine lifecycle ── */
  useEffect(() => {
    const engine = new ViewerEngine(canvasRef.current!);
    engineRef.current = engine;
    let cancelled = false;
    engine.init().then(async () => {
      if (cancelled) return;
      engine.setReducedMotion(reducedMotion);
      engine.onLoadProgress = (pct) => {
        setLoading((l) => (l ? { ...l, pct } : null));
      };
      setEngineReady(true);
      onPrefetchReady?.((e) => engine.preload(e));
      await presentEmpire(empire, { initial: true });
    });
    return () => {
      cancelled = true;
      engine.dispose();
      engineRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    engineRef.current?.setReducedMotion(reducedMotion);
  }, [reducedMotion]);

  useEffect(() => {
    engineRef.current?.setAutoRotate(animating);
  }, [animating]);

  useEffect(() => {
    engineRef.current?.setPanMode(tool === "pan");
  }, [tool]);

  /* Route metadata and the terrain georeference are small JSON files. The
     renderer keeps the loaded route as pending data if the GLB is still being
     prepared, then clamps it to the mesh as soon as the model is presented. */
  useEffect(() => {
    const engine = engineRef.current;
    if (!engineReady || !engine || !builtInRoute) return;
    let cancelled = false;

    Promise.all([
      fetch(terrainManifestPath).then((response) => {
        if (!response.ok) throw new Error(`Terrain manifest HTTP ${response.status}`);
        return response.json() as Promise<TerrainManifestDocument>;
      }),
      fetch(builtInRoute.dataPath).then((response) => {
        if (!response.ok) throw new Error(`Route data HTTP ${response.status}`);
        return response.json() as Promise<RouteDocument>;
      }),
    ])
      .then(([terrain, routeDocument]) => {
        if (cancelled) return;
        engine.setTerrainGeoReference({
          centerLat: terrain.center.lat,
          centerLon: terrain.center.lon,
          baseElevationM: terrain.elevation_m.base,
        });
        builtInRouteRef.current = routeDocument;
        const metrics = engine.setGeoRoute(routeDocument.points, builtInRoute.color);
        engine.setRouteVisible(layers.routes);
        if (metrics) setRouteMetrics(metrics);
        setRouteName(builtInRoute.name);
        setRouteImported(false);
      })
      .catch((error) => console.error("route data load failed", error));

    return () => {
      cancelled = true;
    };
  }, [builtInRoute, engineReady, terrainManifestPath]); // eslint-disable-line react-hooks/exhaustive-deps

  /* dismiss the layers menu on an outside click, or on Escape */
  useEffect(() => {
    if (!layersOpen) return;
    const onDown = (e: PointerEvent) => {
      if (!layersRef.current?.contains(e.target as Node)) setLayersOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLayersOpen(false);
    };
    document.addEventListener("pointerdown", onDown, true);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown, true);
      document.removeEventListener("keydown", onKey);
    };
  }, [layersOpen]);

  /* ── peak switching ── */
  const presentEmpire = useCallback(
    async (next: Empire, opts: { initial?: boolean } = {}) => {
      const engine = engineRef.current;
      if (!engine) return;
      if (currentEmpireRef.current?.id === next.id && !opts.initial) return;
      const token = ++requestRef.current;
      currentEmpireRef.current = next;
      setActiveId(null);
      setHoverId(null);
      setMarkersVisible(false);

      if (loadingTimer.current) clearTimeout(loadingTimer.current);
      loadingTimer.current = setTimeout(() => {
        if (token === requestRef.current) setLoading({ name: next.dwelling, pct: 8 });
      }, 400);
      const model = await engine.load(next).catch((e) => {
        console.error("model load failed", e);
        return null;
      });
      if (loadingTimer.current) clearTimeout(loadingTimer.current);
      if (token !== requestRef.current) return;
      setLoading(null);
      if (!model) return;

      await engine.transition(model, next, {
        instant: opts.initial,
        onMidpoint: () => {
          if (token === requestRef.current) onSwap(next);
        },
      });
      if (token !== requestRef.current) return;

      const metrics = engine.refreshRoute();
      if (metrics) setRouteMetrics(metrics);

      if (opts.initial) engine.playPeakIntro(next);
      setMarkersVisible(true);

      const idx = EMPIRES.findIndex((e) => e.id === next.id);
      window.setTimeout(() => {
        if (token !== requestRef.current) return;
        engine.preload(EMPIRES[(idx + 1) % EMPIRES.length]);
        engine.preload(EMPIRES[(idx - 1 + EMPIRES.length) % EMPIRES.length]);
      }, 1200);
    },
    [onSwap],
  );

  useEffect(() => {
    if (engineReady && currentEmpireRef.current?.id !== empire.id) {
      void presentEmpire(empire);
    }
  }, [empire, engineReady, presentEmpire]);

  useEffect(() => {
    if (focusHotspot) {
      setActiveId(focusHotspot);
      onFocusHandled();
    }
  }, [focusHotspot, onFocusHandled]);

  useEffect(() => {
    const engine = engineRef.current;
    if (!engine || !engineReady) return;
    if (activeHs) {
      engine.focusAnchor(activeHs.anchor, empire);
      engine.setHighlight(activeHs.anchor);
    } else {
      engine.setHighlight(null);
    }
  }, [activeId, engineReady]); // eslint-disable-line react-hooks/exhaustive-deps

  const resetView = useCallback(() => {
    setActiveId(null);
    engineRef.current?.resetPeakView(empire, true);
    setTool("rotate");
  }, [empire]);

  const importGpx = useCallback(
    async (file: File) => {
      const engine = engineRef.current;
      if (!engine) throw new Error("3D viewer is not ready yet.");
      const points = parseGpx(await file.text());
      const metrics = engine.setGeoRoute(points, builtInRoute?.color ?? "#ef5b32");
      if (!metrics) throw new Error("This GPX does not intersect enough of the current 30 km terrain.");
      setRouteMetrics(metrics);
      setRouteName(file.name.replace(/\.gpx$/i, "") || "Imported GPX");
      setRouteImported(true);
      setLayers((previous) => ({ ...previous, routes: true }));
      engine.setRouteVisible(true);
    },
    [builtInRoute?.color],
  );

  const restoreBuiltInRoute = useCallback(() => {
    const engine = engineRef.current;
    const document = builtInRouteRef.current;
    if (!engine || !document || !builtInRoute) return;
    const metrics = engine.setGeoRoute(document.points, builtInRoute.color);
    if (metrics) setRouteMetrics(metrics);
    setRouteName(builtInRoute.name);
    setRouteImported(false);
    setLayers((previous) => ({ ...previous, routes: true }));
    engine.setRouteVisible(true);
  }, [builtInRoute]);

  /* layer toggles */
  const toggleLayer = (key: LayerKey) => {
    const next = { ...layers, [key]: !layers[key] };
    setLayers(next);
    const engine = engineRef.current;
    if (!engine) return;
    if (key === "routes") engine.setRouteVisible(next.routes);
    if (key === "grid") engine.setGrid(next.grid);
    if (key === "wire") engine.setWireframe(next.wire);
    if (key === "xray") engine.setXray(next.xray);
  };

  const LAYER_ITEMS: { key: LayerKey; label: string; icon: typeof GridIcon }[] = [
    { key: "labels", label: "Peak markers", icon: EyeIcon },
    { key: "routes", label: "3D route", icon: LayersIcon },
    { key: "grid", label: "Terrain grid", icon: GridIcon },
    { key: "wire", label: "Wireframe", icon: WireIcon },
    { key: "xray", label: "Terrain x-ray", icon: XrayIcon },
  ];

  return (
    <div className="atlas-card relative h-full w-full overflow-hidden" data-panel="viewer">
      <div
        ref={containerRef}
        className="viewer-stage absolute inset-0"
        role="application"
        aria-label={`Interactive 3D viewer. Use arrow keys to rotate the ${empire.dwelling}, plus and minus to zoom.`}
        tabIndex={0}
        onKeyDown={(e) => {
          const eng = engineRef.current;
          if (!eng) return;
          const step = e.shiftKey ? 18 : 8;
          if (e.key === "ArrowLeft") eng.nudge(-step, 0);
          else if (e.key === "ArrowRight") eng.nudge(step, 0);
          else if (e.key === "ArrowUp") eng.nudge(0, step * 0.6);
          else if (e.key === "ArrowDown") eng.nudge(0, -step * 0.6);
          else if (e.key === "+" || e.key === "=") eng.zoomBy(0.85);
          else if (e.key === "-" || e.key === "_") eng.zoomBy(1.18);
          else if (e.key === "Home") resetView();
          else return;
          e.preventDefault();
        }}
      >
        <canvas ref={canvasRef} className="block h-full w-full touch-none" aria-label={`3D model of the ${empire.dwelling}`} />
        {empire.imageryAttribution && (
          <div className="viewer-attribution" aria-label="Satellite imagery attribution">
            {empire.imageryAttribution}
          </div>
        )}
      </div>

      <HotspotLayer
        engine={engineReady ? engineRef.current : null}
        empire={empire}
        containerRef={containerRef}
        activeId={activeId}
        hoverId={hoverId}
        onHover={setHoverId}
        onActivate={setActiveId}
        visible={markersVisible && layers.labels}
      />

      {builtInRoute && (
        <RoutePanel
          route={builtInRoute}
          routeName={routeName}
          metrics={routeMetrics}
          visible={layers.routes}
          imported={routeImported}
          onToggleVisible={() => toggleLayer("routes")}
          onFocus={() => engineRef.current?.focusRoute()}
          onResetBuiltIn={restoreBuiltInRoute}
          onImportGpx={importGpx}
        />
      )}

      <div className="absolute left-2 top-1/2 z-30 -translate-y-1/2 md:left-3" role="toolbar" aria-label="Model tools" aria-orientation="vertical">
        <div className="atlas-card flex w-[46px] flex-col items-center gap-0.5 !rounded-2xl px-1.5 py-2 sm:w-[58px] md:w-[68px] md:px-2 md:py-2.5">
          <button className={`tool-btn ${tool === "rotate" ? "is-on" : ""}`} onClick={() => setTool("rotate")} aria-pressed={tool === "rotate"}>
            <RotateIcon />
            <span>Rotate</span>
          </button>
          <button className={`tool-btn ${tool === "pan" ? "is-on" : ""}`} onClick={() => setTool(tool === "pan" ? "rotate" : "pan")} aria-pressed={tool === "pan"}>
            <PanIcon />
            <span>Pan</span>
          </button>
          <button className="tool-btn" onClick={() => engineRef.current?.zoomBy(0.78)}>
            <ZoomInIcon />
            <span>Zoom in</span>
          </button>
          <button className="tool-btn" onClick={() => engineRef.current?.zoomBy(1.28)}>
            <ZoomOutIcon />
            <span>Zoom out</span>
          </button>
          <div className="relative" ref={layersRef}>
            <button className={`tool-btn ${layersOpen ? "is-on" : ""}`} onClick={() => setLayersOpen((v) => !v)} aria-expanded={layersOpen} aria-haspopup="true">
              <LayersIcon />
              <span>Layers</span>
            </button>
            {layersOpen && (
              <div className="atlas-card absolute left-[70px] top-0 z-40 w-[168px] !rounded-xl p-1.5" role="menu">
                {LAYER_ITEMS.map((it) => (
                  <button
                    key={it.key}
                    role="menuitemcheckbox"
                    aria-checked={layers[it.key]}
                    className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[0.8rem] text-ink-soft transition-colors hover:bg-paper-deep"
                    onClick={() => toggleLayer(it.key)}
                  >
                    <it.icon className="h-4 w-4 text-slateblue" />
                    <span className="flex-1">{it.label}</span>
                    {layers[it.key] && <CheckIcon className="h-3.5 w-3.5 text-terracotta" />}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button className="tool-btn" onClick={onArtifacts}>
            <VaseIcon />
            <span>Artifacts</span>
          </button>
          <button className="tool-btn" onClick={onTimeline}>
            <TimelineIcon />
            <span>Timeline</span>
          </button>
          <div className="my-1 h-px w-9 bg-line-warm" />
          <button className="tool-btn" onClick={resetView}>
            <ResetIcon />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {activeHs && (
        <div
          className="atlas-card absolute bottom-4 left-1/2 z-30 w-[min(430px,calc(100%-140px))] -translate-x-1/2 !rounded-2xl p-4"
          role="dialog"
          aria-label={activeHs.title}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="kicker !text-[0.62rem] !text-terracotta">{activeHs.category.replace("-", " ")}</div>
              <h3 className="font-display mt-0.5 text-[1.25rem] font-bold leading-tight text-ink">{activeHs.title}</h3>
            </div>
            <button className="rounded-md p-1 text-ink-muted transition-colors hover:bg-paper-deep hover:text-ink" onClick={() => setActiveId(null)} aria-label="Close detail">
              <CloseIcon className="h-[18px] w-[18px]" />
            </button>
          </div>
          <p className="font-display mt-2 text-[0.98rem] italic leading-snug text-ink-muted">{activeHs.short}</p>
          <p className="mt-2 text-[0.86rem] leading-relaxed text-ink-soft">{activeHs.detail}</p>
        </div>
      )}

      {tipVisible && !activeHs && (
        <div className="absolute bottom-4 right-4 z-30 hidden w-[210px] rounded-2xl border border-line-strong bg-[#efe4cf] p-3.5 shadow-card md:block">
          <div className="flex items-center justify-between">
            <span className="font-display flex items-center gap-1.5 text-[0.95rem] font-bold text-ink">
              <BulbIcon className="h-4 w-4 text-gold" />
              Tip
            </span>
            <button className="rounded p-0.5 text-ink-muted transition-colors hover:text-ink" onClick={() => setTipVisible(false)} aria-label="Dismiss tip">
              <CloseIcon className="h-3.5 w-3.5" />
            </button>
          </div>
          <p className="font-display mt-1.5 text-[0.88rem] italic leading-snug text-ink-soft">
            The route is clamped to the DEM. Import a GPX to compare your own track in 3D.
          </p>
        </div>
      )}

      {loading && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-paper/85 backdrop-blur-[2px]" role="status" aria-live="polite">
          <div className="flex w-[240px] flex-col items-center text-center">
            <svg viewBox="0 0 120 120" className="loading-compass h-20 w-20 text-terracotta" aria-hidden>
              <g fill="none" stroke="currentColor" strokeWidth="1.4">
                <circle cx="60" cy="60" r="46" opacity="0.4" />
                <circle cx="60" cy="60" r="34" opacity="0.25" />
                <path d="M60 14v10M60 96v10M14 60h10M96 60h10" />
                <path d="M60 24l7 36-7 36-7-36 7-36z" fill="currentColor" stroke="none" opacity="0.8" />
                <path d="M24 60l36-7 36 7-36 7-36-7z" fill="currentColor" stroke="none" opacity="0.3" />
              </g>
            </svg>
            <svg viewBox="0 0 160 40" className="mt-3 w-[150px] text-ink-muted" aria-hidden>
              <path className="loading-line" d="M10 34 L50 34 L60 18 L70 30 L80 10 L92 30 L102 18 L112 34 L150 34" fill="none" stroke="currentColor" strokeWidth="1.4" />
            </svg>
            <h3 className="font-display mt-3 text-[1.25rem] font-bold text-ink">Loading {loading.name}</h3>
            <div className="mt-3 h-[3px] w-full overflow-hidden rounded-full bg-line-warm">
              <div className="h-full rounded-full bg-terracotta transition-all duration-300" style={{ width: `${loading.pct}%` }} />
            </div>
            <p className="loading-fact font-display mt-3 text-[0.85rem] italic text-ink-muted">Preparing terrain, imagery and route layers…</p>
          </div>
        </div>
      )}
    </div>
  );
});
