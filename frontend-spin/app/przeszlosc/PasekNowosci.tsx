"use client";
import { useEffect, useRef, useState, type FocusEvent } from 'react';
import { TICK_ANCHOR, TICK_FADE_MS, TICK_INTERVAL_MS, TICK_LABEL, fitWords, readMs, stepIndex, tickItems, tickState, tickVisible, type StartLatest } from './pasek-nowosci-dane';
import './pasek-nowosci.css';

/**
 * Pasek "Ostatnio w bazie" (właściciel 13.10: "pasek jak newsowy z najnowszymi danymi"), pod paskiem menu strony głównej.
 * NIE przewija: jedna linia o stałej wysokości (40 px), jedna pozycja naraz, zmiana co --fx-ticker-interval płynnym przenikaniem
 * (tylko opacity + translateY 4 px). Pauza przy najechaniu, fokusie i w karcie w tle; przycisk Pauza / Wznów (aria-pressed).
 * prefers-reduced-motion: bez zegara i animacji, pierwsza pozycja statyczna + przycisk "Następna". aria-live="off": czytnik nie czyta
 * każdej zmiany, region ma etykietę i pełną obsługę klawiatury. Dane wyłącznie z /api/przeszlosc/start/ (latest[]), te same co sekcja
 * "Najnowsze w bazie" (kotwica #najnowsze). Stany: ładowanie = szkielet tej samej wysokości (bez skoku układu); brak danych albo błąd = brak paska.
 */
