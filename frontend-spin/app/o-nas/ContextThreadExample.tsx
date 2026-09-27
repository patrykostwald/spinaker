/**
 * Ilustracja dla redakcji: autoryzowana nitka kontekstowa to poziomy pasek boxów.
 * Box otwierający (materiał, który redakcja chce wypromować) → 1–14 boxów kontekstu, najwyżej 15 razem.
 * Przykład jest wymyślony — pokazuje zasadę, nie prawdziwą sprawę.
 */
const BOXES = [
  { kind: 'Wywiad', source: 'Państwa redakcja', title: 'Rozmowa z byłym dyrektorem spółki: „Ostrzegałem zarząd pół roku wcześniej”', date: '12.09', opening: true },
  { kind: 'Komunikat', source: 'Prokuratura Krajowa', title: 'Zatrzymanie trzech osób w sprawie przetargu', date: '14.09' },
  { kind: 'Artykuł', source: 'inna redakcja', title: 'Kim są zatrzymani i co łączy ich ze spółką', date: '15.09' },
  { kind: 'Film', source: 'kanał YouTube', title: 'Nagranie z posiedzenia rady nadzorczej', date: '16.09' },
  { kind: 'Śledztwo', source: 'Państwa redakcja', title: 'Jak rozpisano przetarg — dokumenty krok po kroku', date: '18.09' },
];

const RECIPE = [
  ['Box otwierający', 'Państwa materiał, który chcą Państwo wypromować: artykuł, wywiad, film, śledztwo.'],
  ['Do 14 boxów kontekstu', 'razem najwyżej 15. Dowolne materiały: komunikaty, dokumenty, artykuły innych redakcji, filmy.'],
  ['Z Bazy albo po linku', 'box wybierają Państwo z naszej Bazy albo tworzą sami — link, tytuł, zdjęcie; nowy box trafia do Bazy.'],
  ['Kolejność', 'ustala autor — tak, by czytelnik przeszedł całą historię od materiału otwierającego.'],
  ['Każdy box ze źródłem', 'nazwa źródła, data i link do oryginału — czytelnik trafia do Państwa strony.'],
  ['Podpis', 'autor i redakcja przy nitce — nitka jest Państwa.'],
];

export function ContextThreadExample() {
  return (
    <div id="nitka-kontekstowa" className="sc-ctx">
      <h3 className="sc-onas-subtitle">Autoryzowana nitka kontekstowa — jak wygląda</h3>
      <p className="sc-ctx__lead">
        Poziomy pasek boxów. Pierwszy to materiał, który chcą Państwo wypromować; za nim — boxy, które dają mu kontekst. Czytelnik przewija w bok
        i w kilka sekund widzi całą historię, a każdy box prowadzi do oryginału.
      </p>
      <figure className="sc-ctx__strip-wrap">
        <ol className="sc-ctx__strip" aria-label="Przykładowa nitka kontekstowa">
          {BOXES.map((box, index) => (
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
        <figcaption className="sc-ctx__caption">
          Przykład wymyślony — pokazuje zasadę, nie prawdziwą sprawę. To nie jest nitka newsowa (kolejne wiadomości o tym samym) — takie paski
          układamy automatycznie.
        </figcaption>
      </figure>
      <dl className="sc-ctx__recipe">
        {RECIPE.map(([term, text]) => <div key={term}><dt>{term}</dt><dd>{text}</dd></div>)}
      </dl>
    </div>
  );
}
