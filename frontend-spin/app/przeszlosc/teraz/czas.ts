import { adresZrodla } from './link';

/** Czas w strefie Europe/Warsaw, po polsku, bez zależności od strefy przeglądarki. */
const STREFA = 'Europe/Warsaw';

const formatGodziny = new Intl.DateTimeFormat('pl-PL', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: STREFA });
const formatDnia = new Intl.DateTimeFormat('sv-SE', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: STREFA });
const formatKrotki = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', timeZone: STREFA });

const dzien = (ms: number) => formatDnia.format(ms);

/** „14:32”; pusty tekst dla braku albo błędnej daty. */
export function godzina(iso: string | null | undefined): string {
  if (!iso) return '';
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? formatGodziny.format(ms) : '';
}

/** „dziś o godz. 14:32”, „wczoraj o godz. 21:10”, „12 listopada o godz. 09:40”. */
export function dataIGodzina(iso: string | null | undefined, teraz: number = Date.now()): string {
  if (!iso) return '';
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return '';
  const g = formatGodziny.format(ms);
  const d = dzien(ms);
  if (d === dzien(teraz)) return `dziś o godz. ${g}`;
  if (d === dzien(teraz - 86_400_000)) return `wczoraj o godz. ${g}`;
  return `${formatKrotki.format(ms)} o godz. ${g}`;
}

/** „od godz. 14:32” (dziś), „od wczoraj, godz. 14:32”, „od 12 listopada, godz. 09:40”: początek okresu w zdaniu. */
export function odGodziny(iso: string | null | undefined, teraz: number = Date.now()): string {
  if (!iso) return '';
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return '';
  const g = formatGodziny.format(ms);
  const d = dzien(ms);
  if (d === dzien(teraz)) return `od godz. ${g}`;
  if (d === dzien(teraz - 86_400_000)) return `od wczoraj, godz. ${g}`;
  return `od ${formatKrotki.format(ms)}, godz. ${g}`;
}

/** „2026-11-18 14:32” w strefie Warszawy (do tabeli i eksportu CSV, sortuje się jak tekst). */
export function czasLokalny(iso: string | null | undefined): string {
  if (!iso) return '';
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return '';
  return `${dzien(ms)} ${formatGodziny.format(ms)}`;
}

/** „3 min temu”, „2 godz. temu”, „3 dni temu”. */
export function ileTemu(iso: string | null | undefined, teraz: number = Date.now()): string {
  if (!iso) return '';
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return '';
  const min = Math.max(0, Math.round((teraz - ms) / 60_000));
  if (min < 1) return 'przed chwilą';
  if (min < 60) return `${min} min temu`;
  const godz = Math.round(min / 60);
  if (godz < 24) return `${godz} godz. temu`;
  return `${Math.round(godz / 24)} dni temu`;
}

/** Adres hosta bez „www.”, do podpisu odnośnika; pusty przy błędnym adresie i przy adresie innym niż bezwzględny http(s). */
export function host(url: string | null | undefined): string {
  const adres = adresZrodla(url);
  try { return adres ? new URL(adres).hostname.replace(/^www\./, '') : ''; } catch { return ''; }
}
