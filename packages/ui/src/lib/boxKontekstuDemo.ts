/**
 * Lokalne, fikcyjne dane demonstracyjne dla widoku „Box kontekstu”.
 * Nie są prawdziwymi publikacjami i nie pochodzą z API. Służą wyłącznie
 * do oceny układu, zanim widok zostanie podłączony do /api/articles/:id/context/.
 */

export type ContextMaterialType =
  | 'artykul'
  | 'wywiad'
  | 'reportaz'
  | 'dokument'
  | 'film'
  | 'post'
  | 'komunikat'
  | 'reklama';

/** Relacja boxa do wydarzenia zapisana przez redakcję — nie jest oceną treści. */
export type ContextRole =
  | 'pierwsza-informacja'
  | 'zrodlo-pierwotne'
  | 'inny-opis'
  | 'dalszy-ciag'
  | 'reklama';

export type ContextBox = {
  id: string;
  type: ContextMaterialType;
  source: string;
  author?: string;
  /** ISO 8601 z przesunięciem strefy. */
  publishedAt: string;
  title: string;
  summary: string;
  /** Sposób pozyskania metadanych (RSS, API, ręcznie potwierdzone konto…). */
  acquisition: string;
  role: ContextRole;
  /** Źródło pierwotne: dokument, komunikat, nagranie lub wypowiedź u źródła. */
  primary: boolean;
};

export type ContextEvent = {
  title: string;
  place: string;
  note: string;
};

export const CONTEXT_TYPE_LABELS: Record<ContextMaterialType, string> = {
  artykul: 'ARTYKUŁ',
  wywiad: 'WYWIAD',
  reportaz: 'REPORTAŻ',
  dokument: 'DOKUMENT',
  film: 'FILM',
  post: 'POST',
  komunikat: 'KOMUNIKAT',
  reklama: 'REKLAMA',
};

export const CONTEXT_ROLE_LABELS: Record<ContextRole, string> = {
  'pierwsza-informacja': 'pierwsza informacja o wydarzeniu',
  'zrodlo-pierwotne': 'źródło pierwotne / dokument',
  'inny-opis': 'inny opis tego samego faktu',
  'dalszy-ciag': 'dalszy ciąg wydarzenia',
  reklama: 'materiał reklamowy powiązany tematem',
};

export const DEMO_CONTEXT_EVENT: ContextEvent = {
  title: 'Czasowe zamknięcie mostu miejskiego',
  place: 'Miasto Przykładowe (fikcyjne)',
  note: 'Wszystkie źródła, tytuły i daty w tym widoku są zmyślone na potrzeby prezentacji układu.',
};

export const DEMO_CONTEXT_BOXES: ContextBox[] = [
  {
    id: 'demo-dokument-protokol',
    type: 'dokument',
    source: 'BIP Urzędu Miasta Przykładowego',
    publishedAt: '2026-09-12T10:00:00+02:00',
    title: 'Protokół z okresowego przeglądu technicznego mostu (PDF)',
    summary: 'Dokument opublikowany w rejestrze urzędowym dwa dni przed pierwszymi doniesieniami.',
    acquisition: 'oficjalny rejestr / API instytucji',
    role: 'zrodlo-pierwotne',
    primary: true,
  },
  {
    id: 'demo-post-rzecznik',
    type: 'post',
    source: 'Konto X rzecznika urzędu (przykład)',
    author: 'Rzecznik urzędu',
    publishedAt: '2026-09-14T07:40:00+02:00',
    title: 'Most miejski zamknięty dla ruchu do odwołania. Szczegóły w komunikacie.',
    summary: 'Krótka wypowiedź u źródła, opublikowana przed komunikatem i artykułami.',
    acquisition: 'oficjalne API X · konto ręcznie potwierdzone',
    role: 'pierwsza-informacja',
    primary: true,
  },
  {
    id: 'demo-artykul-portal',
    type: 'artykul',
    source: 'Portal A (przykład)',
    author: 'Redakcja portalu',
    publishedAt: '2026-09-14T09:15:00+02:00',
    title: 'Most zamknięty. Objazdy prowadzą przez centrum',
    summary: 'Pierwszy artykuł prasowy powołujący się na wpis rzecznika.',
    acquisition: 'RSS wydawcy',
    role: 'inny-opis',
    primary: false,
  },
  {
    id: 'demo-komunikat-urzad',
    type: 'komunikat',
    source: 'Urząd Miasta Przykładowego',
    publishedAt: '2026-09-14T12:00:00+02:00',
    title: 'Komunikat w sprawie czasowego zamknięcia mostu',
    summary: 'Oficjalny komunikat z zakresem prac i przewidywanym terminem.',
    acquisition: 'RSS instytucji',
    role: 'zrodlo-pierwotne',
    primary: true,
  },
  {
    id: 'demo-artykul-gazeta',
    type: 'artykul',
    source: 'Gazeta F (przykład)',
    author: 'Autor przykładowy',
    publishedAt: '2026-09-14T13:10:00+02:00',
    title: 'Urząd: most zamknięty po przeglądzie technicznym',
    summary: 'Inny opis tego samego faktu, z odwołaniem do komunikatu urzędu.',
    acquisition: 'RSS wydawcy',
    role: 'inny-opis',
    primary: false,
  },
  {
    id: 'demo-wywiad-radio',
    type: 'wywiad',
    source: 'Radio B (przykład)',
    author: 'Prowadząca audycję',
    publishedAt: '2026-09-15T08:10:00+02:00',
    title: 'Wywiad z inżynierem nadzoru o stanie konstrukcji',
    summary: 'Rozmowa radiowa; zapis metadanych bez transkrypcji.',
    acquisition: 'RSS podcastu',
    role: 'dalszy-ciag',
    primary: false,
  },
  {
    id: 'demo-film-komisja',
    type: 'film',
    source: 'Kanał wideo rady miasta (przykład)',
    publishedAt: '2026-09-15T19:00:00+02:00',
    title: 'Nagranie z posiedzenia komisji infrastruktury',
    summary: 'Pełne nagranie posiedzenia — źródło pierwotne wypowiedzi radnych.',
    acquisition: 'YouTube Data API',
    role: 'zrodlo-pierwotne',
    primary: true,
  },
  {
    id: 'demo-reportaz-tygodnik',
    type: 'reportaz',
    source: 'Tygodnik D (przykład)',
    author: 'Reporterka przykładowa',
    publishedAt: '2026-09-17T06:00:00+02:00',
    title: 'Jeden most, dwa brzegi. Tydzień objazdów',
    summary: 'Reportaż o skutkach zamknięcia dla mieszkańców.',
    acquisition: 'RSS wydawcy',
    role: 'dalszy-ciag',
    primary: false,
  },
  {
    id: 'demo-reklama-przewoznik',
    type: 'reklama',
    source: 'Przewoźnik E (przykład)',
    publishedAt: '2026-09-17T10:00:00+02:00',
    title: 'Dojedź na drugi brzeg linią sezonową',
    summary: 'Materiał reklamowy oznaczony przez wydawcę. Nie jest materiałem informacyjnym.',
    acquisition: 'dodany ręcznie przez redakcję · oznaczony jako reklama',
    role: 'reklama',
    primary: false,
  },
];

/** Przykładowa nitka odpowiadająca schematowi z opisu: artykuł → wywiad → reportaż → dokument → reklama. */
export const DEMO_THREAD_EXAMPLE: string[] = [
  'demo-artykul-portal',
  'demo-wywiad-radio',
  'demo-reportaz-tygodnik',
  'demo-dokument-protokol',
  'demo-reklama-przewoznik',
];
