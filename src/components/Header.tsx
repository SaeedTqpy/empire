import { memo } from "react";
import { CompassIcon, EmpiresIcon, NotesIcon, MenuIcon } from "./icons";

interface HeaderProps {
  onMenuOpen: () => void;
  onNav: (id: string) => void;
  activeNav: string;
}

const NAV = [
  { id: "explore", label: "Explore", icon: CompassIcon },
  { id: "peaks", label: "Peaks", icon: EmpiresIcon },
  { id: "routes", label: "Routes", icon: NotesIcon },
];

export const Header = memo(function Header({ onMenuOpen, onNav, activeNav }: HeaderProps) {
  return (
    <header className="relative z-40 flex h-[68px] flex-none items-center gap-2.5 border-b border-line-warm bg-paper px-3 sm:gap-4 sm:px-5">
      <button
        onClick={onMenuOpen}
        className="flex h-10 w-10 flex-none items-center justify-center rounded-xl border border-line-warm bg-surface text-slateblue transition-colors hover:border-line-strong xl:hidden"
        aria-label="Open peak menu"
        aria-haspopup="dialog"
      >
        <MenuIcon className="h-5 w-5" />
      </button>

      <div className="flex min-w-0 flex-none items-center gap-2.5">
        <span className="flex h-9 w-9 items-center justify-center rounded-full border border-line-warm bg-surface">
          <CompassIcon className="h-5 w-5 text-terracotta" aria-hidden />
        </span>
        <div className="min-w-0 leading-none">
          <div className="font-display truncate text-[1.25rem] font-bold tracking-[0.01em] text-ink sm:text-[1.45rem]">Iran 3D Peaks</div>
          <div className="font-display mt-1 hidden text-[0.82rem] font-medium italic text-terracotta sm:block">Explore Iran's mountains in three dimensions</div>
        </div>
      </div>

      <nav className="ml-6 hidden items-center gap-1 xl:flex" aria-label="Primary">
        {NAV.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activeNav === item.id ? "is-active" : ""}`}
            onClick={() => onNav(item.id)}
            aria-current={activeNav === item.id ? "page" : undefined}
          >
            <item.icon />
            {item.label}
          </button>
        ))}
      </nav>

      <div className="flex-1" />

      <div className="hidden rounded-full border border-line-warm bg-surface px-4 py-2 text-[0.78rem] font-medium text-ink-muted sm:block">
        Damavand foundation · Phase 1
      </div>
    </header>
  );
});
