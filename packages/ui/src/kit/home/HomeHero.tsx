"use client";

/**
 * Pas powitalny: ilustracja autorska (`/illustrations/<motyw>/<pora>.webp`) jako niskie tło, a na niej
 * jedno zdanie o trzech częściach serwisu, linki i „Wesprzyj projekt”. Zastępuje wysoki baner, który
 * spychał wiadomości pod linię przewijania. Pas jest stały — nie da się go ukryć.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "../Button";
import { useQuery } from "@tanstack/react-query";
import { getClinicPage } from "../../lib/clinic";
import { formatDateTimePl } from "../../lib/utils";

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
  // Pora dnia i motyw znamy dopiero w przeglądarce — do tego czasu bez obrazka (inaczej pobieralibyśmy dwa).
  const [period, setPeriod] = useState<DayPeriod | null>(null);
  const [theme, setTheme] = useState<ThemeName | null>(null);

  useEffect(() => {
    setPeriod(currentPeriod());
    setTheme(readTheme());
    // Dawny przycisk „ukryj” zapisywał to na urządzeniu — sprzątamy, pas wraca u wszystkich.
    try { localStorage.removeItem("sc-home-intro"); } catch {}
    const observer = new MutationObserver(() => setTheme(readTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return (
    <section className="sc-home-intro" aria-label="Czym jest spin.clinic">
      {/* eslint-disable-next-line @next/next/no-img-element -- ilustracja z /public, bez optymalizacji (images.unoptimized) */}
      {theme && period ? <img className="sc-home-intro__art" src={`/illustrations/${theme}/${period}.webp`} alt="" decoding="async" /> : null}
      <div className="sc-home-intro__content">
        <p className="sc-home-intro__title">
          Konsylium AI bada przekaz polityków. <span>Ty układasz własne wiadomości.</span>
        </p>
        <p className="sc-home-intro__lead">Konsylium AI to kilka modeli, które osobno analizują ten sam materiał według wspólnych zasad.</p>
        {stats ? <div aria-label="Praca Kliniki">
          <dl className="sc-home-intro__stats">
            {([["Przeczytane wpisy", stats.read.total], ["Wstępnie ocenione wpisy", stats.screened.total], ["Opublikowane diagnozy", stats.diagnosed.total]] as const).map(([label, count]) => <div key={label}><dt>{label}</dt><dd>{count.toLocaleString("pl-PL")}</dd></div>)}
          </dl>
          <p className="sc-t-caption">Od 23 września · aktualizacja {formatDateTimePl(new Date(query.dataUpdatedAt).toISOString())} (pobranie danych)</p>
        </div> : <p role="status">{query.isPending ? "Wczytujemy liczniki…" : "Liczniki są chwilowo niedostępne."}</p>}
        {query.isError ? <p role="alert">{stats ? "Aktualizacja jest chwilowo niedostępna." : "Nie udało się pobrać danych."} <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p> : null}
        <p className="sc-home-intro__links"><Link href="/o-nas#film">Zobacz, jak to działa (70 s)</Link><Link href="/o-nas#konsylium">Jak działa Konsylium AI</Link><Link href="/o-nas/karta-konsylium">Karta Konsylium</Link></p>
      </div>
      <div className="sc-home-intro__actions">
        <Button href="/klinika/diagnozy" variant="primary" size="sm">Przeglądaj diagnozy</Button>
      </div>
    </section>
  );
}
