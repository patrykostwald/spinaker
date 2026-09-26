import Link from 'next/link';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { CopyBlock } from './CopyBlock';

export const metadata: Metadata = {
  title: 'O nas — spin.clinic',
  description:
    'spin.clinic to agregator wiadomości ze źródłami i Klinika spinu z automatyczną diagnozą postów polityków. W kolejnej fazie — nitki kontekstowe czytelników. Jak działa, na czym jest zbudowany i co planujemy.',
  alternates: { canonical: '/o-nas' },
};

/** Data ostatniej zmiany opisu — aktualizować przy każdej zmianie treści tej strony. */
const LAST_UPDATED = { iso: '2026-09-26', label: '26 września 2026' };
/** Zmierzony koszt jednej diagnozy (Claude z wyszukiwaniem) — ten sam na stronie Wsparcie. */
const DIAGNOSIS_COST = 'ok. 0,35 USD (ok. 1,30 zł)';

const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic';
const SOURCES_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL || 'zrodla@spin.clinic';
const OPERATOR = 'iapply sp. z o.o., pl. Wolności 16, 61-739 Poznań, KRS 0001133291, NIP 7831915094, REGON 529962488';
const CONTACTS: Array<{ email: string; purpose: string }> = [
  { email: 'kontakt@spin.clinic', purpose: 'pytania o projekt, współpraca, media' },
  { email: SOURCES_EMAIL, purpose: 'źródła, zgody wydawców, zakres dostępu' },
  { email: 'admin@spin.clinic', purpose: 'sprawy techniczne, prywatność, zgłoszenia dotyczące diagnoz' },
];

const SECTIONS = [
  { id: 'spin-doctor', label: 'Spin doctor' },
  { id: 'o-nas', label: 'O nas' },
  { id: 'pojecia', label: 'Box i nitki' },
  { id: 'klinika', label: 'Klinika spinu' },
  { id: 'fazy', label: 'Fazy i technologia' },
  { id: 'wsparcie', label: 'Utrzymanie' },
  { id: 'dla-redakcji', label: 'Dla redakcji i wydawców' },
  { id: 'zasady', label: 'Zasady' },
];

const ABOUT_SNIPPET =
  `spin.clinic zbiera doniesienia mediów i materiały instytucji publicznych — zawsze ze źródłem, datą i linkiem do oryginału — ` +
  `i sprawdza przekazy polityków: każdy nowy post z ich kont na X dostaje automatyczną diagnozę spinu według tych samych zasad dla każdej strony. ` +
  `Nie piszemy własnych newsów i nie oceniamy ludzi — pokazujemy kontekst, żeby każdy mógł ocenić sam. Więcej: https://${DOMAIN}/o-nas`;

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
  { href: '/', name: 'Źródła', status: 'działa · beta', text: 'Wiadomości mediów i instytucji publicznych. Każdy materiał to box ze źródłem, datą i linkiem do oryginału — w Wiadomościach dnia, na paskach newsowych i w Bazie z wyszukiwarką.' },
  { href: '/klinika', name: 'Klinika', status: 'działa · beta', text: 'Weryfikator spinów. Czytamy posty polityków z X, a Dr. Spin rozkłada je na czynniki pierwsze i stawia diagnozę. Rządzący i opozycja obok siebie, według tych samych zasad.' },
  { href: '#fazy', name: 'Nitki', status: 'faza II', text: 'Miejsce dla czytelników: wyjaśniasz spin sam — układasz nitkę kontekstową z materiałów z naszej Bazy albo dodanych przez link, z reakcjami i komentarzami.' },
];

