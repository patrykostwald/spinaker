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

const SECTIONS = [
  { id: 'spin-doctor', label: 'Spin doctor' },
  { id: 'o-nas', label: 'O nas' },
  { id: 'fazy', label: 'Trzy fazy projektu' },
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

const PHASES: Array<{
  id: string;
  status: string;
  title: string;
  lead: string;
  items: string[];
  stack: Array<[string, string]>;
  note: [string, string];
  current?: boolean;
}> = [
  {
    id: 'faza-1',
    status: 'Faza I · teraz (beta)',
    title: 'Baza, boxy i paski newsowe',
    lead: 'Zbieramy materiały z legalnie dostępnych źródeł i pokazujemy je jako boxy — na pasku newsowym, na osi czasu i w bazie z wyszukiwarką.',
    items: [
      'baza materiałów instytucji publicznych i mediów, z wyszukiwaniem po haśle, kategorii, źródle i dacie',
      'pasek newsowy spin.clinic i do pięciu własnych nitek newsowych',
      'po otwarciu boxa: oś czasu 15 powiązanych materiałów i baza powiązanych w kolumnach',
      'rejestr osób publicznych: funkcje, głosowania w Sejmie i doniesienia',
      'nitki Dr. Spina przygotowywane przez redakcję z pomocą narzędzi AI',
    ],
    stack: [
      ['dane', 'Python · Django REST Framework · PostgreSQL'],
      ['pobieranie', 'Celery · Redis — zadania według harmonogramu, w limitach każdego źródła'],
      ['serwis', 'Next.js · React'],
      ['źródła', 'API Sejmu i ELI · RSS · BIP · YouTube Data API · API X (oficjalne, płatne, tylko potwierdzone konta)'],
    ],
    note: ['W trakcie', 'katalog źródeł uzupełniamy — media dołączają po zgodzie wydawców.'],
    current: true,
  },
  {
    id: 'faza-2',
    status: 'Faza II · następny etap',
    title: 'Konta i własny kontekst',
    lead: 'Konto pozwoli zachować własną pracę z materiałami i dzielić się nią z innymi.',
    items: [
      'własne nitki kontekstowe — takie, jakie dziś układa Dr. Spin',
      'reakcje i komentarze do boxów i nitek, z moderacją',
      'obserwowane tematy, ulubione materiały i źródła',
      'rozbudowa rejestru osób publicznych: historia funkcji z datami i powiązania z rejestrów publicznych (np. KRS)',
    ],
    stack: [
      ['konta', 'Django — konta, moderacja, zgłoszenia'],
      ['rejestry', 'publiczne rejestry i API — m.in. KRS, historia kadencji z API Sejmu'],
    ],
    note: ['Nadal bez', 'automatycznej publikacji i automatycznych ocen.'],
  },
  {
    id: 'faza-3',
    status: 'Faza III · plan',
    title: 'Dr. Spin i wyszukiwanie po znaczeniu',
    lead: 'Dr. Spin rozwija się w asystenta redakcyjnego opartego na modelach AI z otwartymi wagami (open-weight).',
    items: [
      'wyszukiwanie po znaczeniu — materiały o tym samym, opisane innymi słowami',
      'łączenie osób z materiałów z rejestrem osób publicznych i osie powiązań',
      'szkice nitek z cytatami, datami i jawnie opisanymi brakami danych — zawsze do sprawdzenia przez redaktora',
    ],
    stack: [
      ['AI', 'NVIDIA NIM — wyszukiwanie po znaczeniu i porządkowanie wyników'],
      ['', 'Groq — szkice redakcyjne w ściśle określonym formacie'],
      ['docelowo', 'otwarte modele na własnej infrastrukturze'],
    ],
    note: ['Stan', 'połączenia z dostawcami są przygotowane i domyślnie wyłączone. Włączamy je po pilotażu na ręcznie sprawdzonych materiałach.'],
  },
];

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
        </Section>

        <Section id="fazy" index={3} kicker="Rozwój" title="Trzy fazy projektu">
          <p className="sc-onas-prose">Rozwijamy spin.clinic etapami. Przy każdej fazie piszemy wprost, co już działa, a co jest dopiero planem — i na jakiej technologii to budujemy.</p>
          <ol className="sc-onas-phases">
            {PHASES.map((phase) => (
              <li key={phase.id} className="sc-onas-phase" data-current={phase.current || undefined} aria-labelledby={`${phase.id}-title`}>
                <p className="sc-onas-phase__status">{phase.status}</p>
                <h3 id={`${phase.id}-title`}>{phase.title}</h3>
                <p>{phase.lead}</p>
                <ul className="sc-onas-list">
                  {phase.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <dl className="sc-onas-stack" aria-label="Technologia">
                  {phase.stack.map(([key, value]) => (
                    <div key={`${key}-${value}`}>
                      <dt>{key}</dt>
                      <dd>{value}</dd>
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
            Dziś powiązania opieramy na słowach, kategoriach i dacie publikacji. W przyszłości planujemy własny, otwartoźródłowy silnik AI, który będzie wspierał
            wyszukiwanie i dobór powiązanych materiałów.
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
            <p>Dziś nitki kontekstowe tworzy wyłącznie redakcja — jako Dr. Spin. W fazie II tę samą możliwość dostaną użytkownicy.</p>
          </div>
          <CopyBlock label="schemat nitki kontekstowej" text={CONTEXT_THREAD} />
        </Section>

        <Section id="dr-spin" index={8} kicker="Dr. Spin" title="Asystent, który szuka kontekstu">
          <div className="sc-onas-prose">
            <p>
              Dr. Spin to zestaw współpracujących programów i modeli AI. Każdego dnia wyszukuje przekazy dnia poszczególnych partii i najczęściej powtarzane spiny, a potem
              przeszukuje naszą bazę źródeł i podsuwa materiały, które dany przekaz potwierdzają, podważają albo wyjaśniają.
            </p>
            <p>
              Nie chodzi o ogłaszanie, co jest prawdą. Chodzi o kontekst: żeby obok przekazu stało to, co mówią dokumenty, co wydarzyło się wcześniej i co ukazało się
              później. Każdą nitkę sprawdza i zatwierdza redakcja — żaden model nie publikuje niczego sam.
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
