/**
 * Fikcyjne dane demonstracyjne dla widoku „Powiększony box materiału”.
 * Wszystkie osoby, podmioty, źródła, tytuły, daty i adresy są zmyślone.
 * Plik nie wysyła żadnych żądań — domena `przyklad.invalid` celowo nie istnieje.
 */

export type MaterialKind = 'artykul' | 'dokument' | 'post' | 'film';
export type SourceKind = 'media' | 'instytucja' | 'social' | 'wideo';

export type DemoMaterial = {
  id: string;
  kind: MaterialKind;
  /** Etykieta formy widoczna w boxie, np. KOMUNIKAT, WYWIAD. */
  label: string;
  sourceKind: SourceKind;
  source: string;
  author?: string;
  /** ISO 8601 z przesunięciem strefy. */
  publishedAt: string;
  title: string;
  description: string;
  url: string;
  primary: boolean;
  /** Jawna podstawa automatycznego powiązania — nie ocena treści. */
  relation: string;
  /**
   * Identyfikator prawdziwego materiału z Bazy. Gdy jest podany, reakcje, komentarze i ulubione
   * korzystają z API konta. Dane demonstracyjne go nie mają i niczego nie zapisują.
   */
  articleId?: number;
};

export type DemoComment = { id: string; author: string; createdAt: string; text: string };
export type DemoReactions = { useful: number; notUseful: number };

export const MATERIAL_KIND_LABELS: Record<MaterialKind, { singular: string; plural: string }> = {
  artykul: { singular: 'Artykuł', plural: 'Artykuły' },
  dokument: { singular: 'Dokument', plural: 'Dokumenty' },
  post: { singular: 'Post', plural: 'Posty' },
  film: { singular: 'Film', plural: 'Filmy' },
};

export const SOURCE_KIND_LABELS: Record<SourceKind, string> = {
  media: 'Media',
  instytucja: 'Instytucja publiczna',
  social: 'Konto w serwisie społecznościowym',
  wideo: 'Kanał wideo',
};

export const DEMO_TOPIC = {
  label: 'most miejski',
  note: 'Wszystkie osoby, podmioty, źródła, tytuły i daty są fikcyjne. Linki prowadzą do nieistniejącej domeny przyklad.invalid i są w demo nieaktywne.',
};

