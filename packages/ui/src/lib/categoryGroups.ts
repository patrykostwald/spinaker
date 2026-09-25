/**
 * Osiem grup kategorii portalu (decyzja właściciela 25.09) — zamiast 18 kategorii backendu w filtrach Bazy,
 * formularzu nitki użytkownika i kolumnach „wodospadu”. Każda kategoria `ArticleCategory` należy do
 * dokładnie jednej grupy; kolejność alfabetyczna (polska kolacja). Etykiety na kartach zostają
 * szczegółowe („Komunikat”, „Akt prawny”) — grupa to tylko sposób filtrowania i układania.
 */

export type CategoryGroup = { key: string; label: string; categories: string[] };

const GROUPS: CategoryGroup[] = [
  { key: "artykul", label: "Artykuł", categories: ["article", "opinion", "factcheck", "context"] },
  { key: "film", label: "Film", categories: ["video"] },
  { key: "inne", label: "Inne", categories: ["other", "mention", "tweet"] },
  { key: "podcast", label: "Podcast", categories: ["podcast"] },
  { key: "publiczne", label: "Publiczne", categories: ["voting", "legislation", "parliamentary_print", "document", "statement"] },
  { key: "reklama", label: "Reklama", categories: ["advertisement", "sponsored"] },
  { key: "reportaz", label: "Reportaż", categories: ["reportage"] },
  { key: "wywiad", label: "Wywiad", categories: ["interview"] },
];

export const CATEGORY_GROUPS: CategoryGroup[] = [...GROUPS].sort((a, b) => a.label.localeCompare(b.label, "pl"));

export function categoryGroupByKey(key: string): CategoryGroup | undefined {
  return CATEGORY_GROUPS.find((group) => group.key === key);
}

/** Grupa danej kategorii backendu; nieznana kategoria trafia do „Inne”. */
export function categoryGroupOf(category: string): CategoryGroup {
  return CATEGORY_GROUPS.find((group) => group.categories.includes(category)) ?? categoryGroupByKey("inne")!;
}

/**
 * Klucze grup → kategorie backendu dla `?categories=`. Wartości, które nie są kluczem grupy
 * (np. pojedyncza kategoria zapisana w starszej nitce użytkownika), przechodzą bez zmian.
 */
export function expandCategories(values: string[]): string[] {
  const out = new Set<string>();
  for (const value of values) {
    const group = categoryGroupByKey(value);
    if (group) group.categories.forEach((category) => out.add(category));
    else if (value) out.add(value);
  }
  return [...out];
}
