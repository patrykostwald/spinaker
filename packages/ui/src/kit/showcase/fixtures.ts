/**
 * Fikcyjne dane demonstracyjne biblioteki UI.
 * Wszystkie osoby, podmioty, źródła, tytuły, daty i adresy są zmyślone.
 * Plik nie wysyła żadnych żądań — domena `przyklad.invalid` celowo nie istnieje.
 *
 * Zasady (docs/FRONTEND_MVP_DIRECTION.md): tytuły opisują UKŁAD, nie wydarzenia;
 * żadnych nazwisk, instytucji ani prawdopodobnych nagłówków. Identyfikatory są ujemne,
 * żeby nigdy nie pokryły się z prawdziwym Article. Obrazy to inline SVG ze słowem DEMO.
 */

import type { Article, Source } from "../../types";

export const FIXTURE_SOURCES: Source[] = [
  { id: -1, name: "Dziennik Przykładowy", url: "https://dziennik.przyklad.invalid", source_type: "rss", is_active: true },
  { id: -2, name: "Serwis Testowy", url: "https://serwis.przyklad.invalid", source_type: "rss", is_active: true },
  { id: -3, name: "Agencja Poglądowa", url: "https://agencja.przyklad.invalid", source_type: "rss", is_active: true },
  { id: -4, name: "Biuletyn Makiety Regionalnej i Przykładowej", url: "https://biuletyn.przyklad.invalid", source_type: "official", is_active: true },
  { id: -5, name: "Instytut Przykładów", url: "https://instytut.przyklad.invalid", source_type: "official", is_active: true },
];

