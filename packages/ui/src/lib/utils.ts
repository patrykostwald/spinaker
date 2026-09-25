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

export function formatTimePl(iso: string | null): string {
  if (!iso) return '';
  return new Intl.DateTimeFormat("pl-PL", { timeZone: "Europe/Warsaw", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

export function formatShortDatePl(iso: string | null): string {
  if (!iso) return 'brak daty';
  return new Intl.DateTimeFormat("pl-PL", { timeZone: "Europe/Warsaw", day: "2-digit", month: "2-digit", year: "2-digit" }).format(new Date(iso));
}

export const MATERIAL_TYPE_LABELS = ['ARTYKUŁ', 'WYWIAD', 'REPORTAŻ', 'ŚLEDZTWO', 'DOKUMENT URZĘDOWY', 'REKLAMA', 'FILM'] as const;

export function materialTypeLabel(category: string): string {
  const map: Record<string, string> = {
    article: 'ARTYKUŁ', mention: 'ARTYKUŁ', context: 'ARTYKUŁ', opinion: 'ARTYKUŁ', other: 'ARTYKUŁ', tweet: 'ARTYKUŁ',
    interview: 'WYWIAD', podcast: 'WYWIAD',
    reportage: 'REPORTAŻ',
    factcheck: 'ŚLEDZTWO',
    document: 'DOKUMENT URZĘDOWY', voting: 'DOKUMENT URZĘDOWY', legislation: 'DOKUMENT URZĘDOWY', parliamentary_print: 'DOKUMENT URZĘDOWY', statement: 'DOKUMENT URZĘDOWY',
    sponsored: 'REKLAMA', advertisement: 'REKLAMA',
    video: 'FILM',
  };
  return map[category] ?? 'ARTYKUŁ';
}

/* ——— Czytelniejsze boxy (25.09): krótka etykieta, rodzaj materiału, nazwa źródła, inicjały, czas względny ——— */

/** Krótka, jednowierszowa etykieta kategorii (pełna — `categoryLabel`, np. w podpowiedzi). */
export function shortCategoryLabel(category: string): string {
  const map: Record<string, string> = {
    voting: "Głosowanie", legislation: "Akt prawny", parliamentary_print: "Druk sejmowy", article: "Artykuł",
    interview: "Wywiad", podcast: "Podcast", document: "Dokument", reportage: "Reportaż", statement: "Komunikat",
    mention: "Wzmianka", sponsored: "Sponsorowane", advertisement: "Reklama", video: "Film", other: "Inne",
    tweet: "Wpis", factcheck: "Fact-check", context: "Kontekst", opinion: "Opinia",
  };
  return map[category] ?? categoryLabel(category);
}

/** Rodzina materiału — kolor kropki i tła zaślepki (CSS `data-kind`). */
export function materialKind(category: string): "official" | "article" | "talk" | "video" | "report" | "check" | "ad" {
  if (["document", "voting", "legislation", "parliamentary_print", "statement"].includes(category)) return "official";
  if (["interview", "podcast"].includes(category)) return "talk";
  if (category === "video") return "video";
  if (category === "reportage") return "report";
  if (category === "factcheck") return "check";
  if (["sponsored", "advertisement"].includes(category)) return "ad";
  return "article";
}

const SOURCE_NAMES: Record<string, string> = {
  "api.sejm.gov.pl/eli": "Sejm RP · akty prawne",
  "api.sejm.gov.pl/sejm": "Sejm RP",
  "ipn.gov.pl": "IPN",
  "knf.gov.pl": "KNF",
  "abw.gov.pl": "ABW",
  "trybunal.gov.pl": "Trybunał Konstytucyjny",
  "geoportal.gov.pl": "Geoportal",
  "wios.warszawa.pl": "WIOŚ Warszawa",
  "gios.gov.pl": "GIOŚ",
  "dane.gov.pl": "dane.gov.pl",
  "stat.gov.pl": "GUS",
  "pk.gov.pl": "Prokuratura Krajowa",
  "nbp.pl": "NBP",
  "pap.pl": "PAP",
};

function titleCaseCity(slug: string): string {
  const known: Record<string, string> = { torun: "Toruń", czestochowa: "Częstochowa", olsztyn: "Olsztyn", radom: "Radom", krakow: "Kraków", lodz: "Łódź", poznan: "Poznań", gdansk: "Gdańsk", wroclaw: "Wrocław", szczecin: "Szczecin", warszawa: "Warszawa", katowice: "Katowice", lublin: "Lublin", bialystok: "Białystok", kielce: "Kielce", rzeszow: "Rzeszów", opole: "Opole", bydgoszcz: "Bydgoszcz" };
  return known[slug] ?? slug.charAt(0).toUpperCase() + slug.slice(1);
}

/** Nazwa źródła dla czytelnika: „bip.torun.pl” → „BIP Toruń”, znane domeny → skróty instytucji. */
export function sourceDisplayName(name: string): string {
  const key = name.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/$/, "");
  if (SOURCE_NAMES[key]) return SOURCE_NAMES[key];
  const bip = key.match(/^bip\.([a-z-]+)\.(pl|eu|gov\.pl)$/);
  if (bip) return `BIP ${titleCaseCity(bip[1])}`;
  return name;
}

/** Inicjały do zaślepki: skrót z wielkich liter (IPN), pierwsze litery słów (URE) albo początek domeny. */
export function sourceInitials(displayName: string): string {
  const clean = displayName.replace(/[·•|]/g, " ").trim();
  const acronym = clean.match(/^[A-ZĄĆĘŁŃÓŚŹŻ]{2,5}\b/);
  if (acronym) return acronym[0];
  const words = clean.split(/\s+/).filter((word) => /^[A-ZĄĆĘŁŃÓŚŹŻ]/.test(word));
  if (words.length >= 2) return words.slice(0, 4).map((word) => word[0]).join("");
  const domain = clean.replace(/^www\./i, "").split(/[./\s]/)[0] ?? clean;
  return domain.slice(0, 3).toUpperCase();
}

/** „teraz”, „15 min temu”, „3 godz. temu”, „wczoraj, 14:20”, dalej data krótka. */
export function relativeTimePl(iso: string | null, now: number = Date.now()): string {
  if (!iso) return "";
  const time = new Date(iso).getTime();
  if (!Number.isFinite(time)) return "";
  const minutes = Math.round((now - time) / 60_000);
  if (minutes < 0) return formatTimePl(iso);
  if (minutes < 2) return "teraz";
  if (minutes < 60) return `${minutes} min temu`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} godz. temu`;
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (new Date(time).toDateString() === yesterday.toDateString()) return `wczoraj, ${formatTimePl(iso)}`;
  return formatShortDatePl(iso);
}
