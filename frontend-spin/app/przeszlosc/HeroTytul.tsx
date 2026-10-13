import './hero-tytul.css';

/**
 * Tytuł strony głównej przeszłość.today z mikroanimacją słów (seria 2, zlecenie właściciela: "żeby to ciut ciut żyło").
 * Trzy różne, bardzo delikatne gesty, jeden naraz: "Kto" - podkreślenie rysowane od lewej, "co" - znak zapytania unosi się
 * i gaśnie, "kiedy" - echo słowa przesuwa się w prawo i znika. Pętla co 14 s, start po 1,4 s, tytuł widoczny od razu (LCP).
 * Ozdoby to pseudoelementy z pustym tekstem alternatywnym (`content: "?" / ""`) - DOM i czytnik mają zwykłe zdanie.
 * Tylko transform / opacity, bez zmiany rozmiaru nagłówka; prefers-reduced-motion = brak animacji.
 */
export function HeroTytul() {
  return <>
    <span className="pt-hw" data-w="kto">Kto</span>, <span className="pt-hw" data-w="co">co</span> i&nbsp;<span className="pt-hw" data-w="kiedy" data-echo="kiedy">kiedy</span> w&nbsp;jednym temacie
  </>;
}
