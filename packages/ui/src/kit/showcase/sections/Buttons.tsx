"use client";

/**
 * Witryna Button — pełna matryca z docs/UI_KIT_PLAN.md → «Каталог кнопок».
 * Obie wersje kolorystyczne obok siebie, jak w Typography.tsx: [data-sc-theme] + klasa sc-root.
 */

import { useState } from "react";
import { Button, type ButtonSize, type ButtonVariant } from "../../Button";

export const meta = {
  id: "przyciski",
  title: "Przyciski",
  lead: "Jeden komponent Button, różnicowany propsami. Każdy wariant pokazany we wszystkich rozmiarach i stanach, w obu motywach.",
};

// TODO(R1): zamienić na kit/icons po scaleniu — na razie tymczasowy inline SVG własny dla sekcji R2.
function IconHeart() {
  return (
    <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 20.5s-7.5-4.6-9.8-9.2C.6 7.8 2.3 4.5 5.6 4c2-.3 3.7.7 6.4 3 2.7-2.3 4.4-3.3 6.4-3 3.3.5 5 3.8 3.4 7.3C19.5 15.9 12 20.5 12 20.5Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
    </svg>
  );
}
// TODO(R1): zamienić na kit/icons po scaleniu.
function IconClose() {
  return (
    <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}
// TODO(R1): zamienić na kit/icons po scaleniu.
function IconArrowUpRight() {
  return (
    <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M7 17L17 7M9 7h8v8" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const VARIANTS: { key: ButtonVariant; label: string; text: string }[] = [
  { key: "primary", label: "primary", text: "Wesprzyj" },
  { key: "secondary", label: "secondary", text: "Zobacz wszystkie" },
  { key: "quiet", label: "quiet", text: "Ukryj filtr" },
  { key: "ghost", label: "ghost", text: "Zamknij" },
  { key: "danger", label: "danger", text: "Usuń materiał" },
];
const SIZES: ButtonSize[] = ["sm", "md", "lg"];

function ButtonsPanel({ theme }: { theme: "dark" | "light" }) {
  const [pressedFavorite, setPressedFavorite] = useState(false);
  const [pressedFilter, setPressedFilter] = useState(true);

  return (
    <div className="sc-specimen__theme sc-root" data-sc-theme={theme}>
      <p className="sc-t-caption">{theme === "dark" ? "Noc" : "Dzień"}</p>

      <h4 className="sc-t-title-s sc-section__sub">Warianty × rozmiary</h4>
      <div style={{ display: "grid", gap: "var(--sc-s-3)" }}>
        {VARIANTS.map((v) => (
          <div key={v.key} style={{ display: "flex", alignItems: "center", gap: "var(--sc-s-3)", flexWrap: "wrap" }}>
            <code className="sc-t-caption sc-text-3" style={{ width: 76 }}>{v.label}</code>
            {SIZES.map((size) => (
              <Button key={size} variant={v.key} size={size}>{v.text}</Button>
            ))}
          </div>
        ))}
      </div>

      <h4 className="sc-t-title-s sc-section__sub">Stany (na wariant · md)</h4>
      <div style={{ display: "grid", gap: "var(--sc-s-3)" }}>
        {VARIANTS.map((v) => (
          <div key={v.key} style={{ display: "flex", alignItems: "center", gap: "var(--sc-s-3)", flexWrap: "wrap" }}>
            <code className="sc-t-caption sc-text-3" style={{ width: 76 }}>{v.label}</code>
            <Button variant={v.key} size="md">Spoczynek</Button>
            <Button variant={v.key} size="md" data-lit="true">Naświetlony</Button>
            <Button variant={v.key} size="md" disabled>Zablokowany</Button>
            <Button variant={v.key} size="md" loading>Ładowanie</Button>
            <Button variant={v.key} size="md" pressed>Wciśnięty</Button>
          </div>
        ))}
      </div>

      <h4 className="sc-t-title-s sc-section__sub">Ikonowe, pigułka, pełna szerokość, link</h4>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--sc-s-3)", flexWrap: "wrap", marginBottom: "var(--sc-s-4)" }}>
        <Button
          variant="ghost"
          shape="icon"
          size="sm"
          aria-label={pressedFavorite ? "Usuń z ulubionych" : "Dodaj do ulubionych"}
          pressed={pressedFavorite}
          onClick={() => setPressedFavorite((v) => !v)}
          iconStart={<IconHeart />}
        />
        <Button variant="ghost" shape="icon" size="md" aria-label="Zamknij okno" iconStart={<IconClose />} />
        <Button
          variant="quiet"
          shape="pill"
          size="sm"
          pressed={pressedFilter}
          onClick={() => setPressedFilter((v) => !v)}
        >
          Kategoria: Wywiady
        </Button>
        <Button variant="secondary" size="sm" iconStart={<IconArrowUpRight />}>
          Otwórz źródło
        </Button>
      </div>
      <div style={{ maxWidth: 320, marginBottom: "var(--sc-s-4)" }}>
        <Button variant="secondary" size="md" fullWidth>
          Pokaż więcej
        </Button>
      </div>
      <div>
        <Button variant="primary" size="md" href="#przyciski">
          Otwórz jako link
        </Button>
      </div>
    </div>
  );
}

export function Section() {
  return (
    <div className="sc-specimen">
      <ButtonsPanel theme="dark" />
      <ButtonsPanel theme="light" />
    </div>
  );
}
