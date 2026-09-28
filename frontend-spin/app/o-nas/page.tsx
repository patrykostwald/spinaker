import Link from 'next/link';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { ContextThreadExample } from './ContextThreadExample';
import { SUPPORT_LINKS } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'O nas — spin.clinic',
  description:
    'spin.clinic pokazuje chwyty, nie werdykty: Dr. Spin (AI) rozkłada przekazy polityków i mediów na czynniki pierwsze — obie strony tą samą miarą, automatycznie, ze źródłami.',
  alternates: { canonical: '/o-nas' },
};

/** Data ostatniej zmiany opisu — aktualizować przy każdej zmianie treści tej strony. */
const LAST_UPDATED = { iso: '2026-09-28', label: '28 września 2026' };

const SOURCES_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL || 'zrodla@spin.clinic';
const OPERATOR = 'iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań, KRS 0001133291, NIP 7831915094, REGON 529962488';
const CONTACTS: Array<{ email: string; purpose: string }> = [
  { email: 'kontakt@spin.clinic', purpose: 'pytania o projekt, współpraca, media' },
  { email: SOURCES_EMAIL, purpose: 'źródła, zgody wydawców, zakres dostępu' },
  { email: 'admin@spin.clinic', purpose: 'sprawy techniczne, prywatność, zgłoszenia dotyczące diagnoz' },
];

const SECTIONS = [
  { id: 'spin-doctor', label: 'Spin doctor' },
  { id: 'o-nas', label: 'Dlaczego' },
  { id: 'czym-nie-jestesmy', label: 'Czym nie jesteśmy' },
  { id: 'pojecia', label: 'Pojęcia' },
  { id: 'klinika', label: 'Jak działa Dr. Spin' },
  { id: 'konsylium', label: 'Konsylium AI' },
  { id: 'zasady', label: 'Zasady' },
  { id: 'dla-redakcji', label: 'Dla dziennikarzy i redakcji' },
  { id: 'fazy', label: 'Trzy fazy' },
  { id: 'wsparcie', label: 'Utrzymanie i kontakt' },
];

/** Co jeszcze robi Klinika poza diagnozą wpisu — kafelki zamiast długiej listy. */
const CLINIC_FEATURES = [
  ['Spin dnia', 'Diagnoza z najwyższą siłą spinu z dzisiejszego dnia — oraz najnowszy spin, żeby zawsze było co porównać.'],
  ['Przekaz dnia', 'Darmowe modele streszczają wpisy obozu (co najmniej trzech kont) pięć razy dziennie — z pełną analizą, wpisami źródłowymi i archiwum.'],
  ['Wywiad dnia', 'Co rano automat wybiera najgłośniejszą rozmowę z politykiem z poprzedniego dnia; Dr. Spin ocenia gościa i warsztat prowadzącego tą samą skalą, z minutą nagrania.'],
  ['Strażnica', 'Sprawdzamy, czy politycy usuwają wpisy. Treści nie pokazujemy (zasady X) — fakt, czas i link do kopii w publicznym archiwum, jeśli istnieje. W niedzielę — raport tygodnia.'],
  ['Profile polityków', '„Występuje w podmiotach”: fundacje, stowarzyszenia i spółki potwierdzone w KRS, oraz kariera w spółkach Skarbu Państwa.'],
  ['Na X', 'Konto @spinclinic samo publikuje silne spiny (od 70/100) — jeden wpis z obrazkiem wpisu, bez oznaczania autora. Każdą diagnozę udostępnisz też sam jednym wpisem.'],
];

/** Zakres dostępu do materiałów wydawcy (odczyt RSS) — prostym językiem. */
const PUBLISHER_SCOPE: Array<[string, string]> = [
  ['Co pobieramy', 'tytuł, autora, datę publikacji, link i nazwę źródła'],
  ['Skąd', 'ze wskazanego kanału RSS albo wskazanych stron publicznych'],
  ['Tempo', 'co najmniej 3 sekundy między zapytaniami i uzgodniony limit dzienny'],
  ['Czego nie pobieramy', 'pełnych tekstów, zdjęć ani kopii artykułów; nie trenujemy na nich modeli AI'],
  ['Czytelnik', 'widzi box ze źródłem, a po kliknięciu trafia do oryginału'],
  ['Zgoda', 'brak odpowiedzi nie jest zgodą — źródło pozostaje wyłączone'],
  ['Rezygnacja', 'wystarczy wiadomość, a wyłączymy źródło'],
  ['Kontakt', SOURCES_EMAIL],
];

