import { memo, useRef } from "react";
import type { Peak } from "@/types/peak";
import { BookmarkIcon, HeartIcon, ArrowRightIcon } from "./icons";

interface Props {
  peaks: Peak[];
  activeId: string;
  favorites: Set<string>;
  onSelect: (id: string) => void;
  onToggleFav: (id: string) => void;
  onViewAll: () => void;
  onPrefetch?: (id: string) => void;
}

export const PeakLibrary = memo(function PeakLibrary({
  peaks,
  activeId,
  favorites,
  onSelect,
  onToggleFav,
  onViewAll,
  onPrefetch,
}: Props) {
  const listRef = useRef<HTMLDivElement>(null);

  const onKey = (e: React.KeyboardEvent, idx: number) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const next = e.key === "ArrowDown" ? idx + 1 : idx - 1;
    const clamped = (next + peaks.length) % peaks.length;
    const id = peaks[clamped].id;
    onSelect(id);
    listRef.current?.querySelectorAll<HTMLElement>("[data-peak]")[clamped]?.focus();
  };

  return (
    <aside className="atlas-card flex h-full w-full flex-col gap-3 overflow-hidden p-3" aria-label="Peak library" data-panel="library">
      <div className="iranian-panel-heading flex-none px-1 pt-1">
        <div className="iranian-panel-title-stack">
          <span className="kicker !text-[0.72rem]" lang="fa" dir="rtl">دفتر قله‌ها</span>
          <span className="iranian-panel-subtitle">Iran Peak Library</span>
        </div>
        <BookmarkIcon className="mt-1 h-[18px] w-[18px] text-slateblue" aria-hidden />
      </div>

      <div ref={listRef} className="atlas-scroll -mx-1 min-h-0 flex-1 space-y-1.5 overflow-y-auto px-1 pb-2" role="listbox" aria-label="Iranian peaks">
        {peaks.map((peak, i) => {
          const active = peak.id === activeId;
          const fav = favorites.has(peak.id);
          return (
            <button
              key={peak.id}
              data-peak
              role="option"
              aria-selected={active}
              tabIndex={active ? 0 : -1}
              onKeyDown={(ev) => onKey(ev, i)}
              onMouseEnter={() => onPrefetch?.(peak.id)}
              onFocus={() => onPrefetch?.(peak.id)}
              onClick={() => onSelect(peak.id)}
              className={`empire-card ${active ? "is-active" : ""}`}
            >
              <img className="thumb" src={peak.media.thumbnail} alt={`${peak.name} preview`} loading="lazy" draggable={false} />
              <span className="min-w-0 flex-1 leading-tight">
                <span className="font-display block text-[0.98rem] font-bold leading-[1.1] text-ink">{peak.name}</span>
                <span className="iranian-local-name mt-1 block truncate text-[0.76rem]" lang="fa" dir="rtl">{peak.localName}</span>
                <span className="mt-1 block truncate text-[0.7rem] text-ink-muted">{peak.elevationM.toLocaleString()} m · {peak.range}</span>
              </span>
              <span
                role="button"
                tabIndex={-1}
                aria-label={fav ? "Remove favorite" : "Mark favorite"}
                className={`heart flex-none text-terracotta ${fav ? "is-fav" : ""}`}
                onClick={(ev) => {
                  ev.stopPropagation();
                  onToggleFav(peak.id);
                }}
              >
                <HeartIcon className="h-[18px] w-[18px]" filled={fav || active} />
              </span>
            </button>
          );
        })}
      </div>

      <button onClick={onViewAll} className="btn-outline flex-none !justify-between px-4">
        <span className="grid text-left leading-tight">
          <span className="text-[0.82rem] font-bold" lang="fa" dir="rtl">همه قله‌ها</span>
          <span className="text-[0.62rem] text-ink-muted">View all peaks</span>
        </span>
        <ArrowRightIcon className="h-4 w-4" />
      </button>
    </aside>
  );
});
