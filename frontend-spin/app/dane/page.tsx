import { InfoPage } from '@spin-clinic/ui/kit';
import { RSS_FEEDS, exportHref } from '@spin-clinic/ui';

export const metadata = {
  title: 'Dane i API · spin.clinic',
  description: 'Pobierz publiczne dane spin.clinic (CSV, JSON), subskrybuj kanały RSS i sprawdź, na jakich zasadach możesz je wykorzystać.',
  alternates: {
    canonical: '/dane',
    types: { 'application/rss+xml': RSS_FEEDS.map(feed => ({ url: feed.href, title: `spin.clinic: ${feed.label.toLowerCase()}` })) },
  },
};

const DATASETS = [
  { id: 'diagnozy', name: 'Diagnozy', what: 'opublikowane diagnozy wpisów: autor, klub, werdykt, siła spinu, techniki, liczba twierdzeń wg statusu, adresy', filters: 'q, camp, verdict, party, technique, account, intensity_min, intensity_max, date_from, date_to, sort', page: 'Baza diagnoz (/klinika/diagnozy)' },
  { id: 'osoby', name: 'Osoby publiczne', what: 'rejestr: funkcja, instytucja, klub, izba, liczba diagnoz, źródło funkcji', filters: 'q, role_category, status, party, chamber, sort', page: 'Rejestr osób (/osoby-publiczne)' },
  { id: 'zrodla', name: 'Źródła', what: 'katalog źródeł: adres, grupa, status aktywności i zgody', filters: 'q, status (active, pending)', page: 'Katalog źródeł (/zrodla)' },
  { id: 'wskazniki', name: 'Wskaźniki Kliniki', what: 'dzienne liczby wpisów przeczytanych, ocenionych wstępnie i zdiagnozowanych, osobno dla obu obozów', filters: 'brak', page: 'Dane i wykresy (/klinika/wskazniki)' },
] as const;

export default function DataPage() {
  return <InfoPage eyebrow="DANE" title="Dane i API" lead="Publiczne dane spin.clinic do pobrania: tabele w CSV i JSON oraz kanały RSS. To te same informacje, które widać na stronie, bez żadnych danych wewnętrznych.">
    <section id="eksport"><h2>Pobieranie danych</h2>
      <p>Przyciski „Pobierz dane” na listach (diagnozy, osoby, źródła, wskaźniki) zapisują tabelę z tymi filtrami, które masz aktywne. Możesz też użyć adresów bezpośrednio: dopisz filtry jako parametry adresu, tak samo jak na stronie.</p>
      <div className="sc-table-scroll"><table>
        <thead><tr><th scope="col">Zbiór</th><th scope="col">Zawartość</th><th scope="col">Filtry (parametry)</th><th scope="col">Pliki</th></tr></thead>
        <tbody>{DATASETS.map(set => <tr key={set.id}>
          <th scope="row">{set.name}</th><td>{set.what}. Filtry jak na stronie: {set.page}.</td><td>{set.filters}</td>
          <td><a href={exportHref(set.id, 'csv')}>CSV</a> · <a href={exportHref(set.id, 'json')}>JSON</a></td>
        </tr>)}</tbody>
      </table></div>
    </section>
    <section id="format"><h2>Format plików</h2>
      <ul>
        <li><strong>CSV:</strong> kodowanie UTF-8 ze znacznikiem BOM (polskie znaki w Excelu), separator średnik, nagłówki po polsku, stałe kolumny. Komórki zaczynające się od znaku formuły dostają na początku apostrof.</li>
        <li><strong>JSON:</strong> obiekt z polami <code>zbior</code>, <code>wygenerowano</code>, <code>liczba</code>, <code>filtry</code>, <code>licencja</code>, <code>kolumny</code> (opis kolumn) i <code>dane</code> (lista rekordów).</li>
        <li><strong>Data pliku:</strong> nazwa pliku zawiera dzień pobrania. Dane są migawką z chwili pobrania.</li>
      </ul>
    </section>
    <section id="zakres"><h2>Co udostępniamy, a czego nie</h2>
      <p>Eksport zawiera wyłącznie dane publiczne: opublikowane diagnozy (analiza AI, nie rozstrzygnięcie redakcji), jawne rekordy rejestru osób i katalogu źródeł oraz zbiorcze liczby. Zamiast treści wpisów z X podajemy ich adresy. Nie ma w nim danych czytelników, kont ani zgłoszeń, ani niczego z kolejek wewnętrznych serwisu.</p>
    </section>
    <section id="limity"><h2>Limity</h2>
      <p>Jedna paczka zawiera do 5000 wierszy, a pobrań jest do 30 na godzinę z jednego adresu (po zalogowaniu: 60). Po przekroczeniu limitu serwis odpowie komunikatem o zbyt wielu zapytaniach; spróbuj ponownie później.</p>
    </section>
    <section id="rss"><h2>Kanały RSS</h2>
      <p>Każdy wpis kanału ma tytuł, link do strony, datę publikacji i krótki opis z oznaczeniem „Analiza AI”.</p>
      <ul>{RSS_FEEDS.map(feed => <li key={feed.name}><a href={feed.href}>{feed.label}</a> <small>({feed.href})</small></li>)}</ul>
    </section>
    <section id="licencja"><h2>Warunki ponownego użycia</h2>
      <p>Warunki licencji na dane i analizy ustalimy przed wersją końcową serwisu; do tego czasu obowiązują zasady dozwolonego cytatu z <a href="/zasady-korzystania#reklamacje">Zasad korzystania</a>. Cytując, podaj spin.clinic jako źródło, adres strony i datę pobrania. Treści źródłowe (wpisy, artykuły, wywiady) pozostają własnością ich autorów i wydawców.</p>
    </section>
  </InfoPage>;
}
