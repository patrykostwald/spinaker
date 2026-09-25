import Link from 'next/link';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { CopyBlock } from './CopyBlock';
import { BOX, CONTEXT_THREAD, DR_SPIN, DR_SPIN_LATER, EXPANDED, NEWS_THREAD } from './diagrams';

export const metadata: Metadata = {
  title: 'O nas — spin.clinic',
  description:
    'spin.clinic pokazuje doniesienia mediów i materiały instytucji publicznych w kontekście: ze źródłem, datą i linkiem do oryginału, na osi czasu. Czym są boxy, nitki newsowe i kontekstowe, Dr. Spin i trzy fazy projektu.',
  alternates: { canonical: '/o-nas' },
};

/** Data ostatniej zmiany opisu — aktualizować przy każdej zmianie treści tej strony. */
const LAST_UPDATED = { iso: '2026-09-25', label: '25 września 2026' };

const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'spin.clinic';
const SOURCES_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL || 'zrodla@spin.clinic';
const CONTACTS: Array<{ email: string; purpose: string }> = [
  { email: 'kontakt@spin.clinic', purpose: 'pytania o projekt, współpraca, media' },
  { email: SOURCES_EMAIL, purpose: 'źródła, zgody wydawców, zakres dostępu' },
  { email: 'admin@spin.clinic', purpose: 'sprawy techniczne i administracyjne, błędy serwisu' },
];

const SECTIONS = [
  { id: 'spin-doctor', label: 'Spin doctor' },
  { id: 'o-nas', label: 'O nas' },
  { id: 'fazy', label: 'Fazy i technologia' },
  { id: 'box', label: 'Box' },
  { id: 'po-kliknieciu', label: 'Po otwarciu boxa' },
  { id: 'nitki-newsowe', label: 'Nitka newsowa' },
  { id: 'nitki-kontekstowe', label: 'Nitka kontekstowa' },
  { id: 'dr-spin', label: 'Dr. Spin' },
  { id: 'dla-redakcji', label: 'Dla redakcji i wydawców' },
  { id: 'zasady', label: 'Czego nie robimy' },
];

const ABOUT_SNIPPET =
  `spin.clinic to serwis, który pokazuje doniesienia mediów i materiały instytucji publicznych w kontekście: zawsze ze źródłem, datą i linkiem do oryginału, na osi czasu obok tego, co ukazało się wcześniej i później. ` +
  `Nie piszemy własnych newsów i nie rozstrzygamy, co jest prawdą — dajemy pełniejszy obraz, żeby każdy mógł ocenić sam. Więcej: https://${DOMAIN}/o-nas`;

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
  featuresLabel: string;
  features: Array<{ text: string; status: Status }>;
  stack: Array<{ group: string; items: TechItem[] }>;
  note: [string, string];
  current?: boolean;
};

