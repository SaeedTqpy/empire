import { memo, useRef, useState } from "react";
import type { PeakRoute, RouteMetrics } from "@/types/route";

interface Props {
  route: PeakRoute | null;
  routeName: string;
  metrics: RouteMetrics | null;
  visible: boolean;
  imported: boolean;
  onToggleVisible: () => void;
  onFocus: () => void;
  onResetBuiltIn: () => void;
  onImportGpx: (file: File) => Promise<void>;
}

const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const one = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const RoutePanel = memo(function RoutePanel({
  route,
  routeName,
  metrics,
  visible,
  imported,
  onToggleVisible,
  onFocus,
  onResetBuiltIn,
  onImportGpx,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const distance = route?.referenceMetrics?.distanceKm ?? metrics?.distanceKm;
  const ascent = route?.referenceMetrics?.ascentM ?? metrics?.ascentM;

  const pickFile = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await onImportGpx(file);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not read this GPX file.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <section className="route-panel" aria-label="Mountain route">
      <div className="route-panel__header">
        <div className="min-w-0">
          <div className="route-panel__kicker">3D ROUTE</div>
          <h3 className="route-panel__title">{routeName}</h3>
          <div className="route-panel__source">{imported ? "Local GPX" : route?.sourceLabel ?? "Route data"}</div>
        </div>
        <button className={`route-chip ${visible ? "is-on" : ""}`} onClick={onToggleVisible} aria-pressed={visible}>
          {visible ? "Shown" : "Hidden"}
        </button>
      </div>

      <div className="route-metrics">
        <div>
          <span>Distance</span>
          <strong>{distance === undefined ? "—" : `${one.format(distance)} km`}</strong>
        </div>
        <div>
          <span>Ascent</span>
          <strong>{ascent === undefined ? "—" : `${whole.format(ascent)} m`}</strong>
        </div>
        <div>
          <span>High</span>
          <strong>{metrics ? `${whole.format(metrics.maxElevationM)} m` : "—"}</strong>
        </div>
      </div>

      <div className="route-panel__actions">
        <button onClick={onFocus}>Focus route</button>
        <button onClick={() => inputRef.current?.click()} disabled={busy}>{busy ? "Reading…" : "Import GPX"}</button>
        {imported && <button onClick={onResetBuiltIn}>South route</button>}
      </div>

      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept=".gpx,application/gpx+xml,application/xml,text/xml"
        onChange={(event) => void pickFile(event.target.files?.[0])}
      />

      {error && <p className="route-panel__error">{error}</p>}
      <p className="route-panel__safety">
        {imported ? "GPX is projected locally onto this DEM." : route?.safetyNote}
      </p>
      {!imported && route && <p className="route-panel__credit">{route.attribution}</p>}
    </section>
  );
});
