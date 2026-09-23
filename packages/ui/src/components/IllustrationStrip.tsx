"use client";

import { useEffect, useState } from 'react';

type DayPeriod = 'morning' | 'afternoon' | 'evening';
type ThemeName = 'dark' | 'light' | 'pastel';

function currentPeriod(): DayPeriod {
  const hour = new Date().getHours();
  if (hour >= 6 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 18) return 'afternoon';
  return 'evening';
}

function readTheme(): ThemeName {
  const theme = document.documentElement.dataset.theme;
  return theme === 'light' || theme === 'pastel' ? theme : 'dark';
}

export function IllustrationStrip() {
  const [period, setPeriod] = useState<DayPeriod>('morning');
  const [theme, setTheme] = useState<ThemeName>('dark');

  useEffect(() => {
    setPeriod(currentPeriod());
    setTheme(readTheme());
    const observer = new MutationObserver(() => setTheme(readTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  return (
    <section className="illustration-strip" aria-label={`Ilustracja autorska · ${period} · motyw ${theme}`}>
      <div className="illustration-strip-frame">
        <img className="illustration-strip-art" src={`/illustrations/${theme}/${period}.png`} alt="Akwarelowa ilustracja polskiego krajobrazu, rysowana konturami kredek" />
        <span className="illustration-place-sign"><small>przystanek</small>spin.clinic</span>
        <a className="illustration-support" href="/wsparcie">Wesprzyj</a>
        <p className="illustration-strip-caption">Polska · ilustracja autorska</p>
      </div>
    </section>
  );
}
