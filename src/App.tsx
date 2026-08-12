import { useCallback, useEffect, useMemo, useState } from "react";
import { DEFAULT_PEAK_ID, PEAKS, peakById } from "@/data";
import { Header } from "@/components/Header";
import { PeakLibrary } from "@/components/PeakLibrary";
import { PeakInfoPanel } from "@/components/PeakInfoPanel";
import { Viewer } from "@/components/Viewer";
import { CloseIcon } from "@/components/icons";
import { peakToViewerModel } from "@/lib/peak-viewer-adapter";

const mq = (query: string) => (typeof window !== "undefined" ? window.matchMedia(query).matches : false);

export default function App() {
  const [viewerPeak, setViewerPeak] = useState(() => peakById(DEFAULT_PEAK_ID));
  const [panelPeak, setPanelPeak] = useState(() => peakById(DEFAULT_PEAK_ID));
  const [animating, setAnimating] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeNav, setActiveNav] = useState("explore");
  const [reducedMotion, setReducedMotion] = useState(() => mq("(prefers-reduced-motion: reduce)"));
  const [favorites, setFavorites] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem("iran-peaks-favs") ?? "[]"));
    } catch {
      return new Set();
    }
  });

  const viewerModel = useMemo(() => peakToViewerModel(viewerPeak), [viewerPeak]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReducedMotion(media.matches);
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    document.body.classList.toggle("rm", reducedMotion);
  }, [reducedMotion]);

  useEffect(() => {
    document.title = `${panelPeak.name} — Iran 3D Peaks`;
  }, [panelPeak.name]);

  const selectPeak = useCallback(
    (id: string) => {
      const next = peakById(id);
      if (next.id === viewerPeak.id) return;
      setAnimating(false);
      setViewerPeak(next);
    },
    [viewerPeak.id],
  );

  const toggleFavorite = useCallback((id: string) => {
    setFavorites((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      localStorage.setItem("iran-peaks-favs", JSON.stringify([...next]));
      return next;
    });
  }, []);

  const handleNav = useCallback((id: string) => setActiveNav(id), []);

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <Header onMenuOpen={() => setMenuOpen(true)} onNav={handleNav} activeNav={activeNav} />

      <div className="flex min-h-[70vh] flex-1 gap-4 px-3 pb-4 pt-3 sm:min-h-[600px] sm:px-4 xl:px-5">
        <aside className="hidden w-[268px] flex-none xl:flex">
          <PeakLibrary
            peaks={PEAKS}
            activeId={viewerPeak.id}
            favorites={favorites}
            onSelect={selectPeak}
            onToggleFav={toggleFavorite}
            onViewAll={() => setActiveNav("peaks")}
          />
        </aside>

        <main className="flex min-w-0 flex-1">
          <Viewer
            empire={viewerModel}
            routes={viewerPeak.routes}
            terrainManifestPath={viewerPeak.terrain.manifestPath}
            onSwap={(model) => setPanelPeak(peakById(model.id))}
            reducedMotion={reducedMotion}
            animating={animating}
            focusHotspot={null}
            onFocusHandled={() => undefined}
            onArtifacts={() => undefined}
            onTimeline={() => undefined}
          />
        </main>

        <aside className="hidden w-[330px] flex-none xl:flex">
          <PeakInfoPanel
            peak={panelPeak}
            animating={animating}
            onToggleAnimate={() => setAnimating((value) => !value)}
          />
        </aside>
      </div>

      <section className="px-3 pb-6 sm:px-4 xl:hidden" aria-label="Selected peak">
        <PeakInfoPanel
          peak={panelPeak}
          flow
          animating={animating}
          onToggleAnimate={() => setAnimating((value) => !value)}
        />
      </section>

      {menuOpen && (
        <div className="overlay-backdrop xl:hidden" onClick={() => setMenuOpen(false)}>
          <div
            className="flex h-full w-[min(320px,86vw)] flex-col bg-paper shadow-lift"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Peak menu"
          >
            <div className="flex flex-none items-center justify-between border-b border-line-warm px-4 py-3">
              <div>
                <span className="font-display block text-[1.15rem] font-bold text-ink">Iran 3D Peaks</span>
                <span className="text-[0.72rem] text-ink-muted">Interactive mountain atlas</span>
              </div>
              <button
                onClick={() => setMenuOpen(false)}
                className="rounded-lg border border-line-warm p-1.5 text-ink-muted transition-colors hover:text-ink"
                aria-label="Close menu"
              >
                <CloseIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 px-3 py-3">
              <PeakLibrary
                peaks={PEAKS}
                activeId={viewerPeak.id}
                favorites={favorites}
                onSelect={(id) => {
                  setMenuOpen(false);
                  selectPeak(id);
                }}
                onToggleFav={toggleFavorite}
                onViewAll={() => {
                  setMenuOpen(false);
                  setActiveNav("peaks");
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
