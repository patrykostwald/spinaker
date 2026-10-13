import { apiFetch, ApiError } from './api';
import { glueShortWords } from './typography';

/**
 * „Wcześniej i teraz” (zmiana stanowiska): dwie wypowiedzi tej samej osoby o tym samym temacie, obok siebie, bez oceny.
 *
 * Kontrakt: gust/spin/port/API-v3.md, sekcja 5 (flaga backendu POSITION_PAIRS_ENABLED, domyślnie wyłączona). Publicznie
 * tylko pary ZATWIERDZONE przez człowieka. Front pokazuje je wyłącznie przy fladze NEXT_PUBLIC_POSITION_PAIRS=true
 * (domyślnie wyłączona; w podglądzie właściciela, cookie sc_preview, jak pozostałe flagi) i tylko gdy API zwróciło pary.
 *
 * Zasada naczelna: TA SAMA MIARA DLA KAŻDEJ STRONY, ZAWSZE. Ten plik nie zawiera żadnej logiki zależnej od osoby, partii
 * ani treści: walidacja jest strukturalna (daty, źródło, cytat albo głos), kolejność zawsze A (starsza) -> B (nowsza).
 * Brak liczników, rankingów, ocen i kolorów ostrzegawczych.
 */

export type PositionSideKind = 'wpis' | 'wystapienie' | 'glos' | 'wypowiedz';
export type PositionVote = 'za' | 'przeciw' | 'wstrzymał się';
export type PositionSource = { name: string; url: string; fetched_at: string | null };
export type PositionSide = {
  kind: PositionSideKind;
  kind_label: string;
  /** RRRR-MM-DD */
  date: string;
  /** cytat dosłowny (<= 280 znaków) albo null przy głosowaniu */
  quote: string | null;
  vote: PositionVote | null;
  vote_subject: string | null;
  source: PositionSource;
};
export type PositionPairData = {
  id: number;
  topic: string;
  a: PositionSide;
  b: PositionSide;
  /** jedno opisowe zdanie (<= 200 znaków) albo "" */
  context: string;
  approved_at: string | null;
  ai_suggested: boolean;
  notice: string;
  report_url: string;
  /** decyzja właściciela 13.10 (API-v3 sekcja 0): odpowiedź osoby pod parą albo null */
  subject_response: SubjectResponse | null;
};
export type SubjectResponse = { label: string; text: string; date: string | null };
/** Odpowiedź osoby z API: tekst 10-600 znaków, etykieta domyślnie "Odpowiedź osoby"; inaczej null. */
export function normalizeResponse(raw: unknown): SubjectResponse | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const body = typeof r.text === 'string' ? r.text.trim() : '';
  if (body.length < 1 || body.length > 600) return null;
  const label = typeof r.label === 'string' && r.label.trim() ? r.label.trim() : 'Odpowiedź osoby';
  return { label, text: body, date: typeof r.date === 'string' && /^\d{4}-\d{2}-\d{2}/.test(r.date) ? r.date : null };
}
export type PositionPairsBlock = { items: PositionPairData[]; notice: string; paused: boolean };
export type PositionPairPerson = { id: number; slug: string; name: string };

export const POSITION_PAIRS_NOTICE = 'Dwie wypowiedzi o tym samym temacie. Pokazujemy je obok siebie bez oceny. Sprawdź źródła i kontekst.';
export const POSITION_PAIRS_TITLE = 'Wcześniej i teraz';
/** Nazwa łącznika w interfejsie (typ w danych spinek zostaje „przeczy”). */
export const POSITION_CONNECTOR_LABEL = 'inaczej niż';
export const POSITION_PAIRS_PAUSED = 'Zestawienia „Wcześniej i teraz” są wstrzymane na czas ciszy wyborczej.';
export const POSITION_PAIRS_COMPLETENESS = 'Pokazujemy tylko zestawienia zatwierdzone przez człowieka. Brak zestawienia nie oznacza, że wypowiedzi się nie różnią.';
export const POSITION_PAIRS_ANCHOR = 'wczesniej-i-teraz';

const KIND_LABELS: Record<PositionSideKind, string> = {
  wpis: 'Wpis na X', wystapienie: 'Wystąpienie w Sejmie', glos: 'Głosowanie w Sejmie', wypowiedz: 'Wypowiedź',
};
const VOTES: PositionVote[] = ['za', 'przeciw', 'wstrzymał się'];
const DAY = /^\d{4}-\d{2}-\d{2}/;