const PARTS = [
  { href: '/', name: 'Wiadomości', status: 'działa · beta', text: 'Wiadomości mediów, instytucji publicznych i oficjalnych kanałów wideo. Każdy materiał to box ze źródłem, datą i linkiem do oryginału — w Najnowszych, na paskach i w Bazie z wyszukiwarką.' },
  { href: '/klinika', name: 'Klinika', status: 'działa · beta', text: 'Dr. Spin (AI) ocenia wpisy polityków na X i najgłośniejszy wywiad dnia — także warsztat prowadzącego. Techniki perswazji z cytatami, twierdzenia ze źródłami. Rządzący i opozycja tą samą miarą.' },
  { href: '#fazy', name: 'Nitki', status: 'faza II', text: 'Miejsce dla czytelników: sam wyjaśniasz spin, układając nitkę kontekstową z materiałów z naszej Bazy albo dodanych przez link, z reakcjami i komentarzami.' },
];

/** Konsylium: kto w nim zasiada i co robi. Skład może się zmieniać — aktualny zawsze pod diagnozą. */
const COUNCIL_ROLES = [
  { role: 'Specjaliści konsylium', who: 'gpt-oss (OpenAI) · Qwen (Alibaba) · Nemotron (NVIDIA) · Gemini (Google)', text: 'Każdy osobno i niezależnie ocenia cały wpis: werdykt, siłę 0–100, techniki z dosłownym cytatem i twierdzenia do sprawdzenia. Żaden nie widzi odpowiedzi pozostałych.' },
  { role: 'Laboratorium', who: 'Gemini z wyszukiwarką Google', text: 'Bada w wyszukiwarce każde twierdzenie o faktach. Źródło trafia do diagnozy tylko wtedy, gdy rzeczywiście pojawiło się w wynikach.' },
  { role: 'Konsultant', who: 'Claude (Anthropic) — płatny', text: 'Mocniejszy model z wyszukiwaniem wzywamy, gdy specjaliści się nie zgadzają (mniej niż dwie trzecie zgodnych głosów) albo spin jest silny (70/100 i więcej) — tam, gdzie pomyłka kosztowałaby najwięcej.' },
  { role: 'Lekarz prowadzący', who: 'Gemini (w zapasie: Nemotron, gpt-oss)', text: 'Pisze diagnozę wyłącznie na podstawie ustaleń konsylium i laboratorium. Nie może zmienić werdyktu ani siły, nie może też dodać techniki, której nie wskazali lekarze.' },
  { role: 'Ordynator', who: 'Nemotron (NVIDIA)', text: 'Niezależnie sprawdza, czy diagnoza zgadza się z ocenami i źródłami. Jeśli znajdzie błąd, lekarz prowadzący raz poprawia tekst, a uwagi ordynatora pozostają jawne.' },
  { role: 'Redaktor', who: 'Qwen (Alibaba)', text: 'Poprawia wyłącznie polszczyznę. Jeśli jego wersja zmienia sens, zostaje tekst lekarza prowadzącego.' },
];

/** Droga wpisu do diagnozy — pięć kroków zamiast schematu rysowanego znakami. */
const CLINIC_STEPS = [
  { title: 'Izba przyjęć', caption: 'czy we wpisie jest coś do zbadania' },
  { title: 'Konsylium', caption: 'niezależne oceny kilku specjalistów AI' },
  { title: 'Badania', caption: 'twierdzenia sprawdzone w źródłach' },
  { title: 'Diagnoza i terapia', caption: 'techniki z cytatami i co mówią źródła' },
  { title: 'Na X', caption: 'silne spiny publikujemy na @spinclinic' },
];

/**
 * Statusy technologii i funkcji — tylko cztery, zawsze te same słowa:
 * „działa” — obecne w kodzie i wdrożone; „beta” — dostępne, nadal rozwijane;
 * „planowane” — w planie rozwoju; „wymaga potwierdzenia” — przygotowane lub rozważane, jeszcze nie uruchomione.
 */
type Status = 'działa' | 'beta' | 'planowane' | 'wymaga potwierdzenia';
const STATUS_KEYS: Record<Status, string> = { działa: 'live', beta: 'beta', planowane: 'planned', 'wymaga potwierdzenia': 'pending' };
const STATUS_HELP: Array<[Status, string]> = [
  ['działa', 'obecne w kodzie i wdrożone'],
  ['beta', 'dostępne, nadal rozwijane'],
  ['planowane', 'w planie kolejnych etapów'],
  ['wymaga potwierdzenia', 'przygotowane albo rozważane, jeszcze nie uruchomione'],
];

type TechItem = { name: string; note?: string; status: Status };
type Phase = {
  id: string;
  status: string;
  title: string;
  lead: string;
  features: Array<{ text: string; status: Status }>;
  stack: Array<{ group: string; items: TechItem[] }>;
  current?: boolean;
};

