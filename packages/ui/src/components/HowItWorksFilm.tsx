/**
 * Animacja „Jak działa spin.clinic” (ok. 70 s, 8 scen): box → oś czasu → nitka newsowa → nitka kontekstowa → Klinika
 * → faza II i III. Plik statyczny w `frontend-spin/public/jak-dziala/`; osadzamy go na „O nas” (29.09.2026).
 */
export function HowItWorksFilm({ title = "Jak działa spin.clinic — animacja, ok. 70 s" }: { title?: string }) {
  return (
    <figure id="film" className="sc-film">
      <iframe className="sc-film__frame" src="/jak-dziala/index.html" title={title} loading="lazy" />
      <figcaption className="sc-film__caption">
        Animacja pokazuje, jak działa serwis: box, oś czasu, nitki, Klinika spinu i kolejne fazy. Materiały i osoby są przykładowe.{" "}
        <a href="/jak-dziala/index.html" target="_blank" rel="noopener">Otwórz na pełnym ekranie ↗</a>
      </figcaption>
    </figure>
  );
}