export const DEMO_MATERIALS: DemoMaterial[] = [
  {
    id: 'm-dok-protokol', kind: 'dokument', label: 'DOKUMENT', sourceKind: 'instytucja',
    source: 'BIP Urzędu Miasta Przykładowego', publishedAt: '2026-09-12T10:00:00+02:00',
    title: 'Protokół z okresowego przeglądu technicznego mostu',
    description: 'Dokument z rejestru urzędowego opublikowany przed pierwszymi doniesieniami.',
    url: 'https://przyklad.invalid/bip/protokol-przegladu', primary: true,
    relation: 'ten sam obiekt: most miejski · dokument cytowany w komunikacie',
  },
  {
    id: 'm-post-rzecznik', kind: 'post', label: 'POST', sourceKind: 'social',
    source: 'Konto rzecznika urzędu (fikcyjne)', author: 'Rzecznik urzędu', publishedAt: '2026-09-14T07:40:00+02:00',
    title: 'Most miejski zamknięty dla ruchu do odwołania. Szczegóły w komunikacie.',
    description: 'Krótka wypowiedź u źródła, opublikowana przed komunikatem.',
    url: 'https://przyklad.invalid/konto-rzecznika/post-1', primary: true,
    relation: 'wspólny tag: most miejski · ta sama instytucja',
  },
  {
    id: 'm-art-portal-a', kind: 'artykul', label: 'ARTYKUŁ', sourceKind: 'media',
    source: 'Portal A (fikcyjny)', author: 'Redakcja portalu', publishedAt: '2026-09-14T09:15:00+02:00',
    title: 'Most zamknięty. Objazdy prowadzą przez centrum',
    description: 'Pierwszy artykuł prasowy o zamknięciu, powołuje się na wpis rzecznika.',
    url: 'https://przyklad.invalid/portal-a/most-zamkniety', primary: false,
    relation: 'wspólny tag: most miejski · cytuje wpis rzecznika',
  },
  {
    id: 'm-kom-urzad', kind: 'dokument', label: 'KOMUNIKAT', sourceKind: 'instytucja',
    source: 'Urząd Miasta Przykładowego', publishedAt: '2026-09-14T12:00:00+02:00',
    title: 'Komunikat w sprawie czasowego zamknięcia mostu miejskiego',
    description: 'Oficjalny komunikat z zakresem prac, objazdami i przewidywanym terminem ponownego otwarcia.',
    url: 'https://przyklad.invalid/urzad/komunikat-most', primary: true,
    relation: 'materiał otwarty w powiększeniu',
  },
  {
    id: 'm-art-gazeta-f', kind: 'artykul', label: 'ARTYKUŁ', sourceKind: 'media',
    source: 'Gazeta F (fikcyjna)', author: 'Autor przykładowy', publishedAt: '2026-09-14T13:10:00+02:00',
    title: 'Urząd: most zamknięty po przeglądzie technicznym',
    description: 'Inny opis tego samego faktu, z odwołaniem do komunikatu.',
    url: 'https://przyklad.invalid/gazeta-f/urzad-most', primary: false,
    relation: 'powołuje się na komunikat · wspólny tag: most miejski',
  },
  {
    id: 'm-post-radny', kind: 'post', label: 'POST', sourceKind: 'social',
    source: 'Konto radnego (fikcyjne)', author: 'Radny przykładowy', publishedAt: '2026-09-14T18:30:00+02:00',
    title: 'Pytania o termin remontu zadam na posiedzeniu komisji.',
    description: 'Wypowiedź u źródła zapowiadająca pytania na komisji.',
    url: 'https://przyklad.invalid/konto-radnego/post-7', primary: true,
    relation: 'wspólny tag: most miejski · zapowiedź posiedzenia',
  },
  {
    id: 'm-wyw-radio', kind: 'artykul', label: 'WYWIAD', sourceKind: 'media',
    source: 'Radio B (fikcyjne)', author: 'Prowadząca audycję', publishedAt: '2026-09-15T08:10:00+02:00',
    title: 'Inżynier nadzoru o stanie konstrukcji mostu',
    description: 'Rozmowa radiowa; w bazie są metadane i odnośnik, bez transkrypcji.',
    url: 'https://przyklad.invalid/radio-b/wywiad-inzynier', primary: false,
    relation: 'wspólny tag: most miejski',
  },
  {
    id: 'm-dok-porzadek', kind: 'dokument', label: 'DOKUMENT', sourceKind: 'instytucja',
    source: 'BIP Rady Miasta Przykładowego', publishedAt: '2026-09-15T11:00:00+02:00',
    title: 'Porządek obrad komisji infrastruktury',
    description: 'Dokument zawiera punkt o stanie mostu miejskiego.',
    url: 'https://przyklad.invalid/bip-rady/porzadek-obrad', primary: true,
    relation: 'ten sam obiekt: most miejski · ta sama gmina',
  },
  {
    id: 'm-film-komisja', kind: 'film', label: 'FILM', sourceKind: 'wideo',
    source: 'Kanał wideo rady miasta (fikcyjny)', publishedAt: '2026-09-15T19:00:00+02:00',
    title: 'Nagranie posiedzenia komisji infrastruktury',
    description: 'Pełne nagranie posiedzenia — źródło pierwotne wypowiedzi radnych.',
    url: 'https://przyklad.invalid/wideo/komisja', primary: true,
    relation: 'dokument „Porządek obrad” · ta sama data posiedzenia',
  },
  {
    id: 'm-film-relacja', kind: 'film', label: 'FILM', sourceKind: 'media',
    source: 'Telewizja lokalna C (fikcyjna)', publishedAt: '2026-09-15T21:20:00+02:00',
    title: 'Relacja z posiedzenia komisji w sprawie mostu',
    description: 'Materiał telewizyjny streszczający posiedzenie.',
    url: 'https://przyklad.invalid/tv-c/relacja-komisja', primary: false,
    relation: 'odwołuje się do nagrania posiedzenia',
  },
  {
    id: 'm-art-portal-a-2', kind: 'artykul', label: 'ARTYKUŁ', sourceKind: 'media',
    source: 'Portal A (fikcyjny)', author: 'Redakcja portalu', publishedAt: '2026-09-16T07:30:00+02:00',
    title: 'Remont mostu może potrwać dłużej niż zakładano',
    description: 'Artykuł po posiedzeniu komisji, cytuje wypowiedzi z nagrania.',
    url: 'https://przyklad.invalid/portal-a/remont-dluzej', primary: false,
    relation: 'cytuje nagranie posiedzenia · wspólny tag: most miejski',
  },
  {
    id: 'm-post-mieszkancy', kind: 'post', label: 'POST', sourceKind: 'social',
    source: 'Profil stowarzyszenia mieszkańców (fikcyjny)', publishedAt: '2026-09-16T16:45:00+02:00',
    title: 'Zbieramy pytania mieszkańców dotyczące objazdów.',
    description: 'Post organizacji lokalnej z prośbą o pytania.',
    url: 'https://przyklad.invalid/stowarzyszenie/post-3', primary: false,
    relation: 'wspólny tag: most miejski',
  },
  {
    id: 'm-rep-tygodnik', kind: 'artykul', label: 'REPORTAŻ', sourceKind: 'media',
    source: 'Tygodnik D (fikcyjny)', author: 'Reporterka przykładowa', publishedAt: '2026-09-17T06:00:00+02:00',
    title: 'Jeden most, dwa brzegi. Tydzień objazdów',
    description: 'Reportaż o skutkach zamknięcia dla mieszkańców.',
    url: 'https://przyklad.invalid/tygodnik-d/reportaz-most', primary: false,
    relation: 'wspólny tag: most miejski',
  },
  {
    id: 'm-dok-harmonogram', kind: 'dokument', label: 'DOKUMENT', sourceKind: 'instytucja',
    source: 'BIP Urzędu Miasta Przykładowego', publishedAt: '2026-09-17T10:30:00+02:00',
    title: 'Zaktualizowany harmonogram prac przy moście',
    description: 'Nowa wersja harmonogramu z przesuniętym terminem.',
    url: 'https://przyklad.invalid/bip/harmonogram', primary: true,
    relation: 'ten sam obiekt: most miejski · aktualizacja komunikatu',
  },
];

