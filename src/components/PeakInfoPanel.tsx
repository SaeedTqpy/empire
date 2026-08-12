import { memo } from "react";
import type { Peak, PeakFactIcon } from "@/types/peak";
import {
  LaurelIcon,
  PeriodIcon,
  MapPinIcon,
  MaterialsIcon,
  FeatureIcon,
  OccupantsIcon,
  PlayIcon,
} from "./icons";

const FACT_ICONS: Record<PeakFactIcon, typeof PeriodIcon> = {
  elevation: PeriodIcon,
  range: MaterialsIcon,
  location: MapPinIcon,
  type: FeatureIcon,
  status: OccupantsIcon,
};

interface Props {
  peak: Peak;
  flow?: boolean;
  animating: boolean;
  onToggleAnimate: () => void;
}

export const PeakInfoPanel = memo(function PeakInfoPanel({ peak, flow = false, animating, onToggleAnimate }: Props) {
  return (
    <div className={`atlas-card flex w-full flex-col overflow-hidden ${flow ? "" : "h-full"}`} data-panel="info">
      <div className={flow ? "px-5 pb-5 pt-5" : "atlas-scroll min-h-0 flex-1 overflow-y-auto px-5 pb-5 pt-5"}>
        <div className="flex items-start justify-between gap-3">
          <div className="iranian-panel-title-stack">
            <span className="kicker flex items-center gap-2 !text-[0.7rem]" lang="fa" dir="rtl">
              <LaurelIcon className="h-5 w-5 text-gold" aria-hidden />
              قله برگزیده
            </span>
            <span className="iranian-panel-subtitle">Selected Peak</span>
          </div>
          <span className="iranian-local-name max-w-[48%] text-right text-[0.98rem]" lang="fa" dir="rtl">{peak.localName}</span>
        </div>

        <h2 className="font-display mt-3 text-[1.9rem] font-extrabold leading-none text-ink">{peak.name}</h2>
        <p className="mt-2 text-[0.88rem] font-semibold leading-snug text-terracotta">{peak.subtitle}</p>

        <div className={flow ? "sm:flex sm:items-start sm:gap-6" : ""}>
          <div className={`iranian-hero-frame mt-4 overflow-hidden border ${flow ? "sm:w-[44%] sm:flex-none" : ""}`}>
            <img
              src={peak.media.hero}
              alt={`${peak.name} preview`}
              className="block h-auto w-full object-contain"
              loading="lazy"
              draggable={false}
            />
          </div>

          <div className={flow ? "min-w-0 sm:flex-1" : ""}>
            <p className="mt-4 text-[0.94rem] font-[470] leading-[1.7] text-ink-soft">{peak.description}</p>

            <div className="mt-5">
              <h3 className="kicker !text-[0.7rem]" lang="fa" dir="rtl">مشخصات قله</h3>
              <span className="iranian-panel-subtitle ml-[26px] mt-1 block">Peak facts</span>
            </div>
            <dl className="iranian-facts mt-2 divide-y divide-line-warm/70">
              {peak.facts.map((fact) => {
                const Icon = FACT_ICONS[fact.icon];
                return (
                  <div key={fact.label} className="flex items-center justify-between gap-3 py-[9px]">
                    <dt className="flex flex-none items-center gap-2 text-[0.8rem] font-semibold text-ink-soft">
                      <Icon className="h-[17px] w-[17px] flex-none text-terracotta" aria-hidden />
                      {fact.label}
                    </dt>
                    <dd className="min-w-0 max-w-[55%] text-right text-[0.8rem] font-medium leading-snug text-ink">{fact.value}</dd>
                  </div>
                );
              })}
            </dl>
          </div>
        </div>
      </div>

      <div className="flex-none border-t border-line-warm/70 px-4 pb-4 pt-3">
        <button
          className={`btn-primary w-full !py-2.5 ${animating ? "!bg-terracotta-deep" : ""}`}
          onClick={onToggleAnimate}
          aria-pressed={animating}
        >
          <PlayIcon className="h-4 w-4" />
          <span lang="fa" dir="rtl">{animating ? "توقف چرخش سه‌بعدی" : "چرخش سه‌بعدی قله"}</span>
        </button>
        <p className="mt-2 text-center text-[0.68rem] leading-relaxed text-ink-muted">Self-hosted terrain · Sentinel-2 · cinematic camera · geo-aware routes & markers</p>
      </div>
    </div>
  );
});
