import Link from 'next/link';
import { Button, InfoPage } from '@spin-clinic/ui/kit';

export const metadata = { title: 'Wsparcie · spin.clinic' };
// Linki BUYCOFFEE_URL i PATRONITE_URL czytamy z .env.production przy każdym wejściu, nie przy budowaniu obrazu.
export const dynamic = 'force-dynamic';

function publicSupportUrl(value: string | undefined) {
  try {
    const url = new URL(value || '');
    return url.protocol === 'https:' ? url.toString() : '';
  } catch {
    return '';
  }
}

/** Koszty z pomiarów (diagnoza) i z konfiguracji (limit dzienny) — bez kwot, których nie znamy z faktur. */
const COSTS: Array<[string, string]> = [
  ['Diagnoza Dr. Spina', 'ok. 0,35 USD (ok. 1,30 zł) za jedną — model Claude z wyszukiwaniem w sieci. Przy 20 diagnozach dziennie to ok. 800 zł miesięcznie.'],
  ['Posty polityków', 'oficjalne, płatne API X — płacimy za każde pobranie.'],
  ['Strażnik i przekazy dnia', '0 zł — darmowe limity Groq i NVIDIA NIM.'],
  ['Serwer, baza, kopie zapasowe, domena', 'stały koszt miesięczny.'],
];

const GOALS: Array<[string, string]> = [
  ['Utrzymanie', 'Pełny miesiąc Kliniki: diagnozy, API X i serwer. Gdy wpłat jest mniej, zmniejszamy dzienną liczbę diagnoz; gdy więcej — sprawdzamy więcej wypowiedzi.'],
  ['Faza II', 'Konta czytelników, nitki kontekstowe z materiałów z Bazy i strażnica zmian, która pokaże, gdy źródło po publikacji zmieni albo usunie materiał.'],
  ['Własny serwer AI', 'Maszyna z kartą graficzną i otwarte modele, także polskie. Koszt jednej diagnozy spadnie prawie do zera, a Klinika uniezależni się od cen i regulaminów wielkich firm.'],
];

export default function SupportPage() {
  const buycoffee = publicSupportUrl(process.env.BUYCOFFEE_URL);
  const patronite = publicSupportUrl(process.env.PATRONITE_URL);
  const links = [
    buycoffee && { label: 'Postaw kawę na BuyCoffee', href: buycoffee },
    patronite && { label: 'Wspieraj co miesiąc na Patronite', href: patronite },
  ].filter(Boolean) as { label: string; href: string }[];

  return <InfoPage eyebrow="WSPARCIE" title="Politycy mają spin doktorów. My mamy spin.clinic." lead="spin.clinic to niezależny projekt, który pokazuje wiadomości ze źródłami i rozkłada przekazy polityków na czynniki pierwsze. Utrzymują go wyłącznie czytelnicy — bez reklam, sponsorów i partyjnych pieniędzy.">
    <section><h2>Kto za tym stoi</h2><p>Projekt buduje jedna osoba, która nie jest i nigdy nie była członkiem żadnej partii politycznej, redakcji ani organizacji politycznej. Nie reprezentuje żadnego obozu. Cały serwis powstaje przy wsparciu narzędzi sztucznej inteligencji — od kodu po analizę przekazów — i jest odpowiedzią na prostą nierówność: politycy mają zespoły od wizerunku, a obywatele zwykle nie mają nikogo. Operatorem serwisu jest iapply sp. z o.o. z Poznania.</p></section>
    <section><h2>Na co idą pieniądze</h2>
      <dl className="sc-support-costs">{COSTS.map(([name, text]) => <div key={name}><dt>{name}</dt><dd>{text}</dd></div>)}</dl>
      <p className="sc-support-note">Dziś pokrywamy te koszty sami. Jedna kawa za 10 zł to około 7 kolejnych diagnoz.</p>
    </section>
    <section><h2>Na co zbieramy</h2>
      <dl className="sc-support-costs">{GOALS.map(([name, text]) => <div key={name}><dt>{name}</dt><dd>{text}</dd></div>)}</dl>
      <p className="sc-support-note">Co dokładnie jest w każdej fazie, opisujemy w <Link href="/o-nas#fazy">O nas → Trzy fazy projektu</Link>.</p>
    </section>
    <section><h2>Wsparcie nie kupuje wpływu</h2><p>Żadna wpłata nie daje wpływu na diagnozy, na wybór czytanych kont ani na treść serwisu. Dr. Spin ocenia rządzących i opozycję według tych samych zasad, a jego diagnoz nikt nie poprawia. Nie przyjmujemy wpłat od partii, polityków ani ich fundacji.</p></section>
    <section><h2>Wybierz sposób wsparcia</h2>{links.length ? <><p>Jednorazowo — BuyCoffee, co miesiąc — Patronite. Wpłaty obsługują te serwisy; spin.clinic nie przetwarza danych płatniczych.</p><div className="sc-info-page__actions">{links.map(link => <Button key={link.href} href={link.href} variant="primary">{link.label}</Button>)}</div></> : <p>Linki do BuyCoffee i Patronite pojawią się tutaj wkrótce. Nie pobieramy płatności bezpośrednio w serwisie.</p>}</section>
    <section><h2>Dziękujemy</h2><p>Jeśli nie możesz wesprzeć finansowo, udostępnij diagnozę z <Link href="/klinika">Kliniki</Link> na X — to też bardzo pomaga.</p></section>
  </InfoPage>;
}
