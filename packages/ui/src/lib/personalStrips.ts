export type PersonalStrip = { id: string; label: string; query: string; category: string; sourceId: number | '' };

const STORAGE_KEY = 'spinclinic-mvp-strips';
const MAX_STRIPS = 5;

function read(): PersonalStrip[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
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