/** Tylko adresy http(s): nic z javascript: ani data: nie trafia do href. */
export function safeHttpUrl(url: unknown): string | null {
  return typeof url === 'string' && /^https?:\/\/[^\s]+$/i.test(url.trim()) ? url.trim() : null;
}

/** Odnośnik źródła: http(s) albo adres wewnętrzny serwisu ("/klinika/123"); nic innego nie trafia do href. */
export function safeSourceHref(url: unknown): string | null {
  const http = safeHttpUrl(url);
  if (http) return http;
  return typeof url === 'string' && /^\/(?!\/)[^\s]*$/.test(url.trim()) ? url.trim() : null;
}

/** Domena do podpisu odnośnika źródła („x.com”, „sejm.gov.pl”); adres wewnętrzny = nazwa serwisu. */
export function sourceDomain(url: string): string {
  if (url.startsWith('/')) return 'spin.clinic';
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; }
}

const text = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

function normalizeSide(raw: unknown): PositionSide | null {
  if (!raw || typeof raw !== 'object') return null;
  const side = raw as Record<string, unknown>;
  const date = typeof side.date === 'string' && DAY.test(side.date) ? side.date.slice(0, 10) : '';
  const kind = (['wpis', 'wystapienie', 'glos', 'wypowiedz'] as const).find(item => item === side.kind) ?? 'wypowiedz';
  const quote = text(side.quote) || null;
  const vote = VOTES.find(item => item === side.vote) ?? null;
  const source = side.source && typeof side.source === 'object' ? side.source as Record<string, unknown> : null;
  const url = safeHttpUrl(source?.url);
  const name = text(source?.name);
  // para bez daty, treści albo źródła z odnośnikiem nie jest weryfikowalna - nie pokazujemy jej (ta sama zasada dla każdej)
  if (!date || (!quote && !vote) || !url || !name) return null;
  const fetched = typeof source?.fetched_at === 'string' && DAY.test(source.fetched_at) ? source.fetched_at.slice(0, 10) : null;
  return {
    kind, kind_label: text(side.kind_label) || KIND_LABELS[kind], date, quote, vote,
    vote_subject: text(side.vote_subject) || null, source: { name, url, fetched_at: fetched },
  };
}

/** Para z API albo null, gdy nie spełnia warunków strukturalnych (id, temat, dwie strony, A nie nowsza niż B). */
export function normalizePair(raw: unknown): PositionPairData | null {
  if (!raw || typeof raw !== 'object') return null;
  const pair = raw as Record<string, unknown>;
  const id = Number(pair.id);
  const a = normalizeSide(pair.a);
  const b = normalizeSide(pair.b);
  const topic = text(pair.topic);
  if (!Number.isInteger(id) || id < 1 || !a || !b || !topic || a.date > b.date) return null;
  const report = typeof pair.report_url === 'string' && /^\/api\/stanowiska\/\d+\/zgloszenie\/?$/.test(pair.report_url) ? pair.report_url : `/api/stanowiska/${id}/zgloszenie/`;
  return {
    id, topic, a, b, context: text(pair.context), approved_at: typeof pair.approved_at === 'string' ? pair.approved_at : null,
    ai_suggested: Boolean(pair.ai_suggested), notice: text(pair.notice) || POSITION_PAIRS_NOTICE, report_url: report,
    subject_response: normalizeResponse(pair.subject_response),
  };
}

/** Blok z API (profil, diagnoza, /stanowiska/) bez par niepoprawnych; brak klucza albo null = brak bloku. */
export function normalizeBlock(raw: unknown): PositionPairsBlock | null {
  if (!raw || typeof raw !== 'object') return null;
  const block = raw as Record<string, unknown>;
  const items = Array.isArray(block.items) ? block.items.map(normalizePair).filter((item): item is PositionPairData => item !== null) : [];
  return { items, notice: text(block.notice) || POSITION_PAIRS_NOTICE, paused: block.paused === true };
}

