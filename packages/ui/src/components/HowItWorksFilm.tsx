/**
 * Film „Jak działa spin.clinic” (ok. 60 s, właściciel 5.10.2026): „Jak działa przekaz” → spin.clinic, potem ścieżka czytelnika:
 * spinki, połączenia, ocena, komentarz, Klinika, dwa wywiady dnia, własna spinka. Plik statyczny w `frontend-spin/public/jak-dziala/`.
 */
export function HowItWorksFilm({ title, lang = "pl" }: { title?: string; lang?: "pl" | "en" }) {
  const english = lang === "en";
  return (
    <figure id="film" className="sc-film">
      <iframe className="sc-film__frame" src="/jak-dziala/index.html" lang="pl" title={title ?? (english ? "How spin.clinic works - animation, about 60 seconds (in Polish)" : "Jak działa spin.clinic - animacja, ok. 60 s")} loading="lazy" />
      <figcaption className="sc-film__caption">
        {english ? "A one-minute walk through the service: spinki, connections and ratings, comments, the Clinic and the interviews of the day. The material and people are illustrative. (in Polish)" : "Minuta po najważniejszych funkcjach: spinki, połączenia i oceny, komentarze, Klinika i wywiady dnia. Materiały i osoby są przykładowe."}{" "}
        <a href="/jak-dziala/index.html" target="_blank" rel="noopener">{english ? "Open full screen (in Polish) ↗" : "Otwórz na pełnym ekranie ↗"}</a>
      </figcaption>
    </figure>
  );
}
