import Link from 'next/link';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { CopyBlock } from './CopyBlock';

export const metadata: Metadata = {
  title: 'O nas — spin.clinic',
  description:
    'spin.clinic pokazuje chwyty, nie werdykty: Dr. Spin (AI) rozkłada przekazy polityków i mediów na czynniki pierwsze — obie strony tą samą miarą, automatycznie, ze źródłami.',
  alternates: { canonical: '/o-nas' },
};

/** Data ostatniej zmiany opisu — aktualizować przy każdej zmianie treści tej strony. */
const LAST_UPDATED = { iso: '2026-09-27', label: '27 września 2026' };

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
  { id: 'klinika', label: 'Jak działa Dr. Spin' },
  { id: 'zasady', label: 'Zasady' },
  { id: 'czym-nie-jestesmy', label: 'Czym nie jesteśmy' },
  { id: 'pojecia', label: 'Pojęcia' },
  { id: 'fazy', label: 'Trzy fazy' },
  { id: 'wsparcie', label: 'Utrzymanie' },
  { id: 'dla-redakcji', label: 'Dla redakcji i wydawców' },
];

const PUBLISHER_TERMS = [
  'co pobieramy    tytuł, autor, data publikacji, link, nazwa źródła',
  'skąd            wskazany kanał RSS albo wskazane strony publiczne',
  'tempo           co najmniej 3 s między zapytaniami, uzgodniony limit dzienny',
  'czego nie       pełnych tekstów, zdjęć ani kopii artykułów;',
  '                nie trenujemy na nich modeli AI',
  'czytelnik       widzi box ze źródłem, a po kliknięciu trafia do oryginału',
  'zgoda           brak odpowiedzi nie jest zgodą — źródło zostaje wyłączone',
  'rezygnacja      wystarczy wiadomość, a wyłączymy źródło',
  `kontakt         ${SOURCES_EMAIL}`,
].join('\n');

const PARTS = [
  { href: '/', name: 'Wiadomości', status: 'działa · beta', text: 'Wiadomości mediów, instytucji publicznych i oficjalnych kanałów wideo. Każdy materiał to box ze źródłem, datą i linkiem do oryginału — w Najnowszych, na paskach i w Bazie z wyszukiwarką.' },
  { href: '/klinika', name: 'Klinika', status: 'działa · beta', text: 'Dr. Spin (AI) ocenia posty polityków z X i najgłośniejszy wywiad dnia — także warsztat prowadzącego. Techniki perswazji z cytatami, twierdzenia ze źródłami. Rządzący i opozycja tą samą miarą.' },
  { href: '#fazy', name: 'Nitki', status: 'faza II', text: 'Miejsce dla czytelników: wyjaśniasz spin sam — układasz nitkę kontekstową z materiałów z naszej Bazy albo dodanych przez link, z reakcjami i komentarzami.' },
];