export const DEMO_ENTRY_IDS = ['m-kom-urzad', 'm-art-portal-a', 'm-post-radny', 'm-film-komisja'];

export const DEMO_REACTIONS: Record<string, DemoReactions> = {
  'm-kom-urzad': { useful: 14, notUseful: 2 },
  'm-film-komisja': { useful: 9, notUseful: 1 },
  'm-art-portal-a': { useful: 5, notUseful: 3 },
};

export const DEMO_COMMENTS: Record<string, DemoComment[]> = {
  'm-kom-urzad': [
    { id: 'c1', author: 'czytelnik_demo_A', createdAt: '2026-09-14T13:02:00+02:00', text: 'Przydało się zestawienie z protokołem przeglądu z 12.09 — widać, skąd wziął się termin.' },
    { id: 'c2', author: 'czytelnik_demo_B', createdAt: '2026-09-15T08:40:00+02:00', text: 'Brakuje mi tu jeszcze harmonogramu objazdów w formie dokumentu.' },
  ],
  'm-film-komisja': [
    { id: 'c3', author: 'czytelnik_demo_C', createdAt: '2026-09-16T09:12:00+02:00', text: 'Dobrze, że jest pełne nagranie obok relacji telewizyjnej.' },
  ],
};

/* ——— Wariant: profil polityka (postać fikcyjna) ——— */

export type VoteChoice = 'za' | 'przeciw' | 'wstrzymal' | 'nieobecny';
export type EntityKind = 'fundacja' | 'stowarzyszenie' | 'spolka';
export type Verification = 'potwierdzone' | 'do-potwierdzenia';

export type DemoVote = { id: string; date: string; topic: string; choice: VoteChoice; sourceLabel: string; url: string };
export type DemoRegistryRelation = {
  id: string;
  entity: string;
  kind: EntityKind;
  publicRole: string;
  status: 'obecna' | 'historyczna';
  verifiedAt: string;
  sourceLabel: string;
  url: string;
  verification: Verification;
};

export const VOTE_LABELS: Record<VoteChoice, string> = {
  za: 'Za',
  przeciw: 'Przeciw',
  wstrzymal: 'Wstrzymał się',
  nieobecny: 'Nie głosował',
};

export const ENTITY_KIND_LABELS: Record<EntityKind, { singular: string; plural: string }> = {
  fundacja: { singular: 'fundacja', plural: 'Fundacje' },
  stowarzyszenie: { singular: 'stowarzyszenie', plural: 'Stowarzyszenia' },
  spolka: { singular: 'spółka', plural: 'Spółki' },
};

