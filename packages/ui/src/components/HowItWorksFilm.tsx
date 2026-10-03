/**
 * Animacja „Jak działa spin.clinic” (ok. 70 s, 8 scen): box → oś czasu → nitka newsowa → nitka kontekstowa → Klinika
 * → faza II i III. Plik statyczny w `frontend-spin/public/jak-dziala/`; osadzamy go na „O nas” (29.09.2026).
 */
export function HowItWorksFilm({ title, lang = "pl" }: { title?: string; lang?: "pl" | "en" }) {
  const english = lang === "en";
  return (
    <figure id="film" className="sc-film">
      <iframe className="sc-film__frame" src="/jak-dziala/index.html" lang="pl" title={title ?? (english ? "How spin.clinic works - animation, about 70 seconds (in Polish)" : "Jak działa spin.clinic - animacja, ok. 70 s")} loading="lazy" />
      <figcaption className="sc-film__caption">
        {english ? "The animation shows how the service works: cards, the timeline, threads, the Clinic and future phases. The material and people are illustrative. (in Polish)" : "Animacja pokazuje, jak działa serwis: box, oś czasu, tropy, Klinika spinu i kolejne fazy. Materiały i osoby są przykładowe."}{" "}
        <a href="/jak-dziala/index.html" target="_blank" rel="noopener">{english ? "Open full screen (in Polish) ↗" : "Otwórz na pełnym ekranie ↗"}</a>
      </figcaption>
    </figure>
  );
}
