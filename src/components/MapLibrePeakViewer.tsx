import { memo, useCallback, useEffect, useRef, useState } from "react";
import {
  AttributionControl,
  GeoJSONSource,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  Popup,
  ScaleControl,
  TerrainControl,
  type StyleSpecification,
} from "maplibre-gl";
import type { Peak } from "@/types/peak";
import type { GeoRoutePoint, RouteDocument } from "@/types/route";
import { parseGpx } from "@/lib/gpx";

interface LocalMapManifest {
  schema_version: number;
  peak_id: string;
  bounds: [number, number, number, number];
  tile_size: number;
  min_zoom: number;
  max_zoom: number;
  satellite: {
    tile_template: string;
    attribution: string;
    source_native_resolution_m: number;
    format: string;
  };
  terrain: {
    tile_template: string;
    attribution: string;
    source_native_resolution_m: number;
    encoding: "terrarium";
  };
  presentation: {
    terrain_exaggeration: number;
    max_pitch: number;
    default_zoom: number;
    default_pitch: number;
    default_bearing: number;
  };
}

interface MapLibrePeakViewerProps {
  peak: Peak;
  reducedMotion: boolean;
  animating: boolean;
}

const ROUTE_SOURCE_ID = "peak-route";
const ROUTE_SHADOW_LAYER_ID = "peak-route-shadow";
const ROUTE_LAYER_ID = "peak-route-line";

function routeFeature(points: GeoRoutePoint[]) {
  return {
    type: "Feature" as const,
    properties: {},
    geometry: {
      type: "LineString" as const,
      coordinates: points.map((point) => [point.lon, point.lat]),
    },
  };
}

function routeBounds(points: GeoRoutePoint[]) {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const point of points) {
    west = Math.min(west, point.lon);
    south = Math.min(south, point.lat);
    east = Math.max(east, point.lon);
    north = Math.max(north, point.lat);
  }
  if (!Number.isFinite(west)) return null;
  return [
    [west, south],
    [east, north],
  ] as [[number, number], [number, number]];
}

function expandedBounds(bounds: [number, number, number, number]) {
  const [west, south, east, north] = bounds;
  const dx = Math.max(0.08, (east - west) * 0.65);
  const dy = Math.max(0.08, (north - south) * 0.65);
  return [
    [west - dx, south - dy],
    [east + dx, north + dy],
  ] as [[number, number], [number, number]];
}

function buildStyle(manifest: LocalMapManifest): StyleSpecification {
  const terrainSource = {
    type: "raster-dem" as const,
    tiles: [manifest.terrain.tile_template],
    tileSize: manifest.tile_size,
    minzoom: manifest.min_zoom,
    maxzoom: manifest.max_zoom,
    bounds: manifest.bounds,
    encoding: manifest.terrain.encoding,
    attribution: manifest.terrain.attribution,
  };

  return {
    version: 8,
    sources: {
      satellite: {
        type: "raster",
        tiles: [manifest.satellite.tile_template],
        tileSize: manifest.tile_size,
        minzoom: manifest.min_zoom,
        maxzoom: manifest.max_zoom,
        bounds: manifest.bounds,
        attribution: manifest.satellite.attribution,
      },
      "terrain-dem": terrainSource,
      "hillshade-dem": { ...terrainSource },
    },
    layers: [
      {
        id: "background",
        type: "background",
        paint: { "background-color": "#b8c3c7" },
      },
      {
        id: "satellite",
        type: "raster",
        source: "satellite",
        paint: {
          "raster-resampling": "linear",
          "raster-saturation": 0.06,
          "raster-contrast": 0.06,
          "raster-brightness-min": 0.015,
          "raster-brightness-max": 0.99,
        },
      },
      {
        id: "terrain-hillshade",
        type: "hillshade",
        source: "hillshade-dem",
        paint: {
          "hillshade-exaggeration": 0.28,
          "hillshade-illumination-direction": 315,
          "hillshade-shadow-color": "rgba(18, 22, 24, 0.48)",
          "hillshade-highlight-color": "rgba(255, 251, 239, 0.34)",
          "hillshade-accent-color": "rgba(68, 76, 78, 0.30)",
        },
      },
    ],
    terrain: {
      source: "terrain-dem",
      exaggeration: manifest.presentation.terrain_exaggeration,
    },
  };
}

