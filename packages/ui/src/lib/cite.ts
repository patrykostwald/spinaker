/** „Cytuj”: gotowy zapis bibliograficzny z permalinkiem, datą publikacji i datą dostępu (czysta funkcja, testowana w cite.test.mjs). */
export type CitationInput = {
  /** Autor lub wydawca pierwotny, np. nazwa źródła; puste = pomijamy. */
  author?: string;
  title: string;
  /** Data publikacji (ISO); brak = „data publikacji nieustalona”. */
  publishedAt?: string | null;
  /** Dla stron bez daty publikacji (np. profil osoby): data ostatniej weryfikacji danych. */
  updatedAt?: string | null;
  /** Bezwzględny adres strony (permalink). */
  url: string;
  /** Dodatkowy opis rodzaju, np. „Diagnoza AI”. */
  kind?: string;
  /** Moment dostępu; domyślnie teraz. */
  accessedAt?: Date | string;
};

const day = (value: Date | string | null | undefined) => {
  if (!value) return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("pl-PL", { timeZone: "Europe/Warsaw", day: "numeric", month: "long", year: "numeric" }).format(date);
};

export function buildCitation({ author, title, publishedAt, updatedAt, url, kind, accessedAt = new Date() }: CitationInput): string {
  const published = day(publishedAt);
  const updated = day(updatedAt);
  const accessed = day(accessedAt);
  const parts = [
    author?.trim() ? `${author.trim()}.` : "",
    `„${title.trim()}”${kind ? ` (${kind})` : ""}.`,
    "spin.clinic,",
    published ? `opublikowano: ${published},` : updated ? `zaktualizowano: ${updated},` : "data publikacji nieustalona,",
    `dostęp: ${accessed},`,
    url,
  ];
  return parts.filter(Boolean).join(" ");
}
