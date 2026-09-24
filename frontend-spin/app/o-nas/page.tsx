import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'O nas — spin.clinic',
  description: 'Czym jest spin.clinic: materiały w kontekście źródeł, czasu i powiązanych publikacji. Trzy fazy projektu, rola redakcji i ograniczenia AI.',
  alternates: { canonical: '/o-nas' },
};

/** Data ostatniej zmiany opisu metody — aktualizować przy każdej zmianie treści tej strony. */
const LAST_UPDATED = { iso: '2026-09-23', label: '23 września 2026' };

const RELATIONS = ['hasło', 'osoba', 'instytucja', 'wydarzenie', 'kategoria', 'czas publikacji'];

const TIMELINE = [
  { date: '12.09', label: 'dokument', current: false },
  { date: '14.09', label: 'wpis', current: false },
  { date: '14.09', label: 'ten box', current: true },
  { date: '15.09', label: 'nagranie', current: false },
  { date: '17.09', label: 'reportaż', current: false },
];

const THREAD = ['DOKUMENT', 'KOMUNIKAT', 'NAGRANIE', 'ARTYKUŁ'];

const TECH = [
  {
    question: 'Skąd bierzemy materiały?',
    answer: 'Z kanałów, które wydawcy i instytucje udostępniają do pobierania: oficjalnych API (np. Sejmu i ELI), kanałów RSS, BIP-ów, opisów filmów z YouTube oraz — przez oficjalne, płatne API — wpisów z ręcznie potwierdzonych kont w X. Programy pobierające trzymają się limitów każdego źródła i nie obchodzą blokad.',
    technical: 'importery w Pythonie, kolejki zadań Celery i Redis',
  },
  {
    question: 'Gdzie je przechowujemy?',
    answer: 'W bazie danych, w której każdy box ma źródło, datę publikacji, datę pobrania, sposób pozyskania i odnośnik do oryginału. Jeśli czegoś nie wiemy — na przykład dokładnej godziny — pokazujemy to jako brak, a nie zgadujemy.',
    technical: 'PostgreSQL, API w Django',
  },
  {
    question: 'Jak to widzisz?',
    answer: 'Jako stronę internetową, która działa w przeglądarce komputera i telefonu. Nie wymaga konta ani instalacji. Ustawienia, takie jak motyw czy własne paski, zostają lokalnie w Twojej przeglądarce.',
    technical: 'Next.js i React',
  },
  {
    question: 'Jak szukamy powiązań?',
    answer: 'Dziś: po słowach, datach, źródłach i kategoriach. W fazie III chcemy dodać wyszukiwanie po znaczeniu — tekst zamieniany jest na liczbowy „odcisk” treści, dzięki czemu można znaleźć materiały o tym samym, opisane innymi słowami. Drugi krok ponownie układa wyniki według trafności.',
    technical: 'faza III: embeddingi i reranking (NVIDIA NIM)',
  },
  {
    question: 'Do czego posłuży AI?',
    answer: 'Do przygotowania szkicu dla redaktora: listy materiałów z cytatami, datami i brakami danych. Model musi zwrócić odpowiedź w ściśle określonym formacie, a program odrzuca ją, jeśli brakuje źródeł albo pojawiają się materiały spoza bazy. Dopiero wtedy szkic trafia do człowieka.',
    technical: 'faza III: szkice w formacie JSON (Groq)',
  },
];

const DOES: Array<{ text: string; when: 'teraz' | 'w budowie' | 'zasada' }> = [
  { text: 'pokazuje źródło, datę i odnośnik do oryginału każdego materiału', when: 'teraz' },
  { text: 'układa materiały w kolejności publikacji', when: 'teraz' },
  { text: 'łączy je po haśle, kategorii i czasie', when: 'teraz' },
  { text: 'pokazuje znane braki, np. gdy nie znamy daty publikacji', when: 'teraz' },
  { text: 'łączy materiały po osobach, instytucjach i wydarzeniach', when: 'w budowie' },
  { text: 'odróżnia źródła pierwotne — dokumenty, komunikaty, nagrania — od ich opisów', when: 'w budowie' },
  { text: 'wyraźnie oznacza każdy materiał reklamowy lub sponsorowany', when: 'zasada' },
];

function PhaseList({ items }: { items: string[] }) {
  return <ul className="sc-about-list">{items.map(item => <li key={item}>{item}</li>)}</ul>;
}