const PHASES: Phase[] = [
  {
    id: 'faza-1',
    status: 'Faza I · działa dzisiaj',
    title: 'Wiadomości i Klinika',
    lead: 'To, co działa już dziś. Funkcje oznaczone jako „beta” są dostępne, ale wciąż je rozwijamy.',
    features: [
      { text: 'Wiadomości: Najnowsze, Baza z wyszukiwarką i filtrami, do pięciu własnych pasków „Twoje wiadomości” zapisanych na urządzeniu', status: 'beta' },
      { text: 'box materiału z osią czasu i powiązanymi materiałami', status: 'beta' },
      { text: 'Klinika spinu: izba przyjęć wpisów, diagnozy i terapie AI, spin dnia i najnowszy spin, liczniki przy każdym polityku', status: 'beta' },
      { text: 'przekaz dnia obu obozów z pełną analizą, wpisami źródłowymi i archiwum', status: 'beta' },
      { text: 'wywiad dnia wybierany automatycznie z kilkudziesięciu kanałów i całego YouTube — ocena gościa i warsztatu prowadzącego, z cytatami i minutą nagrania', status: 'beta' },
      { text: 'filmy z oficjalnych kanałów YouTube instytucji, partii i mediów — z doborem materiałów z różnych źródeł (pluralizm)', status: 'beta' },
      { text: 'konsylium Dr. Spina: kilka niezależnych modeli AI różnych firm, wspólna ocena, kontrola ordynatora i korekta językowa', status: 'beta' },
      { text: 'strażnica usuniętych wpisów polityków i tygodniowy raport Dr. Spina z wątkiem na X', status: 'beta' },
      { text: 'profile osób publicznych: „Występuje w podmiotach” — fundacje, stowarzyszenia i spółki potwierdzone w KRS — oraz drzewko kariery w spółkach Skarbu Państwa', status: 'beta' },
      { text: 'diagnoza na X jednym wpisem — do udostępnienia przez czytelnika i automatycznie z konta @spinclinic (spiny od 70/100); rejestr osób publicznych z oficjalnymi kontami X', status: 'beta' },
      { text: 'autoryzowane nitki dziennikarzy: box otwierający i do 14 boxów kontekstu, nowy box po linku, cała nitka jako wątek na X', status: 'beta' },
      { text: 'instalacja na telefonie z przeglądarki (aplikacja PWA)', status: 'beta' },
    ],
    stack: [
      { group: 'Serwis', items: [
        { name: 'Next.js 14 · React · TypeScript · Tailwind CSS', note: 'motyw jasny i ciemny, telefon i komputer', status: 'działa' },
        { name: 'Python · Django 5 · Django REST Framework', note: 'dane, rejestry, publiczne API z opisem OpenAPI', status: 'działa' },
      ] },
      { group: 'Dane', items: [
        { name: 'PostgreSQL 15 · Redis 7 · Celery', note: 'baza i zadania w tle według harmonogramu', status: 'działa' },
        { name: 'importery źródeł fail-closed', note: 'bez zatwierdzonego kanału i zakresu dostępu źródło nie jest pobierane', status: 'działa' },
      ] },
      { group: 'Źródła', items: [
        { name: 'oficjalne API Sejmu i ELI · RSS · BIP', status: 'działa' },
        { name: 'API X (oficjalne, płatne)', note: 'wpisy z kont potwierdzonych dowodem', status: 'działa' },
        { name: 'YouTube Data API', note: 'oficjalne kanały instytucji, partii i mediów (z dowodem na stronie źródła) oraz automatyczny wybór wywiadu dnia', status: 'działa' },
      ] },
      { group: 'AI w Klinice', items: [
        { name: 'Groq · NVIDIA NIM', note: 'izba przyjęć wpisów, przekazy dnia i konsylium: gpt-oss (OpenAI), Qwen (Alibaba), Nemotron (NVIDIA) — bez kosztów', status: 'beta' },
        { name: 'Gemini (Google)', note: 'członek konsylium, sprawdzanie faktów w wyszukiwarce Google, opis zdjęć z wpisów, transkrypcja wywiadu dnia', status: 'beta' },
        { name: 'Claude (Anthropic) z wyszukiwaniem w sieci', note: 'konsultacje przy spornych i silnych spinach oraz ocena wywiadu dnia', status: 'beta' },
      ] },
      { group: 'Infrastruktura', items: [
        { name: 'Docker · Caddy (HTTPS) · serwer VPS · GitHub Actions', status: 'działa' },
      ] },
    ],
    current: true,
  },
  {
    id: 'faza-2',
    status: 'Faza II · najbliższy etap',
    title: 'Nitki czytelników',
    lead: 'Trzecia część serwisu: czytelnicy układają i publikują własne nitki kontekstowe.',
    features: [
      { text: 'konta czytelników: reakcje i komentarze z moderacją pod diagnozami i materiałami, ulubione, panel użytkownika', status: 'planowane' },
      { text: 'nitki kontekstowe czytelników — prywatne i publiczne; wyjaśnianie spinu materiałami z Bazy', status: 'planowane' },
      { text: 'dodawanie materiału przez link także dla czytelników — ten sam link to jeden box, bez duplikatów', status: 'planowane' },
      { text: 'w Klinice dowody jako boxy z naszej bazy zamiast samego tekstu', status: 'planowane' },
      { text: 'strażnica zmian: pokazujemy, gdy źródło po publikacji zmieni albo usunie materiał — z datą i wersją sprzed zmiany', status: 'planowane' },
      { text: 'dane analityczne: indeks spinu polityków i partii w czasie, najczęstsze techniki, tematy przekazów; później — które nitki i narracje trafiają do czytelników', status: 'planowane' },
      { text: 'dyskusja pod nitkami czytelników — argument wymaga źródła (link albo box z Bazy)', status: 'planowane' },
      { text: 'diagnozy kolejnych nagrań wideo (poza wywiadem dnia) i alerty po haśle albo źródle', status: 'planowane' },
    ],
    stack: [
      { group: 'Technologia', items: [
        { name: 'NVIDIA NIM — wyszukiwanie po znaczeniu', note: 'dobór powiązanych materiałów w bazie; przygotowane, wyłączone', status: 'wymaga potwierdzenia' },
        { name: 'powiadomienia e-mail, w serwisie i push (PWA)', status: 'planowane' },
      ] },
    ],
  },
  {
    id: 'faza-3',
    status: 'Faza III · kolejne fazy',
    title: 'Własna maszyna i otwarte modele',
    lead: 'Zamiast zestawu zewnętrznych usług — własny serwer i otwarty model, który czyta wpisy i stawia diagnozy.',
    features: [
      { text: 'diagnozy na własnym serwerze GPU, na otwartych modelach — z pełną kontrolą i jawną konfiguracją', status: 'planowane' },
      { text: 'asystent OSINT oparty na naszej bazie (RAG): wklejasz link, pytanie albo plik — dostajesz rozbiór narracji i źródła; każde ustalenie z boxem źródłowym', status: 'planowane' },
      { text: 'aplikacje mobilne w App Store i Google Play — ta sama baza i Klinika, powiadomienia o nowych spinach', status: 'planowane' },
      { text: 'mapy powiązań osób, instytucji i materiałów', status: 'planowane' },
    ],
    stack: [
      { group: 'Technologia', items: [
        { name: 'otwarte modele, m.in. polskie Bielik i PLLuM', note: 'wybór po porównaniu jakości z obecnymi diagnozami', status: 'wymaga potwierdzenia' },
        { name: 'Qdrant', note: 'kandydat do wyszukiwania wektorowego, po porównaniu z PostgreSQL', status: 'wymaga potwierdzenia' },
        { name: 'Capacitor albo React Native', note: 'aplikacje na iOS i Android zbudowane na obecnym serwisie', status: 'wymaga potwierdzenia' },
      ] },
    ],
  },
];