const PHASES: Phase[] = [
  {
    id: 'faza-1',
    status: 'Faza I · działa dzisiaj',
    title: 'Baza, boxy i rejestry',
    lead: 'To, co działa już dziś. Funkcje oznaczone jako „beta” są dostępne dla czytelników, ale wciąż je rozwijamy.',
    featuresLabel: 'Funkcje',
    features: [
      { text: 'wyszukiwanie materiałów w bazie, filtrowanie po kategorii, źródle i haśle', status: 'beta' },
      { text: 'publiczne boxy materiałów i kontekst materiału: oś czasu powiązanych i baza powiązanych', status: 'beta' },
      { text: 'pasek newsowy i do pięciu nitek użytkownika — zapisane widoki na urządzeniu', status: 'beta' },
      { text: 'rejestr osób publicznych i stanowisk publicznych, z historią sprawowania funkcji i osią czasu osoby', status: 'beta' },
      { text: 'powiązania osób, organizacji, źródeł i materiałów — wyłącznie potwierdzone dowodami', status: 'beta' },
      { text: 'Wiadomości dnia, sekcje tematyczne i temat dnia', status: 'beta' },
      { text: 'Dr. Spin — narzędzie zespołu do porządkowania kontekstu i dowodów', status: 'beta' },
      { text: 'import i audyt źródeł, ręczne zatwierdzanie dowodów', status: 'beta' },
    ],
    stack: [
      {
        group: 'Frontend',
        items: [
          { name: 'Next.js 14 · React · TypeScript', status: 'działa' },
          { name: 'Tailwind CSS 3.4 i wspólny pakiet komponentów', note: 'motyw jasny i ciemny, układ na telefon i komputer', status: 'działa' },
          { name: 'TanStack Query', note: 'pobieranie i przechowywanie danych w przeglądarce', status: 'działa' },
        ],
      },
      {
        group: 'Backend',
        items: [
          { name: 'Python · Django 5 · Django REST Framework', note: 'materiały, źródła, konta, nitki, osoby i stanowiska publiczne, dowody, relacje, historia zmian', status: 'działa' },
          { name: 'Django Admin', note: 'panel administracyjny', status: 'działa' },
          { name: 'OpenAPI (drf-spectacular)', note: 'publiczny opis API', status: 'działa' },
        ],
      },
      {
        group: 'Dane i zadania w tle',
        items: [
          { name: 'PostgreSQL 15', note: 'baza produkcyjna; SQLite wyłącznie do lokalnych testów', status: 'działa' },
          { name: 'Redis 7 · Celery Worker · Celery Beat', note: 'pobieranie i kontrole według harmonogramu', status: 'działa' },
          { name: 'importery źródeł fail-closed', note: 'bez zatwierdzonego kanału i zakresu dostępu źródło nie jest pobierane', status: 'działa' },
        ],
      },
      {
        group: 'Infrastruktura',
        items: [
          { name: 'Docker · Docker Compose · VPS z Ubuntu', note: 'na zewnątrz tylko porty HTTP i HTTPS', status: 'działa' },
          { name: 'Caddy', note: 'reverse proxy i HTTPS z automatycznym certyfikatem', status: 'działa' },
          { name: 'GitHub · GitHub Actions', note: 'testy i ręczne wdrożenie wybranej wersji', status: 'działa' },
        ],
      },
      {
        group: 'Źródła i rejestry',
        items: [
          { name: 'oficjalne API (Sejm, ELI) · RSS · BIP', status: 'działa' },
          { name: 'oficjalne kanały YouTube', note: 'osobny, weryfikowany typ źródła', status: 'działa' },
          { name: 'rejestr stanowisk publicznych', note: 'obecne i byłe osoby, historia zmian', status: 'działa' },
          { name: 'dowody kont X i kolejka ręcznej weryfikacji', status: 'działa' },
        ],
      },
    ],
    note: ['Zasada', 'każde źródło ma zapisane warunki wykorzystania, kanał dostępu, status techniczny i prawny oraz historię audytu. Rozdzielamy dane potwierdzone, kandydatury, źródła czekające na kontakt i źródła nieaktywne.'],
    current: true,
  },
  {
    id: 'faza-2',
    status: 'Faza II · najbliższy etap',
    title: 'Szerszy kontekst, konta i powiadomienia',
    lead: 'Wdrażamy to etapami. Część elementów jest już przygotowana w kodzie, ale nie działa jeszcze dla czytelników.',
    featuresLabel: 'Co dochodzi',
    features: [
      { text: 'napisy i transkrypcje materiałów wideo z YouTube — z wyszukiwaniem w ich treści', status: 'planowane' },
      { text: 'lepsze wykrywanie powiązań między materiałami i rozbudowane osie czasu', status: 'planowane' },
      { text: 'alerty po haśle, źródle i temacie — w serwisie i e-mailem', status: 'planowane' },
      { text: 'konta: własne nitki kontekstowe, reakcje i komentarze z moderacją', status: 'planowane' },
      { text: 'kolejka moderacji i zatwierdzanie treści przed publikacją', status: 'planowane' },
      { text: 'raporty jakości importu: duplikaty, błędne daty, puste materiały, błędy techniczne', status: 'planowane' },
      { text: 'dalsze uzupełnianie rejestru stanowisk publicznych', status: 'planowane' },
    ],
    stack: [
      {
        group: 'Integracje',
        items: [
          { name: 'YouTube Data API', note: 'napisy i transkrypcje', status: 'planowane' },
          { name: 'API X', note: 'pilotaż płatnego dostępu; konta potwierdzane wyłącznie oficjalnymi dowodami', status: 'wymaga potwierdzenia' },
          { name: 'powiadomienia w serwisie i e-mail', status: 'planowane' },
        ],
      },
    ],
    note: ['Nadal bez', 'automatycznej publikacji i automatycznych ocen.'],
  },
  {
    id: 'faza-3',
    status: 'Faza III · planowane kolejne fazy',
    title: 'Wyszukiwanie wspomagane AI i dalszy rozwój',
    lead: 'AI ma być narzędziem zespołu, nie autorem. Model pracuje wyłącznie na rekordach z naszej bazy i na ich dowodach.',
    featuresLabel: 'Założenia',
    features: [
      { text: 'wybór ograniczonej liczby powiązanych materiałów z realnej bazy', status: 'planowane' },
      { text: 'odpowiedzi oparte wyłącznie na istniejących rekordach — bez zmyślonych linków i dopowiadania faktów', status: 'planowane' },
      { text: 'zapis modelu, wersji instrukcji, kosztu, pewności, danych wejściowych i decyzji redaktora — z osobnym audytem jakości', status: 'planowane' },
      { text: 'później: aplikacja instalowana z przeglądarki (PWA) i powiadomienia push, rozbudowane mapy relacji, indeksowanie dokumentów BIP, większe archiwum, narzędzia do moderacji', status: 'planowane' },
    ],
    stack: [
      {
        group: 'AI',
        items: [
          { name: 'wspólny adapter modeli OpenAI i Mistral', note: 'przygotowany w kodzie, domyślnie wyłączony', status: 'wymaga potwierdzenia' },
          { name: 'NVIDIA NIM · Groq', note: 'pilotaże szkiców nitek, domyślnie wyłączone', status: 'wymaga potwierdzenia' },
          { name: 'RAG', note: 'odpowiedzi z cytowaniem materiałów z bazy', status: 'planowane' },
          { name: 'Qdrant', note: 'kandydat do wyszukiwania wektorowego — po porównaniu z wyszukiwaniem w PostgreSQL', status: 'wymaga potwierdzenia' },
          { name: 'własny indeks semantyczny i model lokalny', note: 'dopiero po pomiarze sprzętu, kosztu, czasu i jakości', status: 'wymaga potwierdzenia' },
        ],
      },
      {
        group: 'Później',
        items: [
          { name: 'Web Push (VAPID)', note: 'powiadomienia w przeglądarce', status: 'planowane' },
          { name: 'aplikacje mobilne', note: 'dopiero po potwierdzeniu potrzeb czytelników', status: 'wymaga potwierdzenia' },
        ],
      },
    ],
    note: ['Stan', 'żaden model AI nie publikuje dziś niczego w serwisie, a własny model nie jest warunkiem startu. Supabase rozważaliśmy we wcześniejszej architekturze — obecna wersja działa na Django i PostgreSQL.'],
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
        {/* 01 — definicja na samej górze */}
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
            każdą informację widać ze źródłem, datą i tym, co ukazało się przed nią i po niej.
          </p>
        </section>

        <Section id="o-nas" index={2} kicker="O nas" title="Kontekst zamiast werdyktu" level={1}>
          <div className="sc-onas-prose">
            <p className="sc-onas-lead">
              spin.clinic porządkuje doniesienia mediów i materiały instytucji publicznych tak, żeby od razu było widać, skąd pochodzi informacja, kiedy się pojawiła i co jej
              towarzyszyło. Każdy materiał ma u nas źródło, datę i link do oryginału.
            </p>
            <p>
              Nie piszemy własnych newsów i nie ogłaszamy, co jest prawdą. Zestawiamy materiały na osi czasu — dokument, komunikat, wywiad, artykuł — tak, żeby czytelnik sam
              zobaczył, jak rozwijała się sprawa i kto co powiedział pierwszy.
            </p>
            <p>Robimy to, bo w zalewie przekazów najłatwiej zgubić właśnie kontekst. A bez kontekstu nawet prawdziwe zdanie potrafi wprowadzić w błąd.</p>
            <p className="sc-onas-status">
              <span>Stan projektu</span> wersja beta (faza I). Katalog źródeł rośnie z każdym tygodniem — media dołączają po zgodzie wydawców.
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
          <p className="sc-onas-operator">Operator serwisu: iApply sp. z o.o., pl. Wolności 16, 61-739 Poznań, KRS 0001133291, NIP 7831915094, REGON 529962488.</p>
        </Section>

        <Section id="fazy" index={3} kicker="Rozwój i technologia" title="Trzy fazy projektu">
          <p className="sc-onas-prose">
            Rozwijamy spin.clinic etapami. Przy każdej funkcji i technologii piszemy wprost, w jakim jest stanie — nie przedstawiamy planów jako czegoś, co już działa.
          </p>
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
                <h4 className="sc-onas-phase__label">{phase.featuresLabel}</h4>
                <ul className="sc-onas-tagged">
                  {phase.features.map((feature) => (
                    <li key={feature.text}>
                      <StatusTag status={feature.status} />
                      <span>{feature.text}</span>
                    </li>
                  ))}
                </ul>
                <h4 className="sc-onas-phase__label">Technologia</h4>
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
                <p className="sc-onas-phase__note">
                  <span>{phase.note[0]}:</span> {phase.note[1]}
                </p>
              </li>
            ))}
          </ol>
        </Section>

        <Section id="box" index={4} kicker="Idea" title="Jeden materiał — jeden box">
          <div className="sc-onas-prose">
            <p>
              Box to karta jednego materiału: artykułu, wywiadu, dokumentu, nagrania, wpisu albo komunikatu. Zawsze ma źródło, datę, kategorię i link do oryginału. Nie
              zastępuje publikacji wydawcy — prowadzi do niej.
            </p>
            <p>
              Boxy łączą się ze sobą wspólnymi elementami: hasłem, osobą, instytucją, kategorią i czasem publikacji. Powiązanie to wspólny punkt, a nie dowód, że jeden
              materiał potwierdza drugi.
            </p>
          </div>
          <CopyBlock label="schemat boxa" text={BOX} caption="Układ boxa — przykład bez prawdziwej publikacji." />
          <p className="sc-onas-aside">
            Dziś powiązania opieramy na słowach, kategoriach i dacie publikacji. W kolejnych fazach planujemy wyszukiwanie wspomagane AI — wyłącznie na rekordach
            z naszej bazy, bez dopowiadania faktów.
          </p>
        </Section>

        <Section id="po-kliknieciu" index={5} kicker="Po kliknięciu" title="Co widać po otwarciu boxa">
          <div className="sc-onas-prose">
            <p>Kliknięcie otwiera box na cały ekran. Pod tytułem, źródłem i opisem są trzy warstwy kontekstu:</p>
            <ol className="sc-onas-steps">
              <li>
                <strong>Oś czasu.</strong> 15 najważniejszych materiałów powiązanych z boxem — od najnowszego po lewej do coraz starszych. Otwarty box stoi na swoim miejscu
                na osi, więc od razu widać, co było przed nim, a co po nim.
              </li>
              <li>
                <strong>Reakcje.</strong> Czytelnicy zaznaczają, czy materiał był przydatny, i mogą dodać komentarz. Reakcja dotyczy materiału, nie osób.
              </li>
              <li>
                <strong>Baza powiązanych.</strong> Wszystkie znalezione materiały w kolumnach według kategorii — artykuł, film, materiały publiczne, reportaż — i w wierszach
                według dat. Wyniki dochodzą na bieżąco, w miarę przeszukiwania bazy.
              </li>
            </ol>
          </div>
          <CopyBlock label="schemat widoku po otwarciu" text={EXPANDED} />
        </Section>

        <Section id="nitki-newsowe" index={6} kicker="Nitka newsowa" title="Twój pasek wiadomości">
          <div className="sc-onas-prose">
            <p>
              Na górze strony głównej jest pasek newsowy spin.clinic: najnowsze materiały, które przewijasz w bok. Takich pasków — nitek newsowych — możesz ustawić sobie do
              pięciu.
            </p>
            <p>
              Każdą dopasowujesz do siebie: po haśle, po kategorii, po źródle albo po wszystkim naraz. Na przykład: hasło „Sejm”, tylko materiały publiczne, ze wszystkich
              źródeł. Kolejność nitek zmieniasz przeciągnięciem, a ustawienia zostają na Twoim urządzeniu — bez zakładania konta.
            </p>
          </div>
          <CopyBlock label="schemat nitki newsowej" text={NEWS_THREAD} />
        </Section>

        <Section id="nitki-kontekstowe" index={7} kicker="Nitka kontekstowa" title="Sprawa od początku do końca">
          <div className="sc-onas-prose">
            <p>
              Nitka kontekstowa zaczyna się od jednego boxa — materiału, który chcemy pokazać, wyjaśnić albo wypromować. Za nim, na osi kontekstu, w kolejności publikacji
              idą materiały, które go dopełniają: dokumenty, komunikaty, wywiady, artykuły. Przy każdym może stać krótki komentarz.
            </p>
            <p>Dziś nitki kontekstowe tworzy wyłącznie zespół spin.clinic — jako Dr. Spin. W fazie II tę samą możliwość dostaną użytkownicy.</p>
          </div>
          <CopyBlock label="schemat nitki kontekstowej" text={CONTEXT_THREAD} />
        </Section>

        <Section id="dr-spin" index={8} kicker="Dr. Spin" title="Asystent, który szuka kontekstu">
          <div className="sc-onas-prose">
            <p>
              Dr. Spin to narzędzie zespołu spin.clinic do porządkowania kontekstu i dowodów (beta). Zespół bierze przekazy dnia poszczególnych partii i najczęściej powtarzane
              spiny, przeszukuje naszą bazę źródeł i zestawia materiały, które dany przekaz potwierdzają, podważają albo wyjaśniają.
            </p>
            <p>
              Dr. Spin nie ogłasza, co jest prawdą, i nie zastępuje dziennikarza. Chodzi o kontekst: żeby obok przekazu stało to, co mówią dokumenty, co wydarzyło się wcześniej i co ukazało się
              później — zawsze z linkami do źródeł. Każdą nitkę sprawdza i zatwierdza zespół — żaden model nie publikuje niczego sam.
            </p>
            <p>
              Wsparcie modeli AI — dobór powiązanych materiałów i szkice nitek — jest przygotowane w kodzie, ale dziś pozostaje wyłączone. Włączymy je dopiero po pilotażu
              na ręcznie sprawdzonych materiałach (faza III).
            </p>
          </div>
          <CopyBlock label="jak pracuje Dr. Spin" text={DR_SPIN} />
          <h3 className="sc-onas-h3">W kolejnych fazach</h3>
          <p className="sc-onas-prose">
            Dr. Spin będzie łączył osoby wymienione w materiale z rejestrem osób publicznych: z ich funkcjami i stanowiskami, ze spółkami i fundacjami, w których działają,
            i z osobami, z którymi są powiązane. Z tego powstaną osie powiązań — każde połączenie z odnośnikiem do źródła.
          </p>
          <CopyBlock label="osie powiązań — plan" text={DR_SPIN_LATER} />
          <p className="sc-onas-callout">
            To nie jest narzędzie, które mówi, co jest prawdą. To narzędzie, które pozwala zobaczyć temat na pełnej osi powiązań, kontekstu i danych dostępnych publicznie
            — i ocenić go samodzielnie.
          </p>
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
            <p>
              Chętnie uwzględnimy wymagany sposób oznaczania źródła i limity techniczne. Zapraszamy też do współpracy przy nitkach: jeśli macie materiał, który zasługuje
              na szerszy kontekst — napiszcie.
            </p>
            <p>
              <a className="sc-onas-mail" href={`mailto:${SOURCES_EMAIL}`}>
                Napisz do nas: {SOURCES_EMAIL}
              </a>
            </p>
          </div>
        </Section>

        <Section id="zasady" index={10} kicker="Zasady" title="Co robimy, a czego nie">
          <div className="sc-onas-rules">
            <div>
              <h3>Robimy</h3>
              <ul className="sc-onas-list is-yes">
                <li>pokazujemy źródło, datę i link do oryginału przy każdym materiale</li>
                <li>układamy materiały w kolejności publikacji</li>
                <li>pokazujemy braki danych jako braki, bez zgadywania</li>
                <li>wyraźnie oznaczamy materiały reklamowe i sponsorowane</li>
              </ul>
            </div>
            <div>
              <h3>Nie robimy</h3>
              <ul className="sc-onas-list is-no">
                <li>nie oceniamy osób</li>
                <li>nie oznaczamy treści jako „prawda” albo „fałsz”</li>
                <li>nie publikujemy niczego automatycznie</li>
                <li>nie piszemy własnych newsów i nie zastępujemy wydawców</li>
                <li>nie kopiujemy pełnych tekstów bez zgody wydawcy</li>
                <li>nie obchodzimy blokad, limitów ani płatnych dostępów</li>
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