function makePopup(peak: Peak, hotspotIndex: number) {
  const hotspot = peak.hotspots[hotspotIndex];
  const root = document.createElement("div");
  root.className = "maplibre-popup-content";

  const kicker = document.createElement("div");
  kicker.className = "maplibre-popup-kicker";
  kicker.textContent = hotspot.category.replace("-", " ");

  const title = document.createElement("strong");
  title.textContent = hotspot.title;

  const text = document.createElement("p");
  text.textContent = hotspot.short;

  root.append(kicker, title, text);
  if (hotspot.elevationM) {
    const elevation = document.createElement("span");
    elevation.className = "maplibre-popup-elevation";
    elevation.textContent = `${hotspot.elevationM.toLocaleString()} m reference elevation`;
    root.append(elevation);
  }
  return root;
}

export const MapLibrePeakViewer = memo(function MapLibrePeakViewer({
  peak,
  reducedMotion,
  animating,
}: MapLibrePeakViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const builtInRouteRef = useRef<GeoRoutePoint[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const interactionPauseUntilRef = useRef(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [errorText, setErrorText] = useState("");
  const [routeName, setRouteName] = useState(peak.routes[0]?.name ?? "Mountain route");
  const [manifest, setManifest] = useState<LocalMapManifest | null>(null);

  const setRoute = useCallback((points: GeoRoutePoint[]) => {
    const map = mapRef.current;
    if (!map || !map.getSource(ROUTE_SOURCE_ID)) return;
    (map.getSource(ROUTE_SOURCE_ID) as GeoJSONSource).setData(routeFeature(points));
  }, []);

  const frameRoute = useCallback(() => {
    const map = mapRef.current;
    const points = builtInRouteRef.current;
    if (!map || points.length < 2) return;
    const bounds = routeBounds(points);
    if (!bounds) return;
    map.fitBounds(bounds, {
      padding: { top: 90, right: 90, bottom: 100, left: 90 },
      pitch: 72,
      bearing: peak.camera.azimuth,
      duration: reducedMotion ? 0 : 1100,
    });
  }, [peak.camera.azimuth, reducedMotion]);

  const restoreBuiltInRoute = useCallback(() => {
    if (builtInRouteRef.current.length < 2) return;
    setRoute(builtInRouteRef.current);
    setRouteName(peak.routes[0]?.name ?? "South Route");
  }, [peak.routes, setRoute]);

  const importGpx = useCallback(
    async (file: File) => {
      try {
        const points = parseGpx(await file.text());
        setRoute(points);
        setRouteName(file.name.replace(/\.gpx$/i, "") || "Imported GPX");
        const bounds = routeBounds(points);
        const map = mapRef.current;
        if (map && bounds) {
          map.fitBounds(bounds, {
            padding: 80,
            pitch: 72,
            duration: reducedMotion ? 0 : 1000,
          });
        }
      } catch (error) {
        setErrorText(error instanceof Error ? error.message : "Unable to read this GPX file.");
      }
    },
    [reducedMotion, setRoute],
  );

  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;
    let map: MapLibreMap | null = null;

    const start = async () => {
      try {
        const manifestResponse = await fetch(`/tiles/maplibre/${peak.id}/manifest.json`, { cache: "no-cache" });
        if (!manifestResponse.ok) throw new Error(`Local terrain manifest HTTP ${manifestResponse.status}`);
        const localManifest = (await manifestResponse.json()) as LocalMapManifest;
        if (cancelled) return;
        setManifest(localManifest);

        let routeDocument: RouteDocument | null = null;
        const route = peak.routes[0];
        if (route) {
          try {
            const routeResponse = await fetch(route.dataPath);
            if (routeResponse.ok) routeDocument = (await routeResponse.json()) as RouteDocument;
          } catch (error) {
            console.warn("MapLibre route load failed", error);
          }
        }

        map = new MapLibreMap({
          container: containerRef.current!,
          style: buildStyle(localManifest),
          center: [peak.coordinates.lon, peak.coordinates.lat],
          zoom: Math.max(localManifest.min_zoom, localManifest.presentation.default_zoom - 1.4),
          pitch: reducedMotion ? localManifest.presentation.default_pitch : 56,
          bearing: reducedMotion ? localManifest.presentation.default_bearing : localManifest.presentation.default_bearing - 24,
          maxPitch: localManifest.presentation.max_pitch,
          maxZoom: 18,
          minZoom: Math.max(7, localManifest.min_zoom - 1),
          maxBounds: expandedBounds(localManifest.bounds),
          renderWorldCopies: false,
          attributionControl: false,
        });
        mapRef.current = map;

        map.addControl(new NavigationControl({ showCompass: true, showZoom: true, visualizePitch: true }), "top-right");
        map.addControl(
          new TerrainControl({
            source: "terrain-dem",
            exaggeration: localManifest.presentation.terrain_exaggeration,
          }),
          "top-right",
        );
        map.addControl(new ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");
        map.addControl(new AttributionControl({ compact: true }), "bottom-right");

        const pauseRotation = () => {
          interactionPauseUntilRef.current = performance.now() + 2800;
        };
        map.on("dragstart", pauseRotation);
        map.on("zoomstart", pauseRotation);
        map.on("rotatestart", pauseRotation);
        map.on("pitchstart", pauseRotation);

        map.on("load", () => {
          if (cancelled || !map) return;

          const routePoints = routeDocument?.points ?? [];
          builtInRouteRef.current = routePoints;
          if (routePoints.length >= 2) {
            map.addSource(ROUTE_SOURCE_ID, {
              type: "geojson",
              data: routeFeature(routePoints),
            });
            map.addLayer({
              id: ROUTE_SHADOW_LAYER_ID,
              type: "line",
              source: ROUTE_SOURCE_ID,
              layout: { "line-cap": "round", "line-join": "round" },
              paint: {
                "line-color": "rgba(18, 20, 20, 0.72)",
                "line-width": ["interpolate", ["linear"], ["zoom"], 10, 3, 16, 9],
                "line-blur": 1.2,
              },
            });
            map.addLayer({
              id: ROUTE_LAYER_ID,
              type: "line",
              source: ROUTE_SOURCE_ID,
              layout: { "line-cap": "round", "line-join": "round" },
              paint: {
                "line-color": peak.routes[0]?.color ?? "#ef5b32",
                "line-width": ["interpolate", ["linear"], ["zoom"], 10, 1.5, 16, 5.5],
              },
            });
          }

          markersRef.current = peak.hotspots.flatMap((hotspot, index) => {
            if (!hotspot.coordinates || !map) return [];
            const button = document.createElement("button");
            button.type = "button";
            button.className = `maplibre-peak-marker maplibre-peak-marker--${hotspot.category}`;
            button.setAttribute("aria-label", hotspot.title);
            button.title = hotspot.title;

            const popup = new Popup({ closeButton: false, offset: 18, maxWidth: "290px" }).setDOMContent(makePopup(peak, index));
            const marker = new Marker({ element: button, anchor: "center" })
              .setLngLat([hotspot.coordinates.lon, hotspot.coordinates.lat])
              .setPopup(popup)
              .addTo(map);

            button.addEventListener("click", () => {
              interactionPauseUntilRef.current = performance.now() + 4000;
              map?.easeTo({
                center: [hotspot.coordinates!.lon, hotspot.coordinates!.lat],
                zoom: hotspot.category === "summit" ? 16.2 : 15.2,
                pitch: 78,
                bearing: peak.camera.azimuth,
                duration: reducedMotion ? 0 : 950,
              });
            });
            return [marker];
          });

          setStatus("ready");
          if (reducedMotion) {
            map.jumpTo({
              center: [peak.coordinates.lon, peak.coordinates.lat],
              zoom: localManifest.presentation.default_zoom,
              pitch: localManifest.presentation.default_pitch,
              bearing: localManifest.presentation.default_bearing,
            });
          } else {
            map.flyTo({
              center: [peak.coordinates.lon, peak.coordinates.lat],
              zoom: localManifest.presentation.default_zoom,
              pitch: localManifest.presentation.default_pitch,
              bearing: localManifest.presentation.default_bearing,
              duration: 2500,
              curve: 1.28,
              essential: true,
            });
          }
        });

        map.on("error", (event) => {
          console.warn("MapLibre terrain event", event.error);
        });
      } catch (error) {
        if (cancelled) return;
        setStatus("error");
        setErrorText(error instanceof Error ? error.message : "Unable to initialize local terrain.");
      }
    };

    void start();
    return () => {
      cancelled = true;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      map?.remove();
      mapRef.current = null;
    };
  }, [peak, reducedMotion]);

  useEffect(() => {
    if (!animating) return;
    let frame = 0;
    let previous = performance.now();
    const animate = (now: number) => {
      const map = mapRef.current;
      if (map && status === "ready" && now >= interactionPauseUntilRef.current && !map.isMoving()) {
        const elapsedSeconds = Math.min(0.05, (now - previous) / 1000);
        map.setBearing(map.getBearing() + elapsedSeconds * 1.8);
      }
      previous = now;
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [animating, status]);

  const resetView = useCallback(() => {
    const map = mapRef.current;
    if (!map || !manifest) return;
    interactionPauseUntilRef.current = performance.now() + 2500;
    map.easeTo({
      center: [peak.coordinates.lon, peak.coordinates.lat],
      zoom: manifest.presentation.default_zoom,
      pitch: manifest.presentation.default_pitch,
      bearing: manifest.presentation.default_bearing,
      duration: reducedMotion ? 0 : 900,
    });
  }, [manifest, peak.coordinates.lat, peak.coordinates.lon, reducedMotion]);

  return (
    <div className="atlas-card maplibre-viewer relative h-full w-full overflow-hidden" data-panel="viewer">
      <div ref={containerRef} className="absolute inset-0" aria-label={`Self-hosted 3D terrain map of ${peak.name}`} />

      <div className="maplibre-quality-badge" aria-live="polite">
        <span className={`maplibre-quality-dot ${status === "error" ? "is-error" : ""}`} />
        {status === "loading" && "Loading local terrain…"}
        {status === "ready" && `Self-hosted · ${manifest?.terrain.source_native_resolution_m ?? 30}m DEM · ${manifest?.satellite.source_native_resolution_m ?? 10}m imagery`}
        {status === "error" && "Local terrain unavailable"}
      </div>

      {status === "ready" && (
        <div className="maplibre-viewer-tools" aria-label="Map controls">
          <button type="button" onClick={resetView}>Reset</button>
          <button type="button" onClick={frameRoute}>Route</button>
          <button type="button" onClick={() => inputRef.current?.click()}>Import GPX</button>
          {routeName !== (peak.routes[0]?.name ?? "Mountain route") && (
            <button type="button" onClick={restoreBuiltInRoute}>South route</button>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".gpx,application/gpx+xml,application/xml,text/xml"
            hidden
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              if (file) void importGpx(file);
              event.currentTarget.value = "";
            }}
          />
          <span className="maplibre-route-name">{routeName}</span>
        </div>
      )}

      {errorText && <div className="maplibre-viewer-error">{errorText}</div>}

      <a className="maplibre-legacy-link" href="?renderer=legacy" title="Compare with the previous Three.js terrain renderer">
        Three.js fallback
      </a>
    </div>
  );
});
