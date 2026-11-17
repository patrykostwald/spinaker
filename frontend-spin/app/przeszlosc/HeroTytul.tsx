'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import './hero-tytul.css';

/**
 * Tytuł strony głównej przeszłość.today: "Kto, co i kiedy?" (zlecenie właściciela 13.10.2026: tylko te trzy słowa, każde
 * z innym, bardzo gustownym, lekko "hakerskim" gestem; jedna animacja naraz, pętla co 14 s, start po 1,4 s).
 *  - "Kto"   - dekodowanie: litery składają się z losowych znaków (jak odczyt zaszyfrowanego pola), stałe miejsca liter;
 *  - "co"    - zaczernienie: pasek w akcencie przykrywa słowo i odsuwa się (dokument po anonimizacji, odsłonięcie);
 *  - "kiedy" - znacznik czasu w mono (data i sekundy tykają jak w logu) + migający kursor po znaku zapytania.
 * Tekst w DOM jest zwykły ("Kto, co i kiedy?"), ozdoby są aria-hidden; SSR bez efektów (LCP: tytuł widoczny od razu);
 * prefers-reduced-motion = brak efektów. Tylko transform / opacity / clip-path, bez zmiany rozmiaru nagłówka.
 */
const GLYPHS = '01#%&@$*/\<>?!+=';
const LOOP = 14000;
const START = 1400;
const STEP = 55;

function pad(n: number) { return String(n).padStart(2, '0'); }
function stamp(d: Date) {
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} · ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function HeroTytul() {
  const root = useRef<HTMLSpanElement>(null);
  const [fx, setFx] = useState<'' | 'kto' | 'co' | 'kiedy'>('');
  const [kto, setKto] = useState<string[] | null>(null);
  const [time, setTime] = useState('');
  const [widths, setWidths] = useState<number[] | null>(null);

  // stałe szerokości liter słowa "Kto" (losowy znak nie może przesunąć układu)
  useLayoutEffect(() => {
    const el = root.current?.querySelector('[data-w="kto"]');
    if (!el) return;
    setWidths(Array.from(el.querySelectorAll<HTMLElement>('[data-l]')).map(n => n.getBoundingClientRect().width));
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const intervals: ReturnType<typeof setInterval>[] = [];
    const at = (ms: number, fn: () => void) => { timers.push(setTimeout(fn, ms)); };
    const word = [...'Kto'];

    const cycle = () => {
      // 1. "Kto": dekodowanie (0 - 0,8 s)
      setFx('kto');
      let step = 0;
      const dec = setInterval(() => {
        step += 1;
        setKto(word.map((ch, i) => (step >= 4 + i * 3 ? ch : GLYPHS[Math.floor(Math.random() * GLYPHS.length)])));
        if (step >= 4 + (word.length - 1) * 3) { clearInterval(dec); setKto(null); }
      }, STEP);
      intervals.push(dec);
      // 2. "co": zaczernienie i odsłonięcie (1,6 - 3,0 s)
      at(1600, () => setFx('co'));
      // 3. "kiedy": znacznik czasu tyka i kursor (3,8 - 7,0 s)
      at(3800, () => {
        setFx('kiedy');
        setTime(stamp(new Date()));
        const tick = setInterval(() => setTime(stamp(new Date())), 1000);
        intervals.push(tick);
        at(3200, () => clearInterval(tick));
      });
      at(7200, () => setFx(''));
    };

    at(START, cycle);
    const loop = setInterval(cycle, LOOP);
    intervals.push(loop);
    return () => { timers.forEach(clearTimeout); intervals.forEach(clearInterval); };
  }, []);

  return (
    <span ref={root} className="pt-hero-title" data-fx={fx || undefined}>
      <span className="pt-hw" data-w="kto" aria-label="Kto">
        {[...'Kto'].map((ch, i) => (
          <span key={i} data-l="" aria-hidden="true"
            style={kto && widths ? { display: 'inline-block', width: widths[i], textAlign: 'center', overflow: 'hidden', verticalAlign: 'bottom' } : undefined}
            data-g={kto && kto[i] !== ch ? 'x' : undefined}>{kto ? kto[i] : ch}</span>
        ))}
      </span>
      , <span className="pt-hw" data-w="co">co</span> i&nbsp;
      <span className="pt-hw" data-w="kiedy">kiedy?<i className="pt-hw__cur" aria-hidden="true">_</i>
        <span className="pt-hw__ts" aria-hidden="true">{time}</span>
      </span>
    </span>
  );
}