function StatusTag({ status }: { status: Status }) {
  return (
    <span className="sc-onas-tag" data-status={STATUS_KEYS[status]}>
      {status}
    </span>
  );
}

function Section({ id, index, kicker, title, children, level = 2 }: { id: string; index: number; kicker: string; title: string; children: ReactNode; level?: 1 | 2 }) {
  const Heading = level === 1 ? 'h1' : 'h2';
  return (
    <section id={id} className="sc-onas-section" aria-labelledby={`${id}-title`}>
      <header className="sc-onas-section__head">
        <p className="sc-onas-kicker">
          <span className="sc-onas-num">{String(index).padStart(2, '0')}</span> {kicker}
        </p>
        <Heading id={`${id}-title`} className="sc-onas-title">
          {title}
          <a className="sc-onas-anchor" href={`#${id}`} aria-label={`Link do sekcji: ${title}`}>
            #
          </a>
        </Heading>
      </header>
      {children}
    </section>
  );
}

export default function AboutPage() {
  return (
    <div className="sc-onas">
      <nav className="sc-onas-toc" aria-label="Na tej stronie">
        <p className="sc-onas-toc__title">Na tej stronie</p>
        <ol>
          {SECTIONS.map((section, index) => (
            <li key={section.id}>
              <a href={`#${section.id}`}>
                <span className="sc-onas-num">{String(index + 1).padStart(2, '0')}</span>
                {section.label}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <article className="sc-onas-main">
        <section id="spin-doctor" className="sc-onas-section sc-onas-hero" aria-labelledby="spin-doctor-title">
          <p className="sc-onas-kicker">
            <span className="sc-onas-num">01</span> Słownik
          </p>
          <figure className="sc-onas-dict">
            <p className="sc-onas-dict__term" id="spin-doctor-title">
              spin doctor
              <span className="sc-onas-dict__gram">także: spin doktor</span>
            </p>
            <blockquote className="sc-onas-dict__def">
              «osoba odpowiedzialna za wykreowanie dobrego wizerunku lub zwycięstwo w wyborach osoby publicznej (zwłaszcza polityka) lub partii»
            </blockquote>
            <figcaption className="sc-onas-dict__source">
              <a href="https://sjp.pwn.pl/sjp/spin-doctor;5569407.html" target="_blank" rel="noopener noreferrer">
                Słownik języka polskiego PWN ↗
              </a>
            </figcaption>
          </figure>
          <p className="sc-onas-hero__after">
            Spin to owoc tej pracy: informacja podana tak, by służyła nadawcy.
            <br />
            Tu spin traci przewagę — każdą informację widać razem ze źródłem, datą i kontekstem.
          </p>
        </section>

        <Section id="o-nas" index={2} kicker="Dlaczego" title="Pokazujemy chwyty, nie werdykty" level={1}>
          <div className="sc-onas-prose">
            <p className="sc-onas-lead">
              Każdy przekaz polityczny ma swój cel — i swoje sposoby, by go osiągnąć. Te sposoby pokazujemy: fałszywą alternatywę, przypisywanie intencji,
              dobór wygodnych danych. Wnioski należą do Ciebie.
            </p>
            <p>
              Dlatego Dr. Spin nie rozstrzyga, kto ma rację. Rozkłada wypowiedzi polityków i przekazy mediów na czynniki pierwsze: stawia diagnozę — wskazuje
              techniki z dosłownymi cytatami — i zaleca terapię: zestawia twierdzenia ze źródłami. Rządzących i opozycję obok siebie, tą samą miarą.
              Dr. Spin to konsylium: kilka niezależnych modeli AI różnych firm ocenia każdy wpis
              osobno, a diagnoza powstaje z ich wspólnej oceny.
            </p>
            <p>
              Całość działa automatycznie: diagnoz nie pisze ani nie poprawia człowiek. Ocenia AI — według jawnych zasad, bez sympatii i uprzedzeń.
            </p>
          </div>
          <ul className="sc-onas-parts">
            {PARTS.map((part) => (
              <li key={part.href}>
                <p className="sc-onas-parts__status">{part.status}</p>
                <h3>{part.href.startsWith('#') ? part.name : <Link href={part.href}>{part.name}</Link>}</h3>
                <p>{part.text}</p>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="czym-nie-jestesmy" index={3} kicker="Czym nie jesteśmy" title="Nie fact-check, nie czat z AI">
          <dl className="sc-onas-terms sc-onas-terms--three">
            <div>
              <dt>Nie fact-checking</dt>
              <dd>
                Nie wydajemy wyroków „prawda — fałsz”. Prawdziwe zdanie też bywa spinem — gdy podano je wybiórczo, bez punktu odniesienia albo z przypisaną
                komuś intencją. Pokazujemy, jak zbudowano przekaz.
              </dd>
            </div>
            <div>
              <dt>Nie czat z AI</dt>
              <dd>
                Czat odpowiada dopiero na pytanie — o jeden wpis, bez pamięci i nie zawsze z prawdziwym źródłem. Dr. Spin pracuje codziennie, z urzędu:
                najpierw szuka w naszej Bazie, potem w sieci, a diagnozy trafiają do archiwum.
              </dd>
            </div>
            <div>
              <dt>Nie uwagi społeczności</dt>
              <dd>
                Notatka społeczności pojawia się dopiero wtedy, gdy zgodzą się co do niej głosujący z różnych stron — pod większością wpisów polityków nie
                pojawia się wcale albo po kilku dniach. Dr. Spin ocenia wpisy w ciągu kilku godzin, u każdego obserwowanego polityka.
              </dd>
            </div>
          </dl>
        </Section>

        <Section id="pojecia" index={4} kicker="Pojęcia" title="Box, Twoje wiadomości, nitka kontekstowa">
          <dl className="sc-onas-terms">
            <div>
              <dt>Box</dt>
              <dd>
                Karta jednego materiału — artykułu, dokumentu, wywiadu, nagrania albo wpisu — zawsze ze źródłem, datą i linkiem do oryginału. Po otwarciu
                pokazuje oś czasu powiązanych materiałów.
              </dd>
            </div>
            <div>
              <dt>Twoje wiadomości</dt>
              <dd>
                Własne paski boxów na stronie głównej, przewijane w bok — najnowsze materiały według Twojego hasła, kategorii albo źródła. Możesz mieć do pięciu, bez zakładania konta.
              </dd>
            </div>
            <div>
              <dt>Nitka kontekstowa</dt>
              <dd>
                Poziomy pasek boxów: box otwierający, a za nim do 14 boxów, które dają mu kontekst. Dziś prowadzą je Dr. Spin i dziennikarze
                (<a href="#nitka-kontekstowa">autoryzowane nitki</a>); w fazie II — także czytelnicy.
              </dd>
            </div>
            <div>
              <dt>Diagnoza spinu</dt>
              <dd>
                Ocena Dr. Spina: werdykt (spin, częściowy spin, bez spinu, nie da się ocenić), siła 0–100 i techniki z dosłownymi cytatami. Do diagnozy
                dołącza terapia — twierdzenia zestawione ze źródłami. Z czasem dowodami będą boxy z naszej Bazy.
              </dd>
            </div>
          </dl>
        </Section>

        <Section id="klinika" index={5} kicker="Klinika spinu" title="Jak działa Dr. Spin">
          <div className="sc-onas-prose">
            <p>
              Czytamy wyłącznie oficjalne konta X polityków i partii, a każde potwierdzamy dowodem — rejestrem Sejmu, Senatu albo Parlamentu Europejskiego
              lub wpisem w Wikidata. Pełną listę publikujemy na dole Kliniki; brakujące konto można zgłosić. Każdy nowy wpis przechodzi pięć etapów, a płacimy
              tylko za te, które naprawdę warto zbadać.
            </p>
          </div>
          <ol className="sc-flow" aria-label="Droga wpisu do diagnozy">
            {CLINIC_STEPS.map((step, index) => (
              <li key={step.title} className="sc-flow__step">
                <span className="sc-flow__num">{index + 1}</span>
                <strong>{step.title}</strong>
                <span className="sc-flow__caption">{step.caption}</span>
              </li>
            ))}
          </ol>
          <p className="sc-flow__more"><a href="#konsylium">Kto zasiada w konsylium i jakich modeli AI używamy →</a></p>
          <h3 className="sc-onas-subtitle">Co jeszcze robi Klinika</h3>
          <dl className="sc-onas-terms sc-onas-terms--three">
            {CLINIC_FEATURES.map(([term, text]) => (
              <div key={term}>
                <dt>{term}</dt>
                <dd>{text}</dd>
              </div>
            ))}
          </dl>
          <p className="sc-onas-callout">
            Dr. Spin nie ogłasza prawdy i nie zastępuje dziennikarza. Pokazuje, jak zbudowano przekaz i co mówią źródła — ocena należy do Ciebie.
          </p>
        </Section>

        <Section id="konsylium" index={6} kicker="Konsylium AI" title="Rada modeli AI zamiast jednego">
          <div className="sc-onas-prose">
            <p className="sc-onas-lead">
              Każdy model AI ma swoje skrzywienia — wynikające z danych, na których go uczono, i z zasad firmy, która go zbudowała. Jeden model to jedna opinia.
              Dlatego Dr. Spin nie jest jednym modelem, tylko konsylium: kilka modeli różnych firm ocenia ten sam wpis niezależnie od siebie, a diagnoza powstaje
              z ich wspólnej oceny według stałych, jawnych zasad.
            </p>
            <p>
              Do każdego zadania dobieramy model, który sprawdza się w nim najlepiej: otwarty i darmowy tam, gdzie wystarczy, płatny tam, gdzie potrzebna jest
              mocniejsza weryfikacja. Pieniądze wydajemy więc tylko na trudne przypadki.
            </p>
          </div>
          <dl className="sc-onas-terms sc-onas-terms--three">
            {COUNCIL_ROLES.map(item => (
              <div key={item.role}>
                <dt>{item.role}</dt>
                <dd>
                  <span className="sc-onas-flow__tech">{item.who}</span>
                  <br />
                  {item.text}
                </dd>
              </div>
            ))}
          </dl>
          <h3 className="sc-onas-subtitle">Jak konsylium łączy głosy</h3>
          <ul className="sc-onas-list">
            <li><strong>Werdykt i siła</strong> — mediana głosów, czyli ocena środkowa: jeden skrajny model nie przesądza. Przy remisie wygrywa łagodniejsza ocena.</li>
            <li><strong>Techniki</strong> — do diagnozy trafia tylko technika wskazana przez co najmniej dwóch specjalistów, zawsze z dosłownym cytatem z wpisu.</li>
            <li><strong>Kworum</strong> — diagnoza powstaje tylko wtedy, gdy wypowie się co najmniej trzech specjalistów; oceny jednego czy dwóch modeli nie publikujemy.</li>
            <li><strong>Cały wpis</strong> — specjaliści dostają tekst, opisy zdjęć i grafik (także tekst na nich) oraz tytuły i opisy stron, do których prowadzą linki.</li>
            <li>
              <strong>Jawność</strong> — pod każdą diagnozą pokazujemy skład konsylium, głos każdego specjalisty, zgodność, uwagi ordynatora i to, czy wzywano
              płatnego konsultanta.
            </li>
          </ul>
          <p className="sc-onas-callout">
            Nie znamy innego serwisu, w którym wypowiedzi polityków ocenia rada niezależnych modeli AI różnych firm — z jawnym głosem każdego z nich.
          </p>
        </Section>

        <Section id="zasady" index={7} kicker="Zasady" title="AI ocenia, człowiek nie poprawia">
          <ul className="sc-onas-list">
            <li>
              <strong>Automatycznie.</strong> O wyborze wpisów, wywiadu dnia i o treści diagnoz decyduje AI. Zespół nie poprawia ani nie wybiera diagnoz — może je
              jedynie ukryć w całości po uzasadnionym zgłoszeniu prawnym.
            </li>
            <li><strong>Ta sama miara.</strong> Rządzący i opozycja, media z każdej strony — te same instrukcje i te same kryteria, zawsze obok siebie.</li>
            <li><strong>Jawnie.</strong> Każda diagnoza ma etykietę AI, nazwę modelu i wersję instrukcji, a pod nią — głosy konsylium.</li>
            <li>
              <strong>Cytat i źródło.</strong> Każda technika ma dosłowny cytat. Twierdzenia o faktach sprawdzamy w wyszukiwarce — bez źródła są oznaczone jako
              „nie do sprawdzenia”.
            </li>
            <li><strong>Cały wpis.</strong> Oceniamy tekst, zdjęcia i grafiki (także tekst na nich) oraz strony, do których prowadzą linki.</li>
            <li className="sc-onas-planned">
              <StatusTag status="planowane" /> <strong>Prawo do odpowiedzi.</strong> Polityk albo redakcja zgłasza zastrzeżenie z dowodem, a AI rozpatruje diagnozę
              ponownie — publicznie, pod diagnozą.
            </li>
            <li className="sc-onas-planned">
              <StatusTag status="planowane" /> <strong>Rejestr błędów.</strong> Diagnoza, która okaże się błędna, nie znika — zostaje z adnotacją, co i dlaczego
              się zmieniło.
            </li>
          </ul>
          <div className="sc-onas-rules">
            <div>
              <h3>Co robimy?</h3>
              <ul className="sc-onas-list is-yes">
                <li>pokazujemy źródło, datę i link do oryginału przy każdym materiale</li>
                <li>oceniamy przekazy wszystkich stron według tych samych zasad</li>
                <li>oznaczamy każdą treść przygotowaną przez AI</li>
                <li>gdy czegoś nie wiemy, niczego nie zmyślamy — wskazujemy brak danych</li>
              </ul>
            </div>
            <div>
              <h3>Czego nie robimy?</h3>
              <ul className="sc-onas-list is-no">
                <li>nie oceniamy osób ani ich poglądów</li>
                <li>nie uznajemy twierdzeń za fałszywe bez źródła</li>
                <li>nie poprawiamy diagnoz AI — publikujemy je z etykietą AI albo wcale</li>
                <li>nie piszemy własnych wiadomości i bez zgody wydawcy nie kopiujemy pełnych tekstów</li>
                <li>nie obchodzimy zabezpieczeń, limitów ani płatnego dostępu</li>
                <li>nie przyjmujemy wpłat od partii, polityków ani ich fundacji</li>
              </ul>
            </div>
          </div>
        </Section>

        <Section id="dla-redakcji" index={8} kicker="Współpraca" title="Dla dziennikarzy i redakcji">
          <div className="sc-onas-prose">
            <p>
              Jeśli trafili Państwo tutaj z naszej wiadomości — dziękujemy za poświęcony czas. Zapraszamy redakcje i poszczególnych dziennikarzy do prowadzenia
              autoryzowanych nitek. Wszelkie materiały mediów pobieramy wyłącznie za zgodą wydawcy.
            </p>
          </div>
          <ContextThreadExample />
          <h3 className="sc-onas-subtitle">Zgoda na odczyt RSS — co to oznacza w praktyce</h3>
          <dl className="sc-onas-scope">
            {PUBLISHER_SCOPE.map(([term, text]) => (
              <div key={term}>
                <dt>{term}</dt>
                <dd>{text}</dd>
              </div>
            ))}
          </dl>
          <div className="sc-onas-prose">
            <p>Chętnie uwzględnimy wymagany sposób oznaczania źródła i limity techniczne.</p>
          </div>
          <div className="sc-onas-prose">
            <p>
              <a className="sc-onas-mail" href={`mailto:${SOURCES_EMAIL}`}>
                Napisz do nas: {SOURCES_EMAIL}
              </a>
            </p>
          </div>
        </Section>

        <Section id="fazy" index={9} kicker="Rozwój" title="Trzy fazy projektu">
          <p className="sc-onas-prose">Przy każdej funkcji i technologii piszemy wprost, w jakim jest stanie — nie przedstawiamy planów jako czegoś, co już działa.</p>
          <dl className="sc-onas-legend" aria-label="Oznaczenia stanu">
            {STATUS_HELP.map(([status, help]) => (
              <div key={status}>
                <dt>
                  <StatusTag status={status} />
                </dt>
                <dd>{help}</dd>
              </div>
            ))}
          </dl>
          <ol className="sc-onas-phases">
            {PHASES.map((phase) => (
              <li key={phase.id} className="sc-onas-phase" data-current={phase.current || undefined} aria-labelledby={`${phase.id}-title`}>
                <p className="sc-onas-phase__status">{phase.status}</p>
                <h3 id={`${phase.id}-title`}>{phase.title}</h3>
                <p>{phase.lead}</p>
                {phase.id === 'faza-3' ? <p><a href={SUPPORT_LINKS.phase3} target="_blank" rel="noopener noreferrer">Zbieramy na nią tutaj: zrzutka.pl — cel 30 000 zł →</a></p> : null}
                <ul className="sc-onas-tagged">
                  {phase.features.map((feature) => (
                    <li key={feature.text}>
                      <StatusTag status={feature.status} />
                      <span>{feature.text}</span>
                    </li>
                  ))}
                </ul>
                <details className="sc-onas-tech">
                <summary>Technologia — dla dociekliwych</summary>
                <dl className="sc-onas-stack">
                  {phase.stack.map((group) => (
                    <div key={group.group}>
                      <dt>{group.group}</dt>
                      <dd>
                        <ul className="sc-onas-tagged">
                          {group.items.map((item) => (
                            <li key={item.name}>
                              <StatusTag status={item.status} />
                              <span>
                                <strong>{item.name}</strong>
                                {item.note ? ` — ${item.note}` : null}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </dd>
                    </div>
                  ))}
                </dl>
                </details>
              </li>
            ))}
          </ol>
        </Section>

        <Section id="wsparcie" index={10} kicker="Utrzymanie i kontakt" title="Niezależni — utrzymują nas czytelnicy">
          <div className="sc-onas-prose">
            <p>
              spin.clinic korzysta z płatnych usług: oficjalnego API X, modeli AI, które sprawdzają fakty i konsultują sporne diagnozy, i serwera, na którym działa baza.
              Wszystko, co się da, robimy w ramach darmowych limitów. Nie mamy reklam ani sponsorów, którzy mogliby wpływać na treść, i nie przyjmujemy
              wpłat od partii, polityków ani ich fundacji. Wsparcie nigdy nie daje wpływu na diagnozy.
            </p>
            <p>Na stronie Wsparcie pokazujemy jawnie, ile kosztuje utrzymanie i na co zbieramy. Każda wpłata to kolejne sprawdzone wypowiedzi i źródła.</p>
            <p>
              <Link className="sc-onas-mail" href="/wsparcie">Wspomóż projekt</Link>
            </p>
          </div>
          <h3 className="sc-onas-subtitle">Kontakt</h3>
          <dl className="sc-onas-contacts" aria-label="Kontakt">
            {CONTACTS.map((contact) => (
              <div key={contact.email}>
                <dt>
                  <a href={`mailto:${contact.email}`}>{contact.email}</a>
                </dt>
                <dd>{contact.purpose}</dd>
              </div>
            ))}
          </dl>
          <p className="sc-onas-operator">Operator serwisu: {OPERATOR}.</p>
          <p className="sc-onas-updated">
            Ostatnia zmiana opisu: <time dateTime={LAST_UPDATED.iso}>{LAST_UPDATED.label}</time> · <Link href="/zrodla">Źródła</Link> ·{' '}
            <Link href="/zasady-korzystania">Zasady korzystania</Link> · <Link href="/polityka-prywatnosci">Prywatność i cookies</Link>
          </p>
        </Section>

      </article>
    </div>
  );
}
