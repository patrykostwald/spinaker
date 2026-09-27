/**
 * Przykładowa autoryzowana nitka kontekstowa: poziomy pasek boxów (O nas i zaproszenie dla dziennikarzy na głównej).
 * Box otwierający (materiał do wypromowania) → do 14 boxów kontekstu, razem najwyżej 15. Przykład jest wymyślony.
 */
export const EXAMPLE_THREAD = {
  title: 'Przetarg w spółce miejskiej — cała historia w pięciu materiałach',
  description: 'Od wywiadu z byłym dyrektorem do dokumentów przetargu: co wiedziano, kiedy i kto ostrzegał.',
  boxes: [
    { kind: 'Wywiad', source: 'Państwa redakcja', title: 'Rozmowa z byłym dyrektorem spółki: „Ostrzegałem zarząd pół roku wcześniej”', date: '12.09', opening: true },
    { kind: 'Komunikat', source: 'Prokuratura Krajowa', title: 'Zatrzymanie trzech osób w sprawie przetargu', date: '14.09' },
    { kind: 'Artykuł', source: 'inna redakcja', title: 'Kim są zatrzymani i co łączy ich ze spółką', date: '15.09' },
    { kind: 'Film', source: 'kanał YouTube', title: 'Nagranie z posiedzenia rady nadzorczej', date: '16.09' },
    { kind: 'Śledztwo', source: 'Państwa redakcja', title: 'Jak rozpisano przetarg — dokumenty krok po kroku', date: '18.09' },
  ],
};

export function ContextThreadStrip() {
  return (
    <figure className="sc-ctx__strip-wrap">
      <ol className="sc-ctx__strip" aria-label="Przykładowa nitka kontekstowa">
        {EXAMPLE_THREAD.boxes.map((box, index) => (
          <li key={box.title} className="sc-ctx__box" data-opening={box.opening || undefined}>
            {box.opening ? <span className="sc-ctx__badge">Box otwierający</span> : <span className="sc-ctx__num">{index + 1}</span>}
            <span className="sc-ctx__thumb" aria-hidden="true" />
            <span className="sc-ctx__kind">{box.kind}</span>
            <strong>{box.title}</strong>
            <small>{box.source} · {box.date}</small>
          </li>
        ))}
        <li className="sc-ctx__more" aria-label="Można dodać więcej boxów">+ do 15 boxów</li>
      </ol>
      <figcaption className="sc-ctx__caption">Przykład wymyślony — pokazuje zasadę, nie prawdziwą sprawę.</figcaption>
    </figure>
  );
}

/** Ta sama nitka jako wątek na X: 1/N — tytuł i opis z linkiem do nitki; dalej po jednym wpisie na box z kartą oryginału. */
export function ContextThreadXPreview({ limit = 3 }: { limit?: number }) {
  const total = EXAMPLE_THREAD.boxes.length + 1;
  return (
    <ol className="sc-xmock" aria-label="Ta sama nitka jako wątek na X">
      <li>
        <span className="sc-xmock__n">1/{total}</span>
        <p><strong>{EXAMPLE_THREAD.title}</strong></p>
        <p>{EXAMPLE_THREAD.description}</p>
        <span className="sc-xmock__card">spin.clinic · nitka kontekstowa</span>
      </li>
      {EXAMPLE_THREAD.boxes.slice(0, limit).map((box, index) => (
        <li key={box.title}>
          <span className="sc-xmock__n">{index + 2}/{total}</span>
          <p><strong>{box.kind} · {box.source}</strong> — {box.title}</p>
          <span className="sc-xmock__card">karta ze zdjęciem · strona źródła</span>
        </li>
      ))}
      {EXAMPLE_THREAD.boxes.length > limit && <li className="sc-xmock__more">… i kolejne boxy jako odpowiedzi</li>}
    </ol>
  );
}