/** Droga posta do diagnozy — cztery kroki zamiast schematu rysowanego znakami. */
const CLINIC_STEPS = [
  { title: 'Strażnik', tech: 'Groq · NVIDIA NIM', text: 'Darmowe, otwarte modele czytają każdy nowy post i oceniają w skali 0–100, czy jest w nim coś do sprawdzenia. Życzenia i zapowiedzi odpadają od razu.' },
  { title: 'Diagnoza', tech: 'Claude (Anthropic) · wyszukiwanie w sieci', text: 'Posty warte sprawdzenia — najwyżej ocenione, w dziennym limicie — trafiają do Dr. Spina: techniki perswazji z dosłownymi cytatami, twierdzenia porównane ze źródłami.' },
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
      { text: 'baza materiałów z wyszukiwarką, paski newsowe i do pięciu własnych pasków w sekcji „Twoje wiadomości”', status: 'beta' },
      { text: 'box materiału z osią czasu i bazą powiązanych materiałów', status: 'beta' },
      { text: 'Klinika spinu: strażnik postów, automatyczne diagnozy z etykietą AI, waga spinu, przekazy dnia obu obozów, spin dnia (także na stronie głównej)', status: 'beta' },
      { text: 'udostępnianie diagnozy jako wątku na X (1/N), także w odpowiedzi pod wpisem polityka', status: 'beta' },
      { text: 'rejestr osób i stanowisk publicznych z historią funkcji i oficjalnymi kontami X', status: 'beta' },
      { text: 'paski newsowe zapisane na urządzeniu — bez zakładania konta', status: 'beta' },
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
        { name: 'YouTube Data API', note: 'oficjalne kanały jako osobny typ źródła', status: 'działa' },
      ] },
      { group: 'AI w Klinice', items: [
        { name: 'Groq', note: 'strażnik: otwarty model ocenia każdy post 0–100 i pisze przekazy dnia, bez kosztów', status: 'beta' },
        { name: 'NVIDIA NIM', note: 'zapasowy model, gdy Groq nie odpowiada', status: 'beta' },
        { name: 'Claude (Anthropic) z wyszukiwaniem w sieci', note: `diagnoza: techniki z cytatami, twierdzenia ze źródłami; ${DIAGNOSIS_COST} za diagnozę`, status: 'beta' },
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
      { text: 'napisy i transkrypcje wideo z YouTube, alerty po haśle i źródle', status: 'planowane' },
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
      { text: 'odpowiedzi oparte na naszej bazie (RAG) — każde ustalenie z boxem źródłowym', status: 'planowane' },
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

        <Section id="o-nas" index={2} kicker="O nas" title="Źródła i Klinika" level={1}>
          <div className="sc-onas-prose">
            <p className="sc-onas-lead">
              spin.clinic to agregator wiadomości ze źródłami i weryfikator spinów polityków. W kolejnej fazie dołączy trzecia część — miejsce, w którym czytelnicy
              sami wyjaśniają spin, układając nitki kontekstowe z materiałów z naszej Bazy.
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
          <div className="sc-onas-prose">
            <p>
              Nie piszemy własnych newsów, nie oceniamy ludzi i nie zastępujemy dziennikarzy. Pokazujemy, skąd pochodzi informacja, kiedy się pojawiła i co jej towarzyszyło
              — bo bez kontekstu nawet prawdziwe zdanie potrafi wprowadzić w błąd.
            </p>
          </div>
          <CopyBlock label="O spin.clinic — tekst do skopiowania" mode="text" text={ABOUT_SNIPPET} />
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

        <Section id="pojecia" index={3} kicker="Pojęcia" title="Box, Twoje wiadomości, nitka kontekstowa">
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
                To też nitka kontekstowa: post polityka i to, co go wyjaśnia. Dziś ma postać tekstu ze źródłami z wyszukiwania; w miarę rozbudowy bazy dowodami będą boxy z
                materiałami źródłowymi.
              </dd>
            </div>
          </dl>
        </Section>

        <Section id="klinika" index={4} kicker="Klinika spinu" title="Jak powstaje diagnoza">
          <div className="sc-onas-prose">
            <p>
              Czytamy wyłącznie oficjalne konta X polityków i partii, potwierdzone dowodem (np. rejestry Sejmu, Senatu i Parlamentu Europejskiego, Wikidata,
              zgodność nazwiska) — pełną listę publikujemy na dole Kliniki, a brakujące konto można zgłosić. Każdy nowy post przechodzi cztery kroki. Płacimy tylko
              za diagnozy postów, które naprawdę warto sprawdzić — {DIAGNOSIS_COST} za jedną, z dziennym limitem.
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
            <li>Każda wskazana technika ma dosłowny cytat z posta. Cytatów, których nie ma w poście, system nie publikuje.</li>
            <li>Twierdzenia o faktach model sprawdza w wyszukiwarce. Bez źródła twierdzenie zostaje oznaczone jako „nie do sprawdzenia”.</li>
            <li>
              Diagnozy publikują się automatycznie i są oznaczone jako wygenerowane przez AI, z nazwą modelu i wersją instrukcji. Nikt nie poprawia ich treści.
            </li>
            <li>
              Diagnozę możemy tylko ukryć w całości — po uzasadnionym zgłoszeniu naruszenia prawa na admin@spin.clinic. Nie zmieniamy jej werdyktu ani słów.
            </li>
            <li>Waga spinu porównuje udział postów ze spinem po każdej stronie, nie ich liczbę — strony mają różną liczbę kont.</li>
            <li>Każdą diagnozę udostępnisz na X jako wątek — pierwszy wpis mieści się w limicie znaków i prowadzi do pełnej diagnozy.</li>
          </ul>
          <p className="sc-onas-callout">
            Dr. Spin nie ogłasza prawdy i nie zastępuje dziennikarza. Pokazuje, jak zbudowany jest przekaz i co mówią źródła — ocena należy do Ciebie.
          </p>
        </Section>

        <Section id="fazy" index={5} kicker="Rozwój i technologia" title="Trzy fazy projektu">
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
              </li>
            ))}
          </ol>
        </Section>

        <Section id="wsparcie" index={6} kicker="Utrzymanie" title="Utrzymujemy to sami">
          <div className="sc-onas-prose">
            <p>
              spin.clinic korzysta z płatnych usług: oficjalnego API X, modelu AI, który stawia diagnozy ({DIAGNOSIS_COST} za jedną), i serwera, na którym działa baza.
              Na razie pokrywamy te koszty sami, bez reklam i bez sponsorów, którzy mogliby wpływać na treść. Wsparcie nigdy nie daje wpływu na diagnozy.
            </p>
            <p>Jeśli Klinika i Wiadomości są dla Ciebie przydatne, wesprzyj projekt — każda wpłata to kolejne sprawdzone posty i źródła.</p>
            <p>
              <Link className="sc-onas-mail" href="/wsparcie">Wesprzyj spin.clinic</Link>
            </p>
          </div>
        </Section>

        <Section id="dla-redakcji" index={7} kicker="Współpraca" title="Dla redakcji i wydawców">
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
        </Section>

        <Section id="zasady" index={8} kicker="Zasady" title="Co robimy, a czego nie">
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
          <p className="sc-onas-updated">
            Ostatnia zmiana opisu: <time dateTime={LAST_UPDATED.iso}>{LAST_UPDATED.label}</time> · <Link href="/zrodla">Źródła</Link> ·{' '}
            <Link href="/zasady-korzystania">Zasady korzystania</Link> · <Link href="/polityka-prywatnosci">Prywatność i cookies</Link>
          </p>
        </Section>
      </article>
    </div>
  );
}
