/**
 * Grupy źródeł (Publiczne · Media · Top media) — jedna definicja dla selektora w pasku kategorii,
 * filtrów Bazy i linków w globalnej stopce. Grupa to parametr adresu `?zrodla=`, więc stopka
 * (w layoucie, poza stroną główną) może ją ustawić zwykłym linkiem.
 * Podział wyznacza backend (`portal_group`: lista wiodących mediów + instytucje publiczne); heurystyka
 * po nazwie zostaje tylko jako zapas dla danych bez tego pola (np. tryb demonstracyjny).
 */

import type { Source } from "../../types";

export type SourceGroup = "publiczne" | "media" | "top";

export const SOURCE_GROUPS: { value: SourceGroup; label: string }[] = [
  { value: "publiczne", label: "Publiczne" },
  { value: "media", label: "Media" },
  { value: "top", label: "Top media" },
];

export const SOURCE_GROUP_PARAM = "zrodla";

const IMPORTANT_SOURCE_NAMES = /pap|reuters|tvn|polsat|wyborcza|oko\.press|rp\.pl|gazeta|onet|interia/i;
const PUBLIC_SOURCE_TYPES = /public|official|government|parliament|sejm|institution|minister|urzad/i;

export function sourceGroupOf(source: Source): SourceGroup {
  if (source.portal_group) return source.portal_group;
  if (IMPORTANT_SOURCE_NAMES.test(source.name) || /top|major|featured/i.test(source.source_type)) return "top";
  if (PUBLIC_SOURCE_TYPES.test(source.source_type) || /sejm|minister|urz[ąa]d|gov\.pl|główny urząd/i.test(source.name)) return "publiczne";
  return "media";
}

export function groupSources(sources: Source[]): Record<SourceGroup, Source[]> {
  const groups: Record<SourceGroup, Source[]> = { top: [], media: [], publiczne: [] };
  for (const source of sources) groups[sourceGroupOf(source)].push(source);
  return groups;
}

/** Tylko źródła, z których faktycznie pobieramy materiały — kandydaci (np. media czekające na zgodę) nie mają treści. */
export function activeSources(sources: Source[]): Source[] {
  return sources.filter((source) => source.is_active !== false);
}

export const GROUP_EMPTY_HINT = "Media dołączą po udzieleniu zgód przez wydawców.";

export function parseSourceGroup(value: string | null | undefined): SourceGroup | null {
  return SOURCE_GROUPS.some((group) => group.value === value) ? (value as SourceGroup) : null;
}

export function sourceGroupLabel(group: SourceGroup): string {
  return SOURCE_GROUPS.find((item) => item.value === group)?.label ?? group;
}
