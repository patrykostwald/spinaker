import { ContextThreadStrip } from '@spin-clinic/ui';

/**
 * Ilustracja dla redakcji: autoryzowana nitka kontekstowa to poziomy pasek boxów.
 * Box otwierający (materiał, który redakcja chce wypromować) → 1–14 boxów kontekstu, najwyżej 15 razem.
 * Przykład jest wymyślony — pokazuje zasadę, nie prawdziwą sprawę.
 */
const RECIPE = [
  ['Box otwierający', 'Państwa materiał, który chcą Państwo wypromować: artykuł, wywiad, film, śledztwo.'],
  ['Do 14 boxów kontekstu', 'razem najwyżej 15. Dowolne materiały: komunikaty, dokumenty, artykuły innych redakcji, filmy.'],
  ['Z Bazy albo po linku', 'box wybierają Państwo z naszej Bazy albo tworzą sami — link, tytuł, zdjęcie; nowy box trafia do Bazy.'],
  ['Kolejność', 'ustala autor — tak, by czytelnik przeszedł całą historię od materiału otwierającego.'],
  ['Każdy box ze źródłem', 'nazwa źródła, data i link do oryginału — czytelnik trafia do Państwa strony.'],
  ['Opis jak wpis na X', 'cały opis nitki mieści się w jednym wpisie na X (do 280 znaków) — łatwo ją udostępnić. Podpisuje autor i redakcja.'],
];

export function ContextThreadExample() {
  return (
    <div id="nitka-kontekstowa" className="sc-ctx">
      <h3>Autoryzowana nitka kontekstowa — jak wygląda</h3>
      <p className="sc-ctx__lead">
        Poziomy pasek boxów. Pierwszy to materiał, który chcą Państwo wypromować; za nim — boxy, które dają mu kontekst. Czytelnik przewija w bok
        i w kilka sekund widzi całą historię, a każdy box prowadzi do oryginału.
      </p>
      <ContextThreadStrip />
      <dl className="sc-ctx__recipe">
        {RECIPE.map(([term, text]) => <div key={term}><dt>{term}</dt><dd>{text}</dd></div>)}
      </dl>
    </div>
  );
}
