export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function formatDatePl(iso: string | null): string {
  if (!iso || iso === 'undated' || iso === 'unknown') return 'Data publikacji nieustalona';
  return new Intl.DateTimeFormat("pl-PL", {
    timeZone: "Europe/Warsaw",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(iso));
}

export function formatDateTimePl(iso: string | null, precision?: string): string {
  if (precision === 'day') return formatDatePl(iso);
  if (!iso || iso === 'undated' || iso === 'unknown') return 'Data publikacji nieustalona';
  return new Intl.DateTimeFormat("pl-PL", {
    timeZone: "Europe/Warsaw",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function categoryLabel(category: string): string {
  const map: Record<string, string> = {
    voting: "Głosowanie Sejmu",
    legislation: "Akt prawny / obwieszczenie",
    parliamentary_print: "Druk sejmowy",
    article: "Artykuł",
    interview: "Wywiad",
    podcast: "Podcast",
    document: "Dokument urzędowy",
    reportage: "Reportaż",
    statement: "Komunikat / oświadczenie",
    mention: "Wzmianka",
    sponsored: "Artykuł sponsorowany",
    advertisement: "Reklama",
    video: "Film",
    other: "Inne / do sklasyfikowania",
    tweet: "Tweet",
    factcheck: "Fact-check",
    context: "Kontekst",
    opinion: "Opinia",
  };
  return map[category] ?? category;
}
