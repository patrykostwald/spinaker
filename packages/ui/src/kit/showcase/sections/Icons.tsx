"use client";

import { useState } from "react";
import {
  SearchIcon,
  CloseIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowUpRightIcon,
  CheckIcon,
  MinusIcon,
  HeartIcon,
  ShareIcon,
  GripIcon,
  FilterIcon,
  CalendarIcon,
  ClockIcon,
  GlobeIcon,
  PlayIcon,
  DocumentIcon,
  PlusIcon,
  MenuClose,
  ThemeIcon,
  SpinnerIcon,
  AlertIcon,
  InfoIcon,
  TrashIcon,
  EditIcon,
  EyeIcon,
  type IconSize,
} from "../../icons";

export const meta = {
  id: "ikony",
  title: "Ikony",
  lead: "Siatka 24×24, currentColor, grubość kreski 1.25px (16px) / 1.5px (20–24px). Przycisk niżej odtwarza wszystkie morfingi i najechania naraz, bez użycia myszy.",
};

const SIZES: IconSize[] = [16, 20, 24];
const ICON_IDS = [
  "search",
  "close",
  "chevron-down",
  "chevron-left",
  "chevron-right",
  "arrow-up-right",
  "check",
  "minus",
  "heart",
  "share",
  "grip",
  "filter",
  "calendar",
  "clock",
  "globe",
  "play",
  "document",
  "plus",
  "menu",
  "theme",
  "spinner",
  "alert",
  "info",
  "trash",
  "edit",
  "eye",
] as const;

const LABELS: Record<(typeof ICON_IDS)[number], string> = {
  search: "search",
  close: "close",
  "chevron-down": "chevron-down",
  "chevron-left": "chevron-left",
  "chevron-right": "chevron-right",
  "arrow-up-right": "arrow-up-right",
  check: "check",
  minus: "minus",
  heart: "heart",
  share: "share",
  grip: "grip",
  filter: "filter",
  calendar: "calendar",
  clock: "clock",
  globe: "globe",
  play: "play",
  document: "document",
  plus: "plus",
  menu: "menu ↔ close",
  theme: "sun ↔ moon",
  spinner: "spinner",
  alert: "alert",
  info: "info",
  trash: "trash",
  edit: "edit",
  eye: "eye ↔ eye-off",
};

/** Jedna ikona w danym rozmiarze. `playing`/`drawKey` sterują stanami z tabeli animacji katalogu. */
function IconAtSize({ id, size, playing, drawKey }: { id: (typeof ICON_IDS)[number]; size: IconSize; playing: boolean; drawKey: number }) {
  switch (id) {
    case "search":
      return <SearchIcon size={size} />;
    case "close":
      return <CloseIcon size={size} />;
    case "chevron-down":
      return <ChevronDownIcon size={size} open={playing} />;
    case "chevron-left":
      return <ChevronLeftIcon size={size} />;
    case "chevron-right":
      return <ChevronRightIcon size={size} />;
    case "arrow-up-right":
      return <ArrowUpRightIcon size={size} />;
    case "check":
      return <CheckIcon key={drawKey} size={size} />;
    case "minus":
      return <MinusIcon key={drawKey} size={size} />;
    case "heart":
      return <HeartIcon size={size} filled={playing} />;
    case "share":
      return <ShareIcon size={size} />;
    case "grip":
      return <GripIcon size={size} />;
    case "filter":
      return <FilterIcon size={size} />;
    case "calendar":
      return <CalendarIcon size={size} />;
    case "clock":
      return <ClockIcon size={size} />;
    case "globe":
      return <GlobeIcon size={size} />;
    case "play":
      return <PlayIcon size={size} />;
    case "document":
      return <DocumentIcon size={size} />;
    case "plus":
      return <PlusIcon size={size} active={playing} />;
    case "menu":
      return <MenuClose size={size} open={playing} />;
    case "theme":
      return <ThemeIcon size={size} mode={playing ? "moon" : "sun"} />;
    case "spinner":
      return <SpinnerIcon size={size} />;
    case "alert":
      return <AlertIcon size={size} />;
    case "info":
      return <InfoIcon size={size} />;
    case "trash":
      return <TrashIcon size={size} />;
    case "edit":
      return <EditIcon size={size} />;
    case "eye":
      return <EyeIcon size={size} visible={!playing} />;
    default:
      return null;
  }
}

function ThemePanel({ theme, playing, drawKey }: { theme: "dark" | "light"; playing: boolean; drawKey: number }) {
  return (
    <div className="sc-root sc-icons__theme" data-sc-theme={theme}>
      <p className="sc-t-caption sc-icons__theme-label">{theme === "dark" ? "Noc" : "Dzień"}</p>
      <div className="sc-icons__grid" data-sc-icon-demo={playing || undefined}>
        {ICON_IDS.map((id) => (
          <div key={id} className="sc-icons__cell">
            <div className="sc-icons__sizes">
              {SIZES.map((size) => (
                <span key={size} className="sc-icons__glyph">
                  <IconAtSize id={id} size={size} playing={playing} drawKey={drawKey} />
                </span>
              ))}
            </div>
            <span className="sc-t-meta sc-text-2">{LABELS[id]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Section() {
  const [playing, setPlaying] = useState(false);
  const [drawKey, setDrawKey] = useState(0);

  function toggle() {
    setPlaying((p) => !p);
    setDrawKey((k) => k + 1);
  }

  return (
    <div>
      <div className="sc-icons__toolbar">
        <button type="button" className="sc-icons__play" aria-pressed={playing} onClick={toggle}>
          {playing ? "Zresetuj animacje" : "Odtwórz animacje"}
        </button>
        <p className="sc-t-body-s sc-text-2" style={{ margin: 0 }}>
          Przełącza morfingi (menu↔close, sun↔moon, eye↔eye-off, plus, heart, chevron-down) oraz
          symuluje najechanie na ikony z animacją przy hover (close, chevrony, strzałka, share, play, trash).
        </p>
      </div>

      <ThemePanel theme="dark" playing={playing} drawKey={drawKey} />
      <ThemePanel theme="light" playing={playing} drawKey={drawKey} />
    </div>
  );
}