export const VERIFICATION_LABELS: Record<Verification, string> = {
  potwierdzone: 'potwierdzone w źródle publicznym',
  'do-potwierdzenia': 'wymaga potwierdzenia redakcji',
};

export const DEMO_POLITICIAN = {
  id: 'p-jan-przykladowy',
  name: 'Jan Przykładowy',
  fictionalNote: 'postać fikcyjna',
  publicRole: 'Poseł (fikcyjna kadencja)',
  club: 'Klub Przykładowy (fikcyjny)',
  description: 'Profil pokazuje wyłącznie publiczne funkcje i jawne głosowania. Nie zawiera adresów, numerów PESEL, dat urodzenia ani danych osób prywatnych.',
  url: 'https://przyklad.invalid/sejm/posel-przykladowy',
};

export const DEMO_VOTES: DemoVote[] = [
  { id: 'v1', date: '2026-09-10', topic: 'Przepisy o utrzymaniu mostów miejskich', choice: 'za', sourceLabel: 'API Sejmu (demo)', url: 'https://przyklad.invalid/sejm/glosowanie/1' },
  { id: 'v2', date: '2026-09-10', topic: 'Poprawka o finansowaniu remontów dróg lokalnych', choice: 'przeciw', sourceLabel: 'API Sejmu (demo)', url: 'https://przyklad.invalid/sejm/glosowanie/2' },
  { id: 'v3', date: '2026-08-28', topic: 'Dostępność przystanków komunikacji miejskiej', choice: 'wstrzymal', sourceLabel: 'API Sejmu (demo)', url: 'https://przyklad.invalid/sejm/glosowanie/3' },
  { id: 'v4', date: '2026-08-27', topic: 'Wniosek o przerwę w obradach', choice: 'nieobecny', sourceLabel: 'API Sejmu (demo)', url: 'https://przyklad.invalid/sejm/glosowanie/4' },
  { id: 'v5', date: '2026-07-24', topic: 'Fundusz dróg samorządowych na 2027 r.', choice: 'za', sourceLabel: 'API Sejmu (demo)', url: 'https://przyklad.invalid/sejm/glosowanie/5' },
];

export const DEMO_REGISTRY: DemoRegistryRelation[] = [
  { id: 'r1', entity: 'Fundacja Przykładowa Rzeka (fikcyjna)', kind: 'fundacja', publicRole: 'członek rady fundacji', status: 'obecna', verifiedAt: '2026-09-15', sourceLabel: 'Rejestr publiczny (demo)', url: 'https://przyklad.invalid/rejestr/fundacja-1', verification: 'potwierdzone' },
  { id: 'r2', entity: 'Fundacja Zielony Brzeg (fikcyjna)', kind: 'fundacja', publicRole: 'członek zarządu', status: 'historyczna', verifiedAt: '2026-09-02', sourceLabel: 'Rejestr publiczny (demo)', url: 'https://przyklad.invalid/rejestr/fundacja-2', verification: 'do-potwierdzenia' },
  { id: 'r3', entity: 'Stowarzyszenie Miłośników Mostów (fikcyjne)', kind: 'stowarzyszenie', publicRole: 'członek zarządu', status: 'obecna', verifiedAt: '2026-09-15', sourceLabel: 'Rejestr publiczny (demo)', url: 'https://przyklad.invalid/rejestr/stowarzyszenie-1', verification: 'potwierdzone' },
  { id: 'r4', entity: 'Stowarzyszenie Przykładowe Forum (fikcyjne)', kind: 'stowarzyszenie', publicRole: 'członek komisji rewizyjnej', status: 'historyczna', verifiedAt: '2026-08-30', sourceLabel: 'Rejestr publiczny (demo)', url: 'https://przyklad.invalid/rejestr/stowarzyszenie-2', verification: 'do-potwierdzenia' },
  { id: 'r5', entity: 'Przykładowa Spółka Komunalna sp. z o.o. (fikcyjna)', kind: 'spolka', publicRole: 'członek rady nadzorczej', status: 'historyczna', verifiedAt: '2026-09-11', sourceLabel: 'Rejestr publiczny (demo)', url: 'https://przyklad.invalid/rejestr/spolka-1', verification: 'potwierdzone' },
];