export default function AboutPage() {
  const contact = process.env.NEXT_PUBLIC_CONTACT_EMAIL;

  return (
    <article className="sc-about">
      <header className="sc-about-hero">
        <p className="sc-about-kicker">O NAS</p>
        <h1>Kontekst przed opinią</h1>
        <p className="sc-about-lead">
          spin.clinic pomaga czytać materiały w kontekście źródeł, czasu i powiązanych publikacji. Nie mówimy, co jest prawdą.
          Pokazujemy, skąd pochodzi informacja i co ukazało się przed nią i po niej — tak, żeby można było ocenić to samodzielnie.
        </p>
        <p className="sc-about-status">
          <span>Stan projektu</span> faza I — działające MVP w budowie. Opisujemy tu także plany; przy każdej fazie zaznaczamy, co już działa, a co dopiero powstanie.
        </p>
        <nav className="sc-about-toc" aria-label="Na tej stronie">
          <a href="#box">Box</a>
          <a href="#fazy">Trzy fazy</a>
          <a href="#redakcja">Człowiek i AI</a>
          <a href="#technologia">Technologia</a>
          <a href="#granice">Co robimy, czego nie</a>
          <a href="#dalej">Źródła i kontakt</a>
        </nav>
      </header>

      <section id="box" className="sc-about-section" aria-labelledby="onas-box">
        <div className="sc-about-intro">
          <p className="sc-about-kicker">IDEA</p>
          <h2 id="onas-box">Jeden materiał — jeden box</h2>
        </div>
        <div className="sc-about-split">
          <div className="sc-about-prose">
            <p>
              Box to karta pojedynczego materiału: artykułu, wywiadu, dokumentu, nagrania, wpisu albo komunikatu.
              Zawsze pokazuje źródło, datę, kategorię i odnośnik do oryginału. Nie zastępuje publikacji wydawcy — prowadzi do niej.
            </p>
            <p>
              Po otwarciu boxa widać inne materiały, które łączy z nim:
            </p>
            <ul className="sc-about-chips" aria-label="Rodzaje powiązań">
              {RELATIONS.map(relation => <li key={relation}>{relation}</li>)}
            </ul>
            <p>
              Dzięki temu pojedynczy nagłówek nie jest oderwany od tego, co wydarzyło się wcześniej i później. Powiązanie oznacza wspólny element — nie dowód, że jeden materiał potwierdza drugi.
            </p>
            <p className="sc-about-aside">
              Dziś powiązania opierają się głównie na słowach, kategoriach i dacie. Łączenie po osobach, instytucjach i wydarzeniach rozwijamy.
            </p>
          </div>
          <figure className="sc-about-sample">
            <div className="sc-about-box">
              <span className="sc-about-box-top"><span className="sc-about-tag">KOMUNIKAT</span><span>14.09 · 12:00</span></span>
              <span className="sc-about-box-source">Urząd Miasta Przykładowego</span>
              <strong>Komunikat w sprawie czasowego zamknięcia mostu</strong>
              <span className="sc-about-box-meta">kategoria: samorząd · odnośnik do oryginału ↗</span>
            </div>
            <figcaption>Przykład układu boxa. Dane są fikcyjne.</figcaption>
          </figure>
        </div>
      </section>

      <section className="sc-about-section" aria-labelledby="onas-flow">
        <div className="sc-about-intro">
          <p className="sc-about-kicker">JAK CZYTAĆ</p>
          <h2 id="onas-flow">Od boxa do nitki</h2>
        </div>
        <ol className="sc-about-flow">
          <li>
            <p className="sc-about-step">1 · BOX</p>
            <h3>Materiał źródłowy</h3>
            <div className="sc-about-mini-box" aria-hidden="true"><span className="sc-about-tag">KOMUNIKAT</span><span>14.09 · 12:00</span></div>
            <p>Jedna publikacja z pochodzeniem, datą i linkiem.</p>
          </li>
          <li>
            <p className="sc-about-step">2 · OŚ CZASU</p>
            <h3>Powiązane materiały</h3>
            <ol className="sc-about-mini-axis" aria-label="Przykładowa oś czasu">
              {TIMELINE.map(item => (
                <li key={`${item.date}-${item.label}`} className={item.current ? 'is-current' : ''}>
                  <span>{item.date}</span>{item.label}
                </li>
              ))}
            </ol>
            <p>Dobierane automatycznie, ułożone według daty publikacji. To mapa, nie ocena.</p>
          </li>
          <li>
            <p className="sc-about-step">3 · NITKA DR SPINA</p>
            <h3>Kontekst ułożony przez człowieka</h3>
            <ol className="sc-about-mini-thread" aria-label="Przykładowa nitka">
              {THREAD.map(item => <li key={item}>{item}</li>)}
            </ol>
            <p>Redaktor wybiera materiały, ustala kolejność, pisze opis i zatwierdza publikację.</p>
          </li>
        </ol>
        <p className="sc-about-note">Krok 2 wykonuje program i nie wyciąga wniosków. Krok 3 jest pracą redakcji — tylko on trafia na stronę jako nitka Dr Spina.</p>
      </section>

      <section id="fazy" className="sc-about-section" aria-labelledby="onas-phases">
        <div className="sc-about-intro">
          <p className="sc-about-kicker">ROZWÓJ</p>
          <h2 id="onas-phases">Trzy fazy projektu</h2>
        </div>
        <div className="sc-about-phases">
          <section className="sc-about-phase is-current" aria-labelledby="onas-phase-1">
            <header>
              <p className="sc-about-phase-status">FAZA I · TERAZ</p>
              <h3 id="onas-phase-1">Działające MVP</h3>
            </header>
            <p>Baza materiałów z legalnych i możliwych do sprawdzenia źródeł, pokazanych jako boxy, na osi czasu i w powiązaniach tematycznych.</p>
            <PhaseList items={[
              'źródła: oficjalne API instytucji, RSS, BIP, Sejm, ELI, opisy filmów z YouTube (bez transkrypcji) oraz wpisy z X — wyłącznie przez oficjalne płatne API, w pilotażu z ręcznie potwierdzonych kont',
              'Temat dnia — automatycznie powiązane materiały ułożone chronologicznie',
              'Baza — wyszukiwanie po haśle, źródle, kategorii i dacie',
              'Dr Spin — nitki układane ręcznie przez redakcję',
              'katalog źródeł i prosty kontekst po otwarciu boxa',
            ]} />
            <p className="sc-about-phase-limit"><span>W trakcie udostępniania:</span> konta użytkowników, prywatne nitki, komentarze i reakcje. Wyszukiwanie po znaczeniu pozostaje planem pilotażu. Baza jest w trakcie uzupełniania i nie obejmuje wszystkich źródeł.</p>
          </section>

          <section className="sc-about-phase" aria-labelledby="onas-phase-2">
            <header>
              <p className="sc-about-phase-status">FAZA II · NASTĘPNY ETAP</p>
              <h3 id="onas-phase-2">Społeczność i własny kontekst</h3>
            </header>
            <p>Konto pozwoli zachować swoją pracę z materiałami i wracać do obserwowanych tematów.</p>
            <PhaseList items={[
              'konta, ulubione materiały i obserwowane tematy',
              'własne nitki kontekstowe i własny wybór źródeł',
              'komentarze i dyskretne reakcje — o przydatności materiału, nie o ludziach',
            ]} />
            <p className="sc-about-phase-limit"><span>Nadal bez:</span> automatycznej publikacji i automatycznych ocen.</p>
          </section>

          <section className="sc-about-phase" aria-labelledby="onas-phase-3">
            <header>
              <p className="sc-about-phase-status">FAZA III · PLAN</p>
              <h3 id="onas-phase-3">Asystent redakcyjny Dr Spin</h3>
            </header>
            <p>Asystent redakcyjny oparty na modelach open-weight. Zaczynamy od usług zewnętrznych:</p>
            <PhaseList items={[
              'NVIDIA NIM — wyszukiwanie materiałów po znaczeniu i porządkowanie wyników według trafności',
              'Groq — szybkie szkice redakcyjne w ściśle określonym formacie',
              'wynik AI jest wyłącznie propozycją dla redaktora; żaden model nie publikuje sam',
            ]} />
            <p>
              Z czasem chcemy uniezależniać się od zewnętrznych dostawców i uruchamiać modele open-weight na własnej infrastrukturze — po sprawdzeniu jakości, licencji i kosztów.
            </p>
            <p className="sc-about-phase-limit"><span>Stan:</span> połączenia są przygotowane i domyślnie wyłączone. Włączymy je dopiero po pilotażu na kilkudziesięciu ręcznie sprawdzonych materiałach.</p>
          </section>
        </div>
      </section>

      <section id="redakcja" className="sc-about-section" aria-labelledby="onas-editorial">
        <div className="sc-about-intro">
          <p className="sc-about-kicker">REDAKCJA</p>
          <h2 id="onas-editorial">Decyduje człowiek. AI pomaga szukać.</h2>
        </div>
        <div className="sc-about-columns">
          <div>
            <h3>Co robi redaktor</h3>
            <PhaseList items={[
              'wybiera materiały do nitki i ustala ich kolejność',
              'pisze krótki opis tego, co zestawienie pokazuje',
              'zatwierdza publikację albo ją wstrzymuje',
              'poprawia błędy i oznacza korekty',
            ]} />
          </div>
          <div>
            <h3>Co będzie mogło AI</h3>
            <PhaseList items={[
              'odnaleźć podobne materiały w bazie',
              'uporządkować kandydatów według trafności',
              'zaproponować szkic z cytatami, linkami i brakami danych',
            ]} />
          </div>
          <div className="sc-about-limits">
            <h3>Ograniczenia, o których mówimy wprost</h3>
            <PhaseList items={[
              'model może przeoczyć materiał albo źle połączyć zdarzenia',
              'zna tylko to, co jest w bazie — nie zna kontekstu spoza niej',
              'nie ocenia osób i nie rozstrzyga, co jest prawdą',
              'do zewnętrznych dostawców trafia tylko krótki fragment publicznego materiału ze źródłem i datą — nigdy dane kont ani prywatna aktywność',
            ]} />
          </div>
        </div>
      </section>

      <section id="technologia" className="sc-about-section" aria-labelledby="onas-tech">
        <div className="sc-about-intro">
          <p className="sc-about-kicker">TECHNOLOGIA</p>
          <h2 id="onas-tech">Jak to działa — po ludzku</h2>
        </div>
        <dl className="sc-about-tech">
          {TECH.map(item => (
            <div key={item.question}>
              <dt>{item.question}</dt>
              <dd>
                <p>{item.answer}</p>
                <small>Technicznie: {item.technical}</small>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section id="granice" className="sc-about-section" aria-labelledby="onas-scope">
        <div className="sc-about-intro">
          <p className="sc-about-kicker">GRANICE</p>
          <h2 id="onas-scope">Co portal robi, a czego nie robi</h2>
        </div>
        <div className="sc-about-scope">
          <div>
            <h3>Robi</h3>
            <ul className="sc-about-list is-yes">
              {DOES.map(item => (
                <li key={item.text}>{item.text} <span className={`sc-about-when is-${item.when === 'teraz' ? 'now' : 'next'}`}>{item.when}</span></li>
              ))}
            </ul>
            <p className="sc-about-aside">„Teraz” — działa w MVP. „W budowie” — rozwijamy w fazie I. „Zasada” — obowiązuje każdą przyszłą funkcję.</p>
          </div>
          <div>
            <h3>Nie robi</h3>
            <ul className="sc-about-list is-no">
              <li>nie ocenia osób</li>
              <li>nie oznacza treści jako „prawda” lub „fałsz”</li>
              <li>nie publikuje niczego automatycznie</li>
              <li>nie pisze własnych newsów ani nie zastępuje wydawców</li>
              <li>nie kopiuje pełnych tekstów bez zgody wydawcy i nie traktuje braku odpowiedzi jako zgody</li>
              <li>nie obchodzi blokad, limitów ani płatnych dostępów</li>
            </ul>
          </div>
        </div>
      </section>

      <section id="dalej" className="sc-about-section" aria-labelledby="onas-next">
        <div className="sc-about-intro">
          <p className="sc-about-kicker">DALEJ</p>
          <h2 id="onas-next">Sprawdź źródła i zasady</h2>
        </div>
        <ul className="sc-about-next">
          <li>
            <Link href="/zrodla">
              <span className="sc-about-step">ŹRÓDŁA</span>
              <strong>Jakie źródła są w katalogu</strong>
              <span>Które są aktywne, a które czekają na weryfikację kanału i zasad wykorzystania.</span>
              <span className="sc-about-arrow" aria-hidden="true">→</span>
            </Link>
          </li>
          <li>
            <Link href="/zasady-korzystania">
              <span className="sc-about-step">ZASADY</span>
              <strong>Zasady korzystania</strong>
              <span>Jak traktujemy materiały, wpisy z platform i redakcyjne nitki.</span>
              <span className="sc-about-arrow" aria-hidden="true">→</span>
            </Link>
          </li>
          <li>
            {contact ? (
              <a href={`mailto:${contact}`}>
                <span className="sc-about-step">KONTAKT</span>
                <strong>Napisz do redakcji</strong>
                <span>Błąd w materiale, propozycja źródła albo pytanie o metodę: {contact}</span>
                <span className="sc-about-arrow" aria-hidden="true">→</span>
              </a>
            ) : (
              <div className="sc-about-next-static">
                <span className="sc-about-step">KONTAKT</span>
                <strong>Kontakt z redakcją</strong>
                <span>Adres kontaktowy opublikujemy przed publicznym uruchomieniem. Źródło możesz już zaproponować na stronie <Link href="/zrodla">Źródła</Link>.</span>
              </div>
            )}
          </li>
        </ul>
        <p className="sc-about-updated">
          Ostatnia zmiana opisu: <time dateTime={LAST_UPDATED.iso}>{LAST_UPDATED.label}</time> · <Link href="/polityka-prywatnosci">Prywatność i cookies</Link> · <Link href="/wsparcie">Wsparcie projektu</Link>
        </p>
      </section>
    </article>
  );
}
