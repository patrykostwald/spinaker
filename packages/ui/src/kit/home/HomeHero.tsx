"use client";

/**
 * Pas powitalny: ilustracja autorska (`/illustrations/<motyw>/<pora>.png`) jako niskie tło, a na niej
 * jedno zdanie o trzech częściach serwisu, linki i „Wesprzyj nas”. Zastępuje wysoki baner, który
 * spychał wiadomości pod linię przewijania. Czytelnik może pas ukryć — zapamiętujemy to na urządzeniu.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "../Button";
import { CloseIcon } from "../icons";

type DayPeriod = "morning" | "afternoon" | "evening";
type ThemeName = "dark" | "light";
const HIDDEN_KEY = "sc-home-intro";

function currentPeriod(): DayPeriod {
  const hour = new Date().getHours();
  if (hour >= 6 && hour < 12) return "morning";
  if (hour >= 12 && hour < 18) return "afternoon";
  return "evening";
}

function readTheme(): ThemeName {
  const theme = document.documentElement.dataset.theme;
  return theme === "light" || theme === "pastel" ? "light" : "dark";
}

export function HomeHero() {
  const [period, setPeriod] = useState<DayPeriod>("morning");
  const [theme, setTheme] = useState<ThemeName>("dark");
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    setPeriod(currentPeriod());
    setTheme(readTheme());
    try { setHidden(localStorage.getItem(HIDDEN_KEY) === "hidden"); } catch {}
    const observer = new MutationObserver(() => setTheme(readTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  if (hidden) return null;

  function hide() {
    setHidden(true);
    try { localStorage.setItem(HIDDEN_KEY, "hidden"); } catch {}
  }

  return (
    <section className="sc-home-intro" aria-label="Czym jest spin.clinic">
      {/* eslint-disable-next-line @next/next/no-img-element -- ilustracja z /public, bez optymalizacji (images.unoptimized) */}
      <img className="sc-home-intro__art" src={`/illustrations/${theme}/${period}.png`} alt="" />
      <div className="sc-home-intro__content">
        <p className="sc-home-intro__title">
          Wiadomości ze źródłami. Diagnozy spinu polityków. <span>Nitki układane przez czytelników.</span>
        </p>
        <p className="sc-home-intro__links">
          <Link href="/klinika">Klinika spinu →</Link>
          <Link href="/nitki">Nitki →</Link>
          <Link href="/o-nas">Jak to działa</Link>
        </p>
      </div>
      <div className="sc-home-intro__actions">
        <Button href="/wsparcie" variant="primary" size="sm">Wesprzyj nas</Button>
        <Button shape="icon" variant="ghost" size="sm" aria-label="Ukryj pas powitalny" onClick={hide} iconStart={<CloseIcon size={16} />} />
      </div>
    </section>
  );
}
