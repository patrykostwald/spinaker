/**
 * Mapa ścieżek (właściciel 4.10 i 5.10): zapisujemy wyłącznie trasę przez serwis, nic o osobie.
 * Bez identyfikatora, ciasteczek i pamięci przeglądarki; kroki żyją tylko w pamięci karty i trafiają paczką
 * na serwer, który od razu zlicza je w godzinnych koszykach. Kliknięcia opisuje klasa elementu, nigdy jego tekst.
 */
const ENTRY = '(wejście)', EXIT = '(wyjście)';
type Step = [string, string, string];

let queue: Step[] = [];
let trail: string[] = [];
let current = '';
let started = false;
let lastClicks: { target: Element; at: number }[] = [];

const device = () => (window.innerWidth < 768 ? 'phone' : 'desktop');
const disabled = () => typeof window === 'undefined' || navigator.webdriver;

/** Nazwa elementu do raportu: pierwsza klasa serwisu (sc-…), inaczej nazwa znacznika. */
function label(element: Element): string {
  const token = [...element.classList].find(name => name.startsWith('sc-')) ?? element.tagName.toLowerCase();
  return token.toLowerCase().replace(/[^a-z0-9_-]/g, '').slice(0, 50);
}

function flush() {
  if (!queue.length) return;
  const body = JSON.stringify({ steps: queue.splice(0, 40), device: device() });
  try {
    if (!navigator.sendBeacon?.('/api/feedback/journey/', new Blob([body], { type: 'application/json' }))) {
      void fetch('/api/feedback/journey/', { method: 'POST', body, headers: { 'Content-Type': 'application/json' }, keepalive: true, credentials: 'omit' });
    }
  } catch { /* ścieżka nigdy nie psuje strony */ }
}

function push(step: Step) {
  queue.push(step);
  if (queue.length >= 30) flush();
}

function onClick(event: MouseEvent) {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  const control = target.closest('button, a, [role="button"], summary, label');
  if (control) push([current, current, `click:${label(control)}`]);
  // 3 kliknięcia w sekundę w to samo miejsce: najpewniej coś nie reaguje
  const spot = target.closest('[class*="sc-"]') ?? target;
  const now = Date.now();
  lastClicks = [...lastClicks.filter(click => now - click.at < 1000 && click.target === spot), { target: spot, at: now }];
  if (lastClicks.length === 3) push([current, current, `rage:${label(spot)}`]);
}

function onHide() {
  if (document.visibilityState === 'hidden') { push([current, EXIT, 'exit']); flush(); }
}

/** Wywoływane przy każdej zmianie adresu. */
export function trackPage(path: string) {
  if (disabled() || path === current) return;
  if (!started) {
    started = true;
    document.addEventListener('click', onClick, { capture: true, passive: true });
    document.addEventListener('visibilitychange', onHide);
    window.addEventListener('pagehide', () => flush());
  }
  push([current || ENTRY, path, 'nav']);
  current = path;
  trail = [...trail, path].slice(-12);
}

/** Ostatnie strony tej wizyty (dołączane jawnie do zgłoszenia błędu). */
export function journeyTrail(): string[] {
  return [...trail];
}
