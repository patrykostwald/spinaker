"use client";

/**
 * Pas powitalny: ilustracja autorska (`/illustrations/<motyw>/<pora>.webp`) jako niskie tło, a na niej
 * jedno zdanie o trzech częściach serwisu, linki i „Wesprzyj projekt”. Zastępuje wysoki baner, który
 * spychał wiadomości pod linię przewijania. Pas jest stały - nie da się go ukryć.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "../Button";
import { useQuery } from "@tanstack/react-query";
import { getClinicPage } from "../../lib/clinic";
import { clinicPeriodLabel } from "../../lib/clinicPeriod";

type DayPeriod = "morning" | "afternoon" | "evening";
type ThemeName = "dark" | "light";

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
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, staleTime: 5 * 60_000 });
  const stats = query.data?.stats;
  // Pora dnia i motyw znamy dopiero w przeglądarce - do tego czasu bez obrazka (inaczej pobieralibyśmy dwa).
  const [period, setPeriod] = useState<DayPeriod | null>(null);
  const [theme, setTheme] = useState<ThemeName | null>(null);

  useEffect(() => {
    setPeriod(currentPeriod());
    setTheme(readTheme());
    // Dawny przycisk „ukryj” zapisywał to na urządzeniu - sprzątamy, pas wraca u wszystkich.
    try { localStorage.removeItem("sc-home-intro"); } catch {}
    const observer = new MutationObserver(() => setTheme(readTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  const tiles = stats ? ([["przeczytanych wpisów polityków", stats.read.total], ["wstępnie ocenionych", stats.screened.total], ["opublikowanych diagnoz", stats.diagnosed.total]] as const) : null;
  return (
    <section className="sc-home-intro" data-v="2" aria-label="Czym jest spin.clinic">
      {/* eslint-disable-next-line @next/next/no-img-element -- ilustracja z /public, bez optymalizacji (images.unoptimized) */}
      {theme && period ? <img className="sc-home-intro__art" src={`/illustrations/${theme}/${period}.webp`} alt="" decoding="async" /> : null}
      <div className="sc-hero">
        <div className="sc-hero__copy">
          <h1 className="sc-hero__title">Konsylium AI bada przekaz polityków.</h1>
          <p className="sc-hero__lead">Konsylium AI to kilka modeli różnych firm, które osobno analizują ten sam wpis według wspólnych zasad, takich samych dla rządu i opozycji.</p>
          <div className="sc-hero__actions">
            <Button href="/klinika/diagnozy" variant="primary">Przeglądaj diagnozy</Button>
            <Button href="/konsylium#film" variant="secondary">▶ Jak to działa (70 s)</Button>
            <Link className="sc-hero__link" href="/konsylium/karta">Karta Konsylium →</Link>
          </div>
        </div>
        {tiles ? (
          <div className="sc-hero__stats" aria-label="Praca Kliniki od początku">
            <ul>{tiles.map(([label, count]) => <li key={label}><strong>{count.toLocaleString("pl-PL")}</strong><span>{label}</span></li>)}</ul>
            <p>{clinicPeriodLabel(query.data, query.dataUpdatedAt)}</p>
          </div>
        ) : <p className="sc-hero__stats-empty" role="status">{query.isPending ? "Wczytujemy liczniki…" : "Liczniki są chwilowo niedostępne."}{query.isError ? <> <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></> : null}</p>}
      </div>
    </section>
  );
}