/** Droga posta do diagnozy — cztery kroki zamiast schematu rysowanego znakami. */
const CLINIC_STEPS = [
  { title: 'Strażnik', tech: 'Groq · NVIDIA NIM', text: 'Darmowe, otwarte modele czytają każdy nowy post i oceniają w skali 0–100, czy jest w nim coś do sprawdzenia. Życzenia i zapowiedzi odpadają od razu.' },
  { title: 'Diagnoza', tech: 'Claude (Anthropic) · wyszukiwanie w sieci', text: 'Posty warte sprawdzenia — najwyżej ocenione, w dziennym budżecie — trafiają do Dr. Spina: techniki perswazji z dosłownymi cytatami, twierdzenia porównane ze źródłami.' },
  { title: 'Publikacja', tech: 'automatycznie · etykieta AI', text: 'Diagnoza trafia na stronę sama, oznaczona jako wygenerowana przez AI. Nikt nie poprawia jej treści — ocena należy do modelu i źródeł.' },
  { title: 'Wątek na X', tech: 'udostępnianie', text: 'Każdą diagnozę można wkleić na X jako wątek 1/N: podsumowanie z linkiem, techniki i źródła — także jako odpowiedź pod wpisem polityka.' },
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
      { text: 'Klinika spinu: strażnik postów, diagnozy AI, spin dnia i najnowszy spin, waga spinu, liczniki przy każdym polityku', status: 'beta' },
      { text: 'przekaz dnia obu obozów z pełną analizą, postami źródłowymi i archiwum', status: 'beta' },
      { text: 'wywiad dnia wybierany automatycznie z kilkudziesięciu kanałów i całego YouTube — ocena gościa i warsztatu prowadzącego, z cytatami i minutą nagrania', status: 'beta' },
      { text: 'filmy z oficjalnych kanałów YouTube instytucji, partii i mediów — z doborem materiałów z różnych źródeł (pluralizm)', status: 'beta' },
      { text: 'udostępnianie diagnozy jako wątku na X; rejestr osób publicznych z oficjalnymi kontami X', status: 'beta' },
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
        { name: 'API X (oficjalne, płatne)', note: 'posty z kont potwierdzonych dowodem', status: 'działa' },
        { name: 'YouTube Data API', note: 'oficjalne kanały instytucji, partii i mediów (z dowodem na stronie źródła) oraz automatyczny wybór wywiadu dnia', status: 'działa' },
      ] },
      { group: 'AI w Klinice', items: [
        { name: 'Groq', note: 'strażnik: otwarty model ocenia każdy post 0–100 i pisze przekazy dnia, bez kosztów', status: 'beta' },
        { name: 'NVIDIA NIM', note: 'zapasowy model, gdy Groq nie odpowiada', status: 'beta' },
        { name: 'Claude Sonnet (Anthropic) z wyszukiwaniem w sieci', note: 'diagnoza: techniki z cytatami, twierdzenia ze źródłami', status: 'beta' },
        { name: 'Gemini (Google)', note: 'wywiad dnia: transkrypcja publicznego filmu z YouTube po samym linku, z minutami — bez pobierania nagrania', status: 'beta' },
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
      { text: 'autoryzowane nitki dziennikarzy — prowadzone pod nazwiskiem, z linkiem do redakcji', status: 'planowane' },
      { text: 'dodawanie materiału przez link — zapisujemy tytuł, adres i źródło, bez treści i zdjęć; ten sam link to jeden box, bez duplikatów', status: 'planowane' },
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
    lead: 'Zamiast zestawu zewnętrznych usług — własny serwer i otwarty model, który czyta posty i stawia diagnozy.',
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
            Spin to efekt tej pracy — informacja podana tak, żeby działała na korzyść nadawcy. <strong>spin.clinic</strong> jest miejscem, w którym spin traci przewagę:
            każdą informację widać ze źródłem, datą i kontekstem.
          </p>
        </section>

        <Section id="o-nas" index={2} kicker="Dlaczego" title="Pokazujemy chwyty, nie werdykty" level={1}>
          <div className="sc-onas-prose">
            <p className="sc-onas-lead">
              Samo prostowanie faktów rzadko zmienia czyjeś zdanie — często je utwardza. Skuteczniej działa pokazanie, jak zbudowany jest przekaz: fałszywa
              alternatywa, przypisywanie intencji, wybiórcze dane. Nikt nie lubi być manipulowany — także przez swoich.
            </p>
            <p>
              Dlatego Dr. Spin nie ogłasza, kto ma rację. Rozkłada wypowiedzi polityków i przekazy mediów na czynniki pierwsze: techniki z dosłownymi cytatami,
              twierdzenia ze źródłami — rządzących i opozycję obok siebie, tą samą miarą. Nie musisz zmieniać poglądów. Wystarczy, że zaczniesz widzieć chwyty.
            </p>
            <p>
              Wszystko dzieje się automatycznie. Diagnoz nie pisze ani nie poprawia człowiek — ocenia AI według jawnych zasad, bez sympatii i antypatii.
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
        </Section>

        <Section id="klinika" index={3} kicker="Klinika spinu" title="Jak działa Dr. Spin">
          <div className="sc-onas-prose">
            <p>
              Czytamy wyłącznie oficjalne konta X polityków i partii, potwierdzone dowodem (np. rejestry Sejmu, Senatu i Parlamentu Europejskiego, Wikidata,
              zgodność nazwiska) — pełną listę publikujemy na dole Kliniki, a brakujące konto można zgłosić. Każdy nowy post przechodzi cztery kroki. Płacimy tylko
              za diagnozy postów, które naprawdę warto sprawdzić.
            </p>
          </div>
          <ol className="sc-onas-flow" aria-label="Droga posta do diagnozy">
            {CLINIC_STEPS.map((step, index) => (
              <li key={step.title}>
                <span className="sc-onas-flow__num">{String(index + 1).padStart(2, '0')}</span>
                <h3>{step.title}</h3>
                <p className="sc-onas-flow__tech">{step.tech}</p>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
          <ul className="sc-onas-list">
            <li>Te same zasady dla każdej strony. Oceniamy komunikat, nie człowieka ani jego poglądy.</li>
            <li>Każda technika ma dosłowny cytat. Twierdzenia o faktach model sprawdza w wyszukiwarce — bez źródła są oznaczone jako „nie do sprawdzenia”.</li>
            <li>
              Publikacja jest automatyczna, z etykietą AI, nazwą modelu i wersją instrukcji. Nikt nie poprawia treści diagnoz; możemy je tylko ukryć w całości
              po uzasadnionym zgłoszeniu prawnym na admin@spin.clinic.
            </li>
            <li>Spin dnia to diagnoza z najwyższą siłą z dzisiaj. Waga porównuje udział postów ze spinem po każdej stronie, nie ich liczbę.</li>
            <li>
              Przekaz dnia: darmowe modele streszczają posty obozu (co najmniej trzech kont) pięć razy dziennie. Po kliknięciu — pełna analiza, lista postów źródłowych
              i archiwum.
            </li>
            <li>
              Wywiad dnia: co rano automat wybiera najgłośniejszą rozmowę z politykiem z poprzedniego dnia — z kilkudziesięciu kanałów stacji, redakcji
              i dziennikarzy oraz z całego YouTube — i sprawdza, czy to rozmowa, a nie monolog. Gemini przygotowuje transkrypcję z minutami, Dr. Spin ocenia
              gościa i warsztat prowadzącego tą samą skalą.
            </li>
            <li>Każdą diagnozę udostępnisz na X jako wątek — pierwszy wpis prowadzi do pełnej diagnozy.</li>
          </ul>
          <p className="sc-onas-callout">
            Dr. Spin nie ogłasza prawdy i nie zastępuje dziennikarza. Pokazuje, jak zbudowany jest przekaz i co mówią źródła — ocena należy do Ciebie.
          </p>
        </Section>

        <Section id="zasady" index={4} kicker="Zasady" title="AI ocenia, człowiek nie poprawia">
          <ul className="sc-onas-list">
            <li>
              <strong>Automatycznie.</strong> Wybór postów, wywiadu dnia i treść diagnoz należą do AI. Zespół nie poprawia ani nie wybiera diagnoz — może je tylko
              ukryć w całości po uzasadnionym zgłoszeniu prawnym.
            </li>
            <li><strong>Ta sama miara.</strong> Rządzący i opozycja, media z każdej strony — te same instrukcje, te same kryteria, obok siebie.</li>
            <li><strong>Jawnie.</strong> Każda diagnoza ma etykietę AI, nazwę modelu i wersję instrukcji; każda technika — cytat, każde twierdzenie — źródło.</li>
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
              <h3>Robimy</h3>
              <ul className="sc-onas-list is-yes">
                <li>pokazujemy źródło, datę i link do oryginału przy każdym materiale</li>
                <li>oceniamy przekazy wszystkich stron według tych samych zasad</li>
                <li>oznaczamy każdą treść przygotowaną przez AI</li>
                <li>pokazujemy braki danych jako braki, bez zgadywania</li>
              </ul>
            </div>
            <div>
              <h3>Nie robimy</h3>
              <ul className="sc-onas-list is-no">
                <li>nie oceniamy osób ani ich poglądów</li>
                <li>nie uznajemy twierdzeń za fałszywe bez źródła</li>
                <li>nie poprawiamy diagnoz AI — publikujemy je z etykietą AI albo wcale</li>
                <li>nie piszemy własnych newsów i nie kopiujemy pełnych tekstów bez zgody wydawcy</li>
                <li>nie obchodzimy blokad, limitów ani płatnych dostępów</li>
                <li>nie przyjmujemy wpłat od partii, polityków ani ich fundacji</li>
              </ul>
            </div>
          </div>
        </Section>

        <Section id="czym-nie-jestesmy" index={5} kicker="Czym nie jesteśmy" title="Nie fact-check, nie czat z AI">
          <dl className="sc-onas-terms">
            <div>
              <dt>Nie fact-checking „prawda — fałsz”</dt>
              <dd>
                Nie wydajemy wyroków. Prawdziwe zdanie też może być spinem — podanym wybiórczo, bez punktu odniesienia albo z przypisaną intencją. Pokazujemy, jak
                zbudowany jest przekaz.
              </dd>
            </div>
            <div>
              <dt>Nie czat z AI</dt>
              <dd>
                Czat odpowiada, gdy ktoś sam zapyta — o jeden wpis, bez pamięci i nie zawsze z prawdziwym źródłem. Dr. Spin pracuje z urzędu, codziennie, na
                instrukcjach dopracowanych do tej jednej pracy: najpierw szuka w naszej bazie mediów i instytucji, potem w sieci. Diagnozy zostają w archiwum, więc
                widać porównanie stron i historię każdego polityka.
              </dd>
            </div>
            <div>
              <dt>Nie uwagi społeczności</dt>
              <dd>
                Notatka pod wpisem pojawia się dopiero po zgodzie głosujących z różnych stron — przy większości wpisów polityków nigdy albo po kilku dniach.
                Dr. Spin ocenia w ciągu godzin, przy każdym obserwowanym polityku.
              </dd>
            </div>
          </dl>
        </Section>

        <Section id="pojecia" index={6} kicker="Pojęcia" title="Box, Twoje wiadomości, nitka kontekstowa">
          <dl className="sc-onas-terms">
            <div>
              <dt>Box</dt>
              <dd>
                Karta jednego materiału — artykułu, dokumentu, wywiadu, nagrania, wpisu. Zawsze ze źródłem, datą i linkiem do oryginału. Po otwarciu pokazuje oś czasu
                powiązanych materiałów.
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
                Jeden box na początku, a za nim — w kolejności publikacji — materiały, które go dopełniają, potwierdzają albo podważają. Dziś układa je zespół jako Dr. Spin;
                w fazie II dostaną to czytelnicy.
              </dd>
            </div>
            <div>
              <dt>Diagnoza spinu</dt>
              <dd>
                Ocena Dr. Spina: werdykt (spin, częściowy spin, bez spinu, nie da się ocenić), siła 0–100, techniki z dosłownymi cytatami i twierdzenia
                porównane ze źródłami. Z czasem dowodami będą boxy z naszej Bazy.
              </dd>
            </div>
          </dl>
        </Section>

        <Section id="fazy" index={7} kicker="Rozwój" title="Trzy fazy projektu">
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

        <Section id="wsparcie" index={8} kicker="Utrzymanie" title="Niezależni — utrzymują nas czytelnicy">
          <div className="sc-onas-prose">
            <p>
              spin.clinic korzysta z płatnych usług: oficjalnego API X, modelu AI, który stawia diagnozy, i serwera, na którym działa baza.
              Wszystko, co da się zrobić na darmowych limitach, robimy na nich. Nie mamy reklam ani sponsorów, którzy mogliby wpływać na treść, i nie przyjmujemy
              wpłat od partii, polityków ani ich fundacji. Wsparcie nigdy nie daje wpływu na diagnozy.
            </p>
            <p>Na stronie Wsparcie pokazujemy jawnie, ile kosztuje utrzymanie i na co zbieramy. Każda wpłata to kolejne sprawdzone wypowiedzi i źródła.</p>
            <p>
              <Link className="sc-onas-mail" href="/wsparcie">Wesprzyj spin.clinic</Link>
            </p>
          </div>
        </Section>

        <Section id="dla-redakcji" index={9} kicker="Współpraca" title="Dla redakcji i wydawców">
          <div className="sc-onas-prose">
            <p>
              Jeśli trafili Państwo tutaj z naszej wiadomości — dziękujemy za poświęcony czas. Materiały mediów pobieramy wyłącznie za zgodą wydawcy. Poniżej krótko, co to
              oznacza w praktyce.
            </p>
          </div>
          <CopyBlock label="zakres dostępu — do skopiowania" text={PUBLISHER_TERMS} />
          <div className="sc-onas-prose">
            <p>Chętnie uwzględnimy wymagany sposób oznaczania źródła i limity techniczne.</p>
            <p>
              <a className="sc-onas-mail" href={`mailto:${SOURCES_EMAIL}`}>
                Napisz do nas: {SOURCES_EMAIL}
              </a>
            </p>
          </div>
          <p className="sc-onas-updated">
            Ostatnia zmiana opisu: <time dateTime={LAST_UPDATED.iso}>{LAST_UPDATED.label}</time> · <Link href="/zrodla">Źródła</Link> ·{' '}
            <Link href="/zasady-korzystania">Zasady korzystania</Link> · <Link href="/polityka-prywatnosci">Prywatność i cookies</Link>
          </p>
        </Section>

      </article>
    </div>
  );
}
