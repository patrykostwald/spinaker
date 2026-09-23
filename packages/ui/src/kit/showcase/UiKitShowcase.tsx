"use client";

import { useEffect, useMemo, useState, type ComponentType } from "react";
import { ForcedReducedMotionContext } from "../motion/useMotionTokens";
import { PortalLayer, PortalProvider } from "../portal";
import { relatedFixtures, resolveFixture } from "./fixtures";
import * as Tokens from "./sections/Tokens";
import * as Typography from "./sections/Typography";
import * as MorphProbe from "./sections/MorphProbe";
import * as Icons from "./sections/Icons";
import * as Controls from "./sections/Controls";
import * as Buttons from "./sections/Buttons";
import * as Dropdowns from "./sections/Dropdowns";
import * as Cards from "./sections/Cards";
import * as Motion from "./sections/Motion";
import * as Navigation from "./sections/Navigation";
import * as Footer from "./sections/Footer";
import * as Mobile from "./sections/Mobile";
import * as Portal from "./sections/Portal";

/**
 * Оболочка витрины. Владелец — R0. Исполнители поставляют файлы `sections/<Имя>.tsx`
 * с `export const meta = { id, title }` и `export function Section()`; интегратор регистрирует их здесь.
 */
type SectionModule = { meta: { id: string; title: string; lead?: string }; Section: ComponentType };

const SECTIONS: SectionModule[] = [Tokens, Typography, Icons, Controls, Buttons, Dropdowns, Cards, Portal, Navigation, Footer, Mobile, Motion, MorphProbe];

type Theme = "dark" | "light";

function readTheme(): Theme {
  return document.documentElement.dataset.theme === "light" || document.documentElement.dataset.theme === "pastel"
    ? "light"
    : "dark";
}

export function UiKitShowcase() {
  const [theme, setTheme] = useState<Theme>("dark");
  const [forceMotion, setForceMotion] = useState(false);
  const [forceTransparency, setForceTransparency] = useState(false);
  const [forceContrast, setForceContrast] = useState(false);

  // Переключатель меняет ТОЛЬКО dataset.theme и восстанавливает исходное значение при уходе.
  // Не пишет в localStorage и не PATCH-ит профиль — иначе просмотр витрины перезапишет настройку владельца.
  useEffect(() => {
    const root = document.documentElement;
    const original = { theme: root.dataset.theme, scheme: root.style.colorScheme };
    setTheme(readTheme());
    return () => {
      if (original.theme) root.dataset.theme = original.theme;
      else delete root.dataset.theme;
      root.style.colorScheme = original.scheme;
      root.classList.remove("sc-theme-transition");
    };
  }, []);

  function chooseTheme(next: Theme) {
    const root = document.documentElement;
    root.classList.add("sc-theme-transition");
    root.dataset.theme = next;
    root.style.colorScheme = next;
    setTheme(next);
    window.setTimeout(() => root.classList.remove("sc-theme-transition"), 300);
  }

  const force = useMemo(
    () =>
      [forceMotion && "reduced-motion", forceTransparency && "reduced-transparency", forceContrast && "contrast"]
        .filter(Boolean)
        .join(" "),
    [forceMotion, forceTransparency, forceContrast],
  );

  return (
    <ForcedReducedMotionContext.Provider value={forceMotion ? true : null}>
      {/* R0 (24.09): ОДИН портал на всю витрину — каждая карточка в любом разделе разворачивается
          в единый предпросмотр и открывается/сворачивается морфингом. Историю ведём в `query`
          (`?podglad=<id>`): у фикстур отрицательные id, `path` тут не имеет смысла. */}
      <PortalProvider historyMode="query">
      <div className="sc-root sc-showcase" data-sc-force={force || undefined}>
        <div className="sc-showcase__banner" role="region" aria-label="Sterowanie witryną">
          <p className="sc-t-meta" style={{ margin: 0 }}>
            <strong>Strona demonstracyjna biblioteki UI.</strong> Wszystkie materiały poniżej są FIKCYJNE i nie są wiadomościami.
          </p>
          <div className="sc-showcase__controls">
            <div className="sc-showcase__seg" role="group" aria-label="Motyw podglądu">
              <button type="button" aria-pressed={theme === "dark"} onClick={() => chooseTheme("dark")}>Noc</button>
              <button type="button" aria-pressed={theme === "light"} onClick={() => chooseTheme("light")}>Dzień</button>
            </div>
            <label className="sc-showcase__check">
              <input type="checkbox" checked={forceMotion} onChange={(e) => setForceMotion(e.target.checked)} />
              Mniej ruchu
            </label>
            <label className="sc-showcase__check">
              <input type="checkbox" checked={forceTransparency} onChange={(e) => setForceTransparency(e.target.checked)} />
              Bez przezroczystości
            </label>
            <label className="sc-showcase__check">
              <input type="checkbox" checked={forceContrast} onChange={(e) => setForceContrast(e.target.checked)} />
              Większy kontrast
            </label>
          </div>
        </div>

        <h1 className="sc-t-display" style={{ margin: "var(--sc-s-8) 0 var(--sc-s-2)" }}>Biblioteka UI spin.clinic</h1>
        <p className="sc-t-body sc-text-2" style={{ margin: 0, maxWidth: "var(--sc-measure)" }}>
          Dwa motywy, Montserrat, ruch na sprężynach. Każda sekcja pokazuje wszystkie stany swojego komponentu.
        </p>

        <nav className="sc-showcase__nav" aria-label="Sekcje">
          {SECTIONS.map(({ meta }) => (
            <a key={meta.id} href={`#${meta.id}`}>{meta.title}</a>
          ))}
        </nav>

        {SECTIONS.map(({ meta, Section }) => (
          <section key={meta.id} id={meta.id} className="sc-section" aria-labelledby={`${meta.id}-title`}>
            <div className="sc-section__head">
              <h2 id={`${meta.id}-title`} className="sc-t-title-l">{meta.title}</h2>
              {meta.lead && <p className="sc-t-body-s">{meta.lead}</p>}
            </div>
            <Section />
          </section>
        ))}
      </div>
      <PortalLayer resolveArticle={resolveFixture} relatedFor={relatedFixtures} />
      </PortalProvider>
    </ForcedReducedMotionContext.Provider>
  );
}
