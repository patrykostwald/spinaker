export type PersonalStrip = { id: string; label: string; query: string; category: string; sourceId: number | '' };

const STORAGE_KEY = 'spinclinic-mvp-strips';
const MAX_STRIPS = 5;

/**
 * Paski na start - Publiczne i Film, bo z tych źródeł dane płyną stale (decyzja właściciela 27.09).
 * Czytelnik może je zmienić, usunąć i dodać kolejne; zapis zostaje na urządzeniu.
 */
export const DEFAULT_STRIPS: PersonalStrip[] = [
  { id: 'preset-publiczne', label: 'Publiczne', query: '', category: 'publiczne', sourceId: '' },
  { id: 'preset-film', label: 'Film', query: '', category: 'film', sourceId: '' },
];

/** Poprzedni zestaw startowy - kto go nie zmieniał, dostaje nowy; własne paski zostają nietknięte. */
const OLD_DEFAULT_IDS = 'preset-publiczne,preset-artykuly,preset-sejm';
const OLD_DEFAULT_LABELS = 'Instytucje publiczne,Media - artykuły,Sejm';

function read(): PersonalStrip[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const stored: PersonalStrip[] | null = raw === null ? null : JSON.parse(raw);
    const untouchedOld = stored?.map(strip => strip.id).join(',') === OLD_DEFAULT_IDS
      && stored.map(strip => strip.label).join(',') === OLD_DEFAULT_LABELS;
    if (stored === null || untouchedOld) {
      write(DEFAULT_STRIPS);
      return DEFAULT_STRIPS;
    }
    return stored;
  } catch {
    return [];
  }
}

function write(strips: PersonalStrip[]) {
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(strips)); } catch { /* private mode: settings just won't persist */ }
}

export const MAX_PERSONAL_STRIPS = MAX_STRIPS;
export function loadPersonalStrips(): PersonalStrip[] { return read(); }
export function savePersonalStrip(strip: PersonalStrip): PersonalStrip[] {
  const current = read();
  if (current.length >= MAX_STRIPS) return current;
  const next = [...current, strip];
  write(next);
  return next;
}
export function removePersonalStrip(id: string): PersonalStrip[] {
  const next = read().filter(strip => strip.id !== id);
  write(next);
  return next;
}
export function updatePersonalStrip(strip: PersonalStrip): PersonalStrip[] {
  const next = read().map(current => current.id === strip.id ? strip : current);
  write(next);
  return next;
}