const longDate = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
const shortDate = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const at = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00Z`);

/** „4 marca 2025” (data z API jest dniem kalendarzowym, bez przesunięć strefy). */
// twarde spacje w datach: dzień, miesiąc i rok nie rozdzielają się na końcu wiersza
export function pairDate(iso: string): string { return longDate.format(at(iso)).replace(/ /g, ' '); }
export function pairDateShort(iso: string): string { return shortDate.format(at(iso)).replace(/ /g, ' '); }

/** Etykieta dostępności pary: „Wcześniej: data, Teraz: data”. */
export function pairAriaLabel(pair: Pick<PositionPairData, 'a' | 'b'>, labels: [string, string] = ['Wcześniej', 'Teraz']): string {
  return `${labels[0]}: ${pairDate(pair.a.date)}, ${labels[1]}: ${pairDate(pair.b.date)}`;
}

/** Szacunek, czy cytat nie zmieści się w budżecie linii (przed pomiarem w przeglądarce i na serwerze). */
export function quoteNeedsToggle(side: Pick<PositionSide, 'quote' | 'vote_subject'>, threshold = 150): boolean {
  return (side.quote ?? side.vote_subject ?? '').length > threshold;
}

/** Strona szczegółu pary (spin.clinic); `person` = id albo slug osoby, gdy znamy (pozwala pobrać parę z listy osoby). */
export function pairDetailHref(id: number, person?: string | number | null): string {
  return `/klinika/stanowiska/${id}${person != null && person !== '' ? `?osoba=${encodeURIComponent(String(person))}` : ''}`;
}
/** Sekcja „Wcześniej i teraz” w profilu osoby na przeszłość.today (działa też na spin.clinic, bo ścieżka jest ta sama). */
export function personPairsHref(slugOrId: string | number, pairId?: number): string {
  return `/przeszlosc/osoba/${encodeURIComponent(String(slugOrId))}#${pairId ? `stanowiska-${pairId}` : POSITION_PAIRS_ANCHOR}`;
}

/** Tekst z twardymi spacjami po jednoliterowych słowach (tytuły, kontekst, zdania objaśniające; nie cytaty). */
export const nb = (value: string): string => glueShortWords(value);

/** Nagłówki i opis strony szczegółu (Open Graph): neutralne, bez cytatów i bez słów oceniających. */
export function pairMetaTitle(pair: PositionPairData, name?: string | null): string {
  return `${POSITION_PAIRS_TITLE}: ${pair.topic}${name ? ` - ${name}` : ''}`;
}
export function pairMetaDescription(pair: PositionPairData, name?: string | null): string {
  return `${name ? `Dwie wypowiedzi: ${name}, ` : 'Dwie wypowiedzi '}o tym samym temacie (${pair.topic}) obok siebie, bez oceny: ${pairDate(pair.a.date)} i ${pairDate(pair.b.date)}. Sprawdź źródła i kontekst.`.slice(0, 300);
}

// --- pobieranie (tylko odczyt; 404 = funkcja wyłączona po stronie backendu albo brak pary) ---

export type PersonPairs = PositionPairsBlock & { person: PositionPairPerson | null };

function person(raw: unknown): PositionPairPerson | null {
  if (!raw || typeof raw !== 'object') return null;
  const value = raw as Record<string, unknown>;
  return Number.isInteger(Number(value.id)) && typeof value.name === 'string'
    ? { id: Number(value.id), slug: typeof value.slug === 'string' ? value.slug : '', name: value.name } : null;
}

/** GET /api/przeszlosc/osoba/<id albo slug>/stanowiska/; null, gdy funkcja wyłączona albo osoba nieznana. */
export async function fetchPersonPairs(ident: string | number): Promise<PersonPairs | null> {
  try {
    const data = await apiFetch<Record<string, unknown>>(`/api/przeszlosc/osoba/${encodeURIComponent(String(ident))}/stanowiska/`);
    const block = normalizeBlock(data);
    return block ? { ...block, person: person(data.person) } : null;
  } catch (error) {
    if (error instanceof ApiError) return null;
    throw error;
  }
}

/**
 * Jedna para. Z `ident` osoby szukamy jej na liście osoby (kontrakt sekcji 5); bez niego prosimy o GET /api/stanowiska/<id>/
 * (do potwierdzenia z backendem - w kontrakcie jest tylko lista osoby i zgłoszenie).
 */