/** Abstrakcyjna plansza-zaślepka: gradient + napis DEMO. Działa w next/image dzięki images.unoptimized. */
export function demoImage(seed: number, ratio: "16:9" | "4:3" | "1:1" = "16:9"): string {
  const [w, h] = ratio === "16:9" ? [640, 360] : ratio === "4:3" ? [640, 480] : [480, 480];
  const hue = (seed * 47) % 360;
  const hue2 = (hue + 60) % 360;
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='${w}' height='${h}' viewBox='0 0 ${w} ${h}'>
<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='hsl(${hue} 40% 38%)'/><stop offset='1' stop-color='hsl(${hue2} 45% 22%)'/></linearGradient></defs>
<rect width='${w}' height='${h}' fill='url(#g)'/>
<circle cx='${w * 0.72}' cy='${h * 0.36}' r='${h * 0.22}' fill='hsl(${hue2} 50% 55% / 0.35)'/>
<text x='${w / 2}' y='${h / 2 + 14}' text-anchor='middle' font-family='sans-serif' font-size='${Math.round(h * 0.16)}' font-weight='700' fill='rgba(255,255,255,0.55)' letter-spacing='6'>DEMO</text>
</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

let counter = 0;

/** Pełny Article z wypełnionymi polami obowiązkowymi; nadpisz, co potrzeba. */
export function makeArticle(overrides: Partial<Article> = {}): Article {
  counter += 1;
  const id = overrides.id ?? -(1000 + counter);
  const source = overrides.source ?? FIXTURE_SOURCES[Math.abs(id) % FIXTURE_SOURCES.length];
  const day = 1 + (Math.abs(id) % 27);
  const hour = 6 + (Math.abs(id) % 15);
  return {
    id,
    title: "Tytuł testowy mieszczący się w dwóch wierszach karty",
    url: `https://${source.url.replace("https://", "")}/material/${Math.abs(id)}`,
    published_date: `2026-09-${String(day).padStart(2, "0")}T${String(hour).padStart(2, "0")}:${String((Math.abs(id) * 7) % 60).padStart(2, "0")}:00+02:00`,
    date_precision: "time",
    category: "article",
    image_url: demoImage(Math.abs(id)),
    discovered_at: null,
    ingestion_method: "demo",
    category_reviewed: true,
    evidence_note: "",
    author: "",
    description:
      "Opis testowy sprawdzający zawijanie akapitu w karcie średniej i dużej. Zawiera polskie znaki: ąćęłńóśźż ĄĆĘŁŃÓŚŹŻ, żeby od razu było widać, czy Montserrat obsługuje latin-ext.",
    source,
    ...overrides,
  };
}

/** Sześć stanów danych z planu, użyte w matrycy karty. */
export const FIXTURE_STATES: { key: string; label: string; article: Article }[] = [
  { key: "normal", label: "Zwykły", article: makeArticle({ id: -1 }) },
  { key: "no-image", label: "Bez miniatury", article: makeArticle({ id: -2, image_url: "", category: "document" }) },
  { key: "no-date", label: "Bez daty (null)", article: makeArticle({ id: -3, published_date: null }) },
  { key: "undated", label: "Data nieustalona", article: makeArticle({ id: -4, published_date: "undated", date_precision: "day" }) },
  {
    key: "long-title",
    label: "Bardzo długi tytuł",
    article: makeArticle({
      id: -5,
      title:
        "Bardzo długi tytuł testowy sprawdzający zawijanie do trzech wierszy oraz przycięcie wielokropkiem na samym końcu, z wyrazami: sprawiedliwości, parlamentarny, Rzeczpospolita",
    }),
  },
  {
    key: "long-source",
    label: "Bardzo długa nazwa źródła",
    article: makeArticle({ id: -6, source: FIXTURE_SOURCES[3], author: "Autor Przykładowy-Testowy" }),
  },
];

const CATEGORY_CYCLE = ["article", "interview", "reportage", "document", "voting", "video", "statement", "factcheck"];
const TITLE_CYCLE = [
  "Tytuł testowy mieszczący się w jednej linii",
  "Dłuższy tytuł testowy, który sprawdza zawijanie do dwóch wierszy w karcie kompaktowej",
  "Bardzo długi tytuł testowy sprawdzający zawijanie do trzech wierszy oraz przycięcie na końcu",
  "Materiał testowy ze znakami ąćęłńóśźż w tytule",
  "Krótki tytuł",
  "Tytuł ze słowem Rzeczpospolita i słowem sprawiedliwości do testu przenoszenia",
];

/** Deterministyczny zestaw n materiałów — do lent, siatek i pomiarów wydajności (makeArticles(240)). */
export function makeArticles(n: number, seed = 1): Article[] {
  return Array.from({ length: n }, (_, i) => {
    const k = seed * 1000 + i;
    return makeArticle({
      id: -(2000 + k),
      title: TITLE_CYCLE[k % TITLE_CYCLE.length],
      category: CATEGORY_CYCLE[k % CATEGORY_CYCLE.length],
      image_url: k % 7 === 3 ? "" : demoImage(k),
      published_date: k % 11 === 5 ? null : undefined,
      source: FIXTURE_SOURCES[k % FIXTURE_SOURCES.length],
    });
  });
}

/** 24 materiały z długimi polskimi ciągami — domyślny zestaw sekcji witryny. */
export const FIXTURE_ARTICLES: Article[] = makeArticles(24, 3);

/** Pięć polos po 8 kart — do przeciągania polos i karuzel. */
export const FIXTURE_STRIPS: { id: string; title: string; articles: Article[] }[] = [
  { id: "najnowsze", title: "Najnowsze materiały", articles: makeArticles(8, 11) },
  { id: "polska", title: "Polska", articles: makeArticles(8, 12) },
  { id: "gospodarka", title: "Gospodarka", articles: makeArticles(8, 13) },
  { id: "prawo", title: "Prawo i instytucje", articles: makeArticles(8, 14) },
  { id: "nauka", title: "Nauka i zdrowie", articles: makeArticles(8, 15) },
];

/** Dłuższy tekst polski do wzorników typografii. */
export const POLISH_SPECIMEN =
  "Zażółć gęślą jaźń. Pchnąć w tę łódź jeża lub ośm skrzyń fig. Rzeczpospolita, sprawiedliwości, parlamentarny, województwo, przedsiębiorczość.";
export const POLISH_LONG_WORDS = "Rzeczpospolita · sprawiedliwości · parlamentarny · przedsiębiorczość · Konstantynopolitańczykowianeczka";
