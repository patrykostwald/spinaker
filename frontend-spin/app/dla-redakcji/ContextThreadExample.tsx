/**
 * Ilustracja dla redakcji (aktualizacja 5.10): autoryzowana spinka w obecnym wyglądzie - nagłówek (tytuł i opis),
 * boksy połączone spinkami z typem połączenia; czytelnicy oceniają połączenia. Przykład wymyślony, pokazuje zasadę.
 */
const BOXES: [string, string, string][] = [
  ['Wywiad', 'Rozmowa z byłym dyrektorem spółki: „Ostrzegałem zarząd pół roku wcześniej”', 'Państwa redakcja · 12.09'],
  ['Komunikat', 'Zatrzymanie trzech osób w sprawie przetargu', 'Prokuratura Krajowa · 14.09'],
  ['Dokument', 'Uchwała zarządu z marca: zmiana warunków przetargu', 'KRS, akta spółki · 03.03'],
];
const LINKS = ['wynika z', 'bo'];

const RECIPE = [
  ['Boks otwierający', 'Państwa materiał, który chcą Państwo wypromować: artykuł, wywiad, film, śledztwo.'],
  ['Do 14 boksów kontekstu', 'razem najwyżej 15: komunikaty, dokumenty, artykuły innych redakcji, filmy. Z naszej Bazy albo po linku.'],
  ['Połączenia z uzasadnieniem', 'między boksami autor wybiera typ (wynika z, bo, ale, czy na pewno?, przeczy) i jednym zdaniem pisze, dlaczego.'],
  ['Czytelnicy oceniają', 'każde połączenie: ✓ zgadzam się, ? wątpię, ✕ nie zgadzam się. Kolor spinki pokazuje, jak oceniono rozumowanie.'],
  ['Tytuł i opis', 'tytuł w dwóch wierszach, pod nim opis całej spinki; po kliknięciu boksu lub połączenia w tym miejscu pojawia się jego wyjaśnienie.'],
  ['Każdy boks ze źródłem', 'nazwa źródła, data i link do oryginału - czytelnik trafia do Państwa strony. Spinkę podpisuje autor i redakcja.'],
];

export function ContextThreadExample() {
  return (
    <div id="trop-przyklad" className="sc-ctx sc-ctx2">
      <h3>Autoryzowana spinka - jak wygląda</h3>
      <p className="sc-ctx__lead">
        Pierwszy boks to materiał, który chcą Państwo wypromować. Za nim są boksy, które dają mu kontekst, połączone spinkami:
        każda mówi, dlaczego następny materiał wynika z poprzedniego. Czytelnik w kilka sekund widzi całą historię i ocenia rozumowanie.
      </p>
      <figure className="sc-ctx2__demo" aria-label="Przykład spinki">
        <header>
          <p className="sc-ctx2__title"><span>Państwa redakcja:</span> Przetarg, który zarząd znał wcześniej</p>
          <p className="sc-ctx2__desc">Wywiad z byłym dyrektorem zestawiony z komunikatem prokuratury i uchwałą zarządu.</p>
        </header>
        <ol className="sc-ctx2__chain">
          {BOXES.flatMap(([kind, title, source], index) => [
            ...(index > 0 ? [<li key={`l${index}`} className="sc-ctx2__link" aria-label={`Połączenie: ${LINKS[index - 1]}`}><b>{LINKS[index - 1]}</b><i /></li>] : []),
            <li key={title} className="sc-ctx2__box" data-first={index === 0 || undefined}>
              <span className="sc-ctx2__kind">{index === 0 ? `${kind} · otwiera` : kind}</span>
              <strong>{title}</strong>
              <small>{source}</small>
            </li>])}
        </ol>
        <figcaption>Przykład wymyślony - pokazuje zasadę, nie prawdziwą sprawę.</figcaption>
      </figure>
      <dl className="sc-ctx__recipe">
        {RECIPE.map(([term, text]) => <div key={term}><dt>{term}</dt><dd>{text}</dd></div>)}
      </dl>
    </div>
  );
}
