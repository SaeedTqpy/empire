import { memo } from "react";
import { CompassIcon, LibraryIcon, NotesIcon, MenuIcon } from "./icons";

interface HeaderProps {
  onMenuOpen: () => void;
  onNav: (id: string) => void;
  activeNav: string;
}

const NAV = [
  { id: "explore", label: "Explore", fa: "کاوش", icon: CompassIcon },
  { id: "peaks", label: "Peaks", fa: "قله‌ها", icon: LibraryIcon },
  { id: "routes", label: "Routes", fa: "مسیرها", icon: NotesIcon },
];

function AchaemenidRosette({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <g fill="currentColor" opacity="0.96">
        {Array.from({ length: 12 }, (_, index) => (
          <ellipse
            key={index}
            cx="24"
            cy="11.5"
            rx="3.15"
            ry="8.2"
            transform={`rotate(${index * 30} 24 24)`}
          />
        ))}
      </g>
      <circle cx="24" cy="24" r="5.2" fill="var(--iran-saffron)" />
      <circle cx="24" cy="24" r="2.1" fill="var(--iran-lapis-deep)" />
    </svg>
  );
}

export const Header = memo(function Header({ onMenuOpen, onNav, activeNav }: HeaderProps) {
  return (
    <header className="iranian-header relative z-40 flex flex-none items-center gap-2.5 px-3 py-2 sm:gap-4 sm:px-5">
      <button
        onClick={onMenuOpen}
        className="iranian-icon-button flex h-10 w-10 flex-none items-center justify-center border bg-surface transition-colors xl:hidden"
        aria-label="Open peak menu"
        aria-haspopup="dialog"
      >
        <MenuIcon className="h-5 w-5" />
      </button>

      <div className="flex min-w-0 flex-none items-center gap-3">
        <span className="iranian-brand-mark">
          <AchaemenidRosette />
        </span>
        <div className="min-w-0">
          <div className="iranian-brand-fa truncate" lang="fa" dir="rtl">قله‌های ایران</div>
          <div className="iranian-brand-en truncate">Iran 3D Peaks · Digital Mountain Atlas</div>
        </div>
      </div>

      <nav className="ml-5 hidden items-center gap-1.5 xl:flex" aria-label="Primary">
        {NAV.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activeNav === item.id ? "is-active" : ""}`}
            onClick={() => onNav(item.id)}
            aria-current={activeNav === item.id ? "page" : undefined}
          >
            <item.icon />
            <span className="nav-copy">
              <span lang="fa" dir="rtl">{item.fa}</span>
              <small>{item.label}</small>
            </span>
          </button>
        ))}
      </nav>

      <div className="flex-1" />

      <div className="iranian-status-chip hidden sm:inline-flex">
        <span lang="fa" dir="rtl">دماوند</span>
        <span aria-hidden>·</span>
        <span>Self-hosted terrain</span>
      </div>
    </header>
  );
});
