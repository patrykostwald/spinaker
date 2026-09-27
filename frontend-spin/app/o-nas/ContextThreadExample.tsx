/**
 * Ilustracja dla redakcji: czym nitka kontekstowa różni się od nitki newsowej.
 * Przykład jest wymyślony — pokazuje zasadę, nie prawdziwą sprawę.
 */
const NEWS = [
  { time: '09:00', title: 'Sejm przyjął ustawę' },
  { time: '11:30', title: 'Opozycja krytykuje ustawę' },
  { time: '14:00', title: 'Prezydent zapowiada decyzję' },
];

const CONTEXT = [
  { kind: 'confirms', label: 'Potwierdza', source: 'Dane GUS', note: 'Stopa bezrobocia rzeczywiście spadła z 10% do 5%.' },
  { kind: 'completes', label: 'Dopełnia', source: 'Artykuł Państwa redakcji', note: 'Spadek zaczął się dwa lata przed zmianą rządu.' },
  { kind: 'challenges', label: 'Podważa', source: 'Raport Eurostatu', note: 'W tym samym czasie bezrobocie spadało w całej Unii.' },
] as const;

const RECIPE = [
  ['Punkt wyjścia', 'jedna konkretna wypowiedź, teza albo liczba — z wpisu, wywiadu, konferencji.'],
  ['3–10 materiałów', 'Państwa artykuły, ale też dokumenty, dane i materiały innych redakcji — każdy z linkiem do oryginału.'],
  ['Jedno zdanie przy każdym', 'co ten materiał wnosi: potwierdza, dopełnia albo podważa punkt wyjścia.'],
  ['Kolejność', 'według daty publikacji — czytelnik widzi, co było wcześniej, a co później.'],
  ['Bez wyroku', 'nitka pokazuje kontekst; ocenę zostawia czytelnikowi.'],
  ['Podpis', 'autor i redakcja przy nitce — nitka jest Państwa.'],
];

export function ContextThreadExample() {
  return (
    <div id="nitka-kontekstowa" className="sc-ctx">
      <h3 className="sc-onas-subtitle">Autoryzowana nitka kontekstowa — jak ją zbudować</h3>
      <div className="sc-ctx__compare">
        <figure className="sc-ctx__card sc-ctx__card--news">
          <figcaption><strong>Nitka newsowa</strong><span>tego nie potrzebujemy</span></figcaption>
          <ol className="sc-ctx__news">
            {NEWS.map(item => <li key={item.time}><time>{item.time}</time> {item.title}</li>)}
          </ol>
          <p className="sc-ctx__caption">Kolejne wiadomości o tym samym. To robią już nasze paski — automatycznie.</p>
        </figure>

        <figure className="sc-ctx__card sc-ctx__card--context">
          <figcaption><strong>Nitka kontekstowa</strong><span>o to prosimy</span></figcaption>
          <ol className="sc-ctx__chain">
            <li className="sc-ctx__start">
              <span className="sc-ctx__step">Punkt wyjścia</span>
              <q>Za naszych rządów bezrobocie spadło o połowę.</q>
              <small>wpis polityka</small>
            </li>
            {CONTEXT.map(item => (
              <li key={item.kind} className="sc-ctx__item" data-kind={item.kind}>
                <span className="sc-ctx__tag">{item.label}</span>
                <strong>{item.source}</strong>
                <span>{item.note}</span>
              </li>
            ))}
            <li className="sc-ctx__end">
              Czytelnik sam widzi: liczba jest prawdziwa, ale zasługa — przypisana. To jest kontekst, którego brakuje w samym wpisie.
            </li>
          </ol>
          <p className="sc-ctx__caption">Przykład wymyślony — pokazuje zasadę, nie prawdziwą sprawę.</p>
        </figure>
      </div>
      <dl className="sc-ctx__recipe">
        {RECIPE.map(([term, text]) => <div key={term}><dt>{term}</dt><dd>{text}</dd></div>)}
      </dl>
    </div>
  );
}