export function PasekNowosci({ latest, loading = false, reduced: forced }: { latest?: StartLatest[] | null; loading?: boolean; reduced?: boolean }) {
  const items = tickItems(latest);
  const n = items.length;
  const root = useRef<HTMLElement>(null);
  const [i, setI] = useState(0);
  const [out, setOut] = useState(false);
  const [paused, setPaused] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [reduced, setReduced] = useState(Boolean(forced));
  useEffect(() => {
    if (forced !== undefined) return;
    const m = window.matchMedia('(prefers-reduced-motion: reduce)');
    const on = () => setReduced(m.matches); on();
    m.addEventListener('change', on); return () => m.removeEventListener('change', on);
  }, [forced]);
  useEffect(() => {
    const on = () => setHidden(document.visibilityState === 'hidden'); on();
    document.addEventListener('visibilitychange', on); return () => document.removeEventListener('visibilitychange', on);
  }, []);
  const state = tickState({ reduced, paused, hovered, focused, hidden, n });
  // zegar: czas z tokenów CSS (--fx-ticker-interval, --fx-ticker-fade) czytany przy starcie; wyjście pozycji = atrybut data-out,
  // wejście następnej = nowy element (key) z animacją CSS; żadnego ruchu poza transform / opacity
  useEffect(() => {
    if (state !== 'running') return;
    const cs = root.current ? getComputedStyle(root.current) : null;
    const interval = readMs(cs?.getPropertyValue('--fx-ticker-interval'), TICK_INTERVAL_MS);
    const fade = readMs(cs?.getPropertyValue('--fx-ticker-fade'), TICK_FADE_MS);
    let swap: ReturnType<typeof setTimeout> | undefined;
    const tick = setInterval(() => { setOut(true); swap = setTimeout(() => { setI(x => stepIndex(x, n)); setOut(false); }, fade); }, interval);
    return () => { clearInterval(tick); if (swap) clearTimeout(swap); setOut(false); };
  }, [state, n]);
  // pauza przy fokusie tylko z klawiatury (:focus-visible): po kliknięciu myszą fokus zostaje na przycisku, a "Wznów" ma wznawiać od razu
  const focus = (e: FocusEvent<HTMLElement>) => { const el = e.target as HTMLElement; if (el.matches?.(':focus-visible')) setFocused(true); };
  const blur = (e: FocusEvent<HTMLElement>) => { if (!(e.relatedTarget instanceof Node && e.currentTarget.contains(e.relatedTarget))) setFocused(false); };
  // "Wznów" kliknięte kursorem nad paskiem: wznawia mimo najechania (kolejne wejście kursora znów zatrzyma)
  const toggle = () => setPaused(p => { if (p) setHovered(false); return !p; });

  if (loading && !n) return <section className="pt-tick" role="region" aria-label={TICK_LABEL} aria-busy="true" data-state="loading">
    <Label /><div className="pt-tick__view"><span className="pt-tick__sk" aria-hidden="true" /></div></section>;
  if (!tickVisible(items)) return null;
  const it = items[Math.min(i, n - 1)];
  return <section ref={root} className="pt-tick" role="region" aria-label={TICK_LABEL} data-state={state}
    onPointerEnter={e => { if (e.pointerType === 'mouse') setHovered(true); }} onPointerLeave={() => setHovered(false)} onFocus={focus} onBlur={blur}>
    <Label />
    <div className="pt-tick__view" aria-live="off">
      <p className="pt-tick__item" key={it.key} data-out={out || undefined}>
        <span className="pt-tick__kind">{it.kind}</span>
        {/* data: pełna na komputerze, "dd.mm" na telefonie (CSS), godzina tylko gdy jest w danych */}
        {it.dateText && <time className="pt-tick__time" dateTime={it.date ?? undefined}>
          <span className="pt-tick__d-full">{it.dateText}</span><span className="pt-tick__d-short" aria-hidden="true">{it.dateText.slice(0, 5)}</span>{it.timeText ? ` ${it.timeText}` : ''}</time>}
        <TitleFit text={it.title} />
        {it.url && <a className="pt-tick__src" href={it.url} target="_blank" rel="noopener noreferrer" title={`Źródło: ${it.host || 'oryginał'} (nowa karta)`}>
          <span className="pt-tick__srcname">{it.host || 'źródło'}</span><i aria-hidden="true">↗</i><span className="pt-tick__sr">, nowa karta</span></a>}
      </p>
    </div>
    <div className="pt-tick__act">
      {/* przyciski jako sama ikona (uwaga właściciela: wiersz ma jedną linię bazową); nazwa w aria-label i title; litera o zerowej
          szerokości (U+200B) w przycisku daje mu linię bazową tekstu, więc ikona stoi na środku linii tytułu */}
      {state === 'static' && n > 1 ? <button type="button" className="px-tool pt-tick__btn" aria-label="Następna pozycja" title="Następna pozycja" onClick={() => setI(x => stepIndex(x, n))}>
          {'​'}<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg></button>
        : n > 1 ? <button type="button" className="px-tool pt-tick__btn" aria-pressed={paused} aria-label={paused ? 'Wznów zmianę pozycji' : 'Zatrzymaj zmianę pozycji'} title={paused ? 'Wznów' : 'Pauza'} onClick={toggle}>
          {'​'}{paused ? <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13l10-6.5z" /></svg>
            : <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" /></svg>}</button> : null}
      <a className="px-link pt-tick__all" href={`#${TICK_ANCHOR}`}><span className="pt-tick__txt">Wszystkie nowości</span><i aria-hidden="true">→</i></a>
    </div>
  </section>;
}

/** Tytuł w jednej linii skracany po całym słowie (pomiar canvasem w prawdziwym kroju; panel 13.10: "ucięty w pół słowa"). Do pomiaru
 *  CSS trzyma zwykły wielokropek; pełny tytuł zostaje w title i w tekście dla czytnika. Przeliczane przy zmianie szerokości i po załadowaniu krojów. */
function TitleFit({ text }: { text: string }) {
  const box = useRef<HTMLSpanElement>(null);
  const [cut, setCut] = useState<string | null>(null);
  useEffect(() => {
    const el = box.current; if (!el || typeof ResizeObserver === 'undefined') return;
    const canvas = document.createElement('canvas'); const ctx = canvas.getContext('2d');
    const font = () => { const cs = getComputedStyle(el); return `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`; };
    const fit = () => {
      if (!ctx) return;
      ctx.font = font();
      // 3 px zapasu: pomiar canvasem bywa o ułamek węższy niż skład w DOM (kerning), a wielokropek nie może być przycięty
      setCut(fitWords(text, el.clientWidth - 3, s => ctx.measureText(s).width));
    };
    fit();
    const ro = new ResizeObserver(fit); ro.observe(el);
    // krój (Geist przez next/font) może jeszcze nie być załadowany przy pierwszym pomiarze: wymuś ładowanie i zmierz ponownie
    const fonts = document.fonts;
    if (fonts) { fonts.load(font()).then(fit).catch(() => undefined); fonts.addEventListener('loadingdone', fit); }
    return () => { ro.disconnect(); fonts?.removeEventListener('loadingdone', fit); };
  }, [text]);
  return <span ref={box} className="pt-tick__title" title={text} data-cut={cut ? '' : undefined}>
    <span className="pt-tick__t" aria-hidden={cut ? true : undefined}>{cut ?? text}</span>{cut && <span className="pt-tick__sr">{text}</span>}</span>;
}

function Label() {
  // na telefonie zostaje sam znacznik ">" (etykietę regionu czyta czytnik z aria-label); tekst znika wizualnie, nie z DOM
  return <span className="pt-tick__lab"><span className="pt-tick__lab-t">{TICK_LABEL}</span> <i aria-hidden="true">&gt;</i></span>;
}
