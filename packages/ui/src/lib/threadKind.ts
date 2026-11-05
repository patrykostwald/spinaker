/**
 * Rodzaj spinki (właściciel 6.10): mała linia meta nad tytułem „AUTOR · RODZAJ”.
 * Dr. Spin: rodzaje z jednego szablonu tytułów „Rodzaj: synteza” (backend/news/thread_review.py, EDITOR).
 * Czytelnik: 4 rodzaje do wyboru na starcie kreatora (Konsylium 2357: 4 szablony), domyślnie kontekst.
 * Te same wartości co PersonalContextThread.KINDS w backend/news/account_models.py.
 */
import type { CommunityThreadSummary } from './community';
import { reactionTint } from './clipColor';
import { sumCounts } from './mood';

export type ThreadKind = 'diagnoza' | 'przekaz_dnia' | 'nowa_narracja' | 'sygnal_lobbingu' | 'kontekst' | 'sprzecznosc' | 'sprawdzam' | 'pytanie';

export const THREAD_KINDS: Record<ThreadKind, { label: string; glyph: string; hint: string }> = {
  diagnoza: { label: 'Diagnoza', glyph: 'diag', hint: 'Dr. Spin rozkłada wpis polityka na techniki i źródła.' },
  przekaz_dnia: { label: 'Przekaz dnia', glyph: 'post', hint: 'Wspólny przekaz jednej strony z jednego dnia.' },
  nowa_narracja: { label: 'Nowa narracja', glyph: 'hook', hint: 'To samo sformułowanie naraz u wielu autorów.' },
  sygnal_lobbingu: { label: 'Sygnał lobbingu', glyph: 'sejm', hint: 'Druk w Sejmie zestawiony z mediami branżowymi.' },
  kontekst: { label: 'Kontekst', glyph: 'pin', hint: 'Dokładam tło, którego brakuje w przekazie.' },
  sprzecznosc: { label: 'Sprzeczność', glyph: 'but', hint: 'Zestawiam wypowiedź z tym, co jej przeczy.' },
  sprawdzam: { label: 'Sprawdzam', glyph: 'check', hint: 'Biorę tezę i układam dowody za i przeciw.' },
  pytanie: { label: 'Pytanie', glyph: 'ask', hint: 'Pokazuję, czego jeszcze nie wiemy.' },
};
/** Rodzaje do wyboru w kreatorze (kolejność = kolejność przycisków); rodzaje Dr. Spina są zarezerwowane. */
export const READER_KINDS: ThreadKind[] = ['kontekst', 'sprzecznosc', 'sprawdzam', 'pytanie'];

type KindSource = Pick<CommunityThreadSummary, 'title' | 'diagnosis_id' | 'narrative' | 'signal_kind'> & { kind?: string | null };

/** Rodzaj z API; przed wdrożeniem pola - z pochodzenia spinki albo przedrostka tytułu. */
export function threadKind(thread: KindSource): ThreadKind {
  if (thread.kind && thread.kind in THREAD_KINDS) return thread.kind as ThreadKind;
  if (thread.diagnosis_id != null) return 'diagnoza';
  if (thread.narrative) return 'przekaz_dnia';
  if (thread.signal_kind === 'lobbying') return 'sygnal_lobbingu';
  if (thread.signal_kind === 'new_narrative') return 'nowa_narracja';
  const prefix = (Object.keys(THREAD_KINDS) as ThreadKind[]).find(key => startsWithLabel(thread.title, THREAD_KINDS[key].label));
  return prefix ?? 'kontekst';
}

const startsWithLabel = (title: string, label: string) => title.toLocaleLowerCase('pl').startsWith(label.toLocaleLowerCase('pl') + ':');

/** Tytuł bez przedrostka „Rodzaj:”, który powtarzałby linię meta (tylko wyświetlanie; dane zostają). */
export function displayTitle(thread: KindSource): string {
  const label = THREAD_KINDS[threadKind(thread)].label;
  return startsWithLabel(thread.title, label) ? thread.title.slice(label.length + 1).trim() || thread.title : thread.title;
}

/** Kolor etykiety rodzaju: przeważająca reakcja czytelników na połączenia; bez reakcji - neutralny (null). */
export function kindTint(thread: Pick<CommunityThreadSummary, 'clips'>): string | null {
  return reactionTint(sumCounts(thread.clips));
}

/** Kolor autora: Dr. Spin zarezerwowany niebieski, czytelnik - kolor nicka (konta e-mail bez koloru - biały). */
export function authorColor(thread: Pick<CommunityThreadSummary, 'is_ai' | 'author_color'>): string {
  return thread.is_ai ? 'var(--sc-accent)' : thread.author_color || 'var(--sc-text)';
}
