/** Publiczny eksport danych i kanały RSS (backend/news/exports.py). Filtry to ten sam query string co na liście. */
export type ExportDataset = "diagnozy" | "osoby" | "zrodla" | "wskazniki";

export function exportHref(dataset: ExportDataset, ext: "csv" | "json", params: Record<string, string | number | undefined | null> = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== null && String(value) !== "") query.set(key, String(value)); });
  const suffix = query.toString();
  return `/api/export/${dataset}.${ext}${suffix ? `?${suffix}` : ""}`;
}

export const RSS_FEEDS = [
  { name: "przekazy", label: "Przekazy dnia", href: "/api/feeds/przekazy.xml" },
  { name: "diagnozy", label: "Opublikowane diagnozy", href: "/api/feeds/diagnozy.xml" },
  { name: "raporty", label: "Raporty tygodnia", href: "/api/feeds/raporty.xml" },
] as const;