export async function fetchPair(id: number, ident?: string | number | null): Promise<{ pair: PositionPairData; person: PositionPairPerson | null; paused: boolean } | null> {
  if (ident != null && ident !== '') {
    const list = await fetchPersonPairs(ident);
    const pair = list?.items.find(item => item.id === id);
    return list && pair ? { pair, person: list.person, paused: list.paused } : null;
  }
  try {
    const data = await apiFetch<Record<string, unknown>>(`/api/stanowiska/${id}/`);
    const pair = normalizePair(data.pair ?? data);
    return pair ? { pair, person: person(data.person), paused: data.paused === true } : null;
  } catch (error) {
    if (error instanceof ApiError) return null;
    throw error;
  }
}

// --- spinki: łącznik "przeczy" (w interfejsie "inaczej niż") renderowany tym samym komponentem ---

type ThreadBox = { title?: string; body?: string; url?: string; source_name?: string; domain?: string; published_date?: string | null; box_type?: string };
const BOX_KIND_LABELS: Record<string, string> = {
  post: 'Wpis na X', claim: 'Sprawdzenie', source: 'Źródło', technique: 'Chwyt', diagnosis: 'Diagnoza', message: 'Przekaz dnia', print: 'Druk sejmowy',
  amendment: 'Poprawka', consultation: 'Postulat organizacji', registry: 'Wpis w rejestrze', declaration: 'Zgłoszenie w uzasadnieniu', summary: 'Podsumowanie Dr. Spina',
};

function threadSide(box: ThreadBox): PositionSide | null {
  const date = typeof box.published_date === 'string' && DAY.test(box.published_date) ? box.published_date.slice(0, 10) : '';
  const quote = text(box.body) || text(box.title);
  const url = safeSourceHref(box.url);
  const name = text(box.source_name) || text(box.domain) || (url ? sourceDomain(url) : '');
  // bez daty, treści albo adresu źródła nie zestawiamy (nie zgadujemy dat): spinka pokazuje wtedy zwykły opis połączenia
  if (!date || !quote || !url || !name) return null;
  return { kind: 'wypowiedz', kind_label: BOX_KIND_LABELS[box.box_type ?? ''] ?? 'Materiał', date, quote: quote.slice(0, 600), vote: null, vote_subject: null, source: { name, url, fetched_at: null } };
}

/** Para z dwóch sąsiednich boksów spinki (kolejność autora, nie chronologia); null, gdy któryś nie ma daty, treści albo adresu. */
export function pairFromThreadBoxes(from: ThreadBox, to: ThreadBox, id: number, topic: string): PositionPairData | null {
  const a = threadSide(from);
  const b = threadSide(to);
  return a && b ? { id, topic, a, b, context: '', approved_at: null, ai_suggested: false, notice: '', report_url: '', subject_response: null } : null;
}

/* ---------------------------------------------------------------- odpowiedź osoby: formularz (API-v3 sekcja 0, 3. recenzja) */
export const REPLY_MIN = 10;
export const REPLY_MAX = 600;
/** Walidacja w przeglądarce: tekst 10-600 znaków; kod (jeśli podany) bez spacji, do 64 znaków. */
export function replyError(body: string, code: string): string | null {
  const t = body.trim();
  if (t.length < REPLY_MIN) return `Odpowiedź musi mieć co najmniej ${REPLY_MIN} znaków.`;
  if (t.length > REPLY_MAX) return `Odpowiedź może mieć najwyżej ${REPLY_MAX} znaków.`;
  if (code.trim() && !/^[A-Za-z0-9-]{4,64}$/.test(code.trim())) return "Kod z wiadomości ma tylko litery, cyfry i myślniki.";
  return null;
}
export function replyBody(body: string, code: string): { text: string; token?: string } {
  const token = code.trim();
  return token ? { text: body.trim(), token } : { text: body.trim() };
}
/** Komunikaty: 404 = ten sam co dla nieistniejącego zestawienia (para niepubliczna nie jest ujawniana). */
export function replyStatusMessage(status: number): string {
  if (status === 202 || status === 200) return "Odpowiedź przyjęta. Pokażemy ją pod zestawieniem po sprawdzeniu nadawcy.";
  if (status === 403) return "Nie możemy przyjąć odpowiedzi bez potwierdzenia: potwierdź adres e-mail i wpisz kod z wiadomości.";
  if (status === 404) return "Nie znaleziono tego zestawienia.";
  if (status === 429) return "Wysłano już za dużo odpowiedzi. Spróbuj później.";
  return "Nie udało się wysłać. Spróbuj za chwilę.";
}