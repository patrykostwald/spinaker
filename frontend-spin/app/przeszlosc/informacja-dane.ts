/**
 * Decyzje właściciela 13.10.2026 (API-v3 sekcja 0): funkcje czyste dla klauzuli informacyjnej RODO art. 14 (`privacy_notice`)
 * z formularzem sprzeciwu oraz dla wykazu OPP z 1,5% podatku (`opp_tax`) w drzewie pieniędzy. Bez Reacta i DOM
 * (ładowane w testach przez transpileModule). Test: tests/125-przeszlosc-decyzje-wlasciciela.test.cjs.
 */

export type PrivacyNotice = {
  version?: string; date?: string; status?: string; title?: string;
  sections?: { heading?: string; text?: string }[];
  objection_url?: string; contact?: string;
};
export type Relation = 'osoba' | 'przedstawiciel' | 'inna';
export const RELATIONS: [Relation, string][] = [['osoba', 'Dotyczy mnie'], ['przedstawiciel', 'Jestem przedstawicielem osoby'], ['inna', 'Inna sytuacja']];
export const REASON_MIN = 20;
/** Kontrakt: sprzeciw zawsze 202 z tą samą treścią; formularz pokazuje jeden neutralny komunikat. */
export const OBJECTION_SENT = 'Wniosek przyjęty, sprawdź e-mail.';
/** Strona potwierdzenia (link z e-maila): komunikat dla statusu GET /api/przeszlosc/sprzeciw/potwierdz/<token>/. */
export function confirmMessage(status: number): { title: string; text: string } {
  if (status === 200) return { title: 'Sprzeciw potwierdzony', text: 'Dziękujemy. Sprzeciw trafił do rozpatrzenia; odpowiemy na adres z formularza.' };
  if (status === 410) return { title: 'Link wygasł lub został już użyty', text: 'Ten link potwierdzający jest jednorazowy i ma ograniczony czas ważności. Jeśli trzeba, wyślij wniosek ponownie z profilu osoby.' };
  if (status === 404) return { title: 'Nie znaleziono linku', text: 'Sprawdź, czy adres został skopiowany w całości, albo wyślij wniosek ponownie z profilu osoby.' };
  return { title: 'Nie udało się sprawdzić linku', text: 'Spróbuj za chwilę.' };
}
export const REASON_MAX = 2000;

/** Adres formularza tylko z tego serwisu (ścieżka /api/...) albo https; inaczej null - formularz się nie pokazuje. */
export function objectionUrl(n: PrivacyNotice | null | undefined): string | null {
  const u = (n?.objection_url ?? '').trim();
  if (/^\/api\/[^\s]*$/.test(u)) return u;
  return /^https:\/\/[^\s]+$/i.test(u) ? u : null;
}

/** Klauzula nadaje się do pokazania: tytuł albo co najmniej jedna sekcja z tekstem. */
export function noticeSections(n: PrivacyNotice | null | undefined): { heading: string; text: string }[] {
  return (n?.sections ?? []).map(s => ({ heading: (s.heading ?? '').trim(), text: (s.text ?? '').trim() })).filter(s => s.text);
}

/** Pierwsza linia widoczna przy zwiniętej klauzuli: tytuł, wersja i data (bez treści prawnej). */
export function noticeLine(n: PrivacyNotice): string {
  const meta = [n.version ? `wersja ${n.version}` : '', n.date ? `z ${n.date}` : '', n.status ?? ''].filter(Boolean).join(', ');
  return `${(n.title ?? 'Informacja o danych').trim()}${meta ? ` (${meta})` : ''}`;
}

/** Walidacja formularza sprzeciwu po stronie przeglądarki (serwer i tak waliduje): komunikat albo null. */
export function objectionError(reason: string, contact: string, relation: string): string | null {
  const r = reason.trim();
  if (r.length < REASON_MIN) return `Opisz powód (co najmniej ${REASON_MIN} znaków).`;
  if (r.length > REASON_MAX) return `Powód może mieć najwyżej ${REASON_MAX} znaków.`;
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.trim())) return 'Podaj adres e-mail - wyślemy link do potwierdzenia.';
  if (!RELATIONS.some(([k]) => k === relation)) return 'Wybierz, kogo dotyczy sprzeciw.';
  return null;
}
export function objectionBody(reason: string, contact: string, relation: Relation) {
  return { reason: reason.trim().slice(0, REASON_MAX), contact: contact.trim(), relation };
}

/* ---------------------------------------------------------------- wykaz OPP z 1,5% podatku */

export type OppRow = { id: string; tax_year?: number | null; payment_year?: number | null; amount?: number | null; currency?: string; source?: string; url?: string; attribution?: string; file_date?: string | null };
export type OppTax = { count?: number; results?: OppRow[]; note?: string };

/** Wiersz wykazu: rok podatkowy, rok wypłaty, kwota (osobno, bez sumowania z dotacjami), źródło MF. */
export function oppLine(r: OppRow, money: (amount: number | null, currency: string) => string): string {
  return [r.amount != null ? money(r.amount, r.currency || 'PLN') : 'kwota: brak w naszych danych',
    r.tax_year ? `rok podatkowy ${r.tax_year}` : '', r.payment_year ? `wypłata w ${r.payment_year}` : '', 'Ministerstwo Finansów, wykaz OPP'].filter(Boolean).join(' · ');
}
