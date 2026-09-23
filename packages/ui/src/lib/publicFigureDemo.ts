import type { PublicFigureDetail } from './publicFigures';

/**
 * DANE DEMONSTRACYJNE — osoba, podmioty, głosowania i materiały są fikcyjne.
 * Kształt `DEMO_PUBLIC_FIGURE` jest identyczny z odpowiedzią GET /api/public-figures/:id/.
 * Domena przyklad.invalid celowo nie istnieje. Numery KRS są zerowe i nie wskazują żadnego podmiotu.
 * `x_account` ma wartość null — demo nie wymyśla handle'a (API zwraca konto X tylko po potwierdzeniu).
 */
export const DEMO_PUBLIC_FIGURE: PublicFigureDetail = {
  id: 0,
  name: 'Jan Przykładowy',
  role_category: 'parliamentary',
  role_title: 'Poseł na Sejm (fikcyjna kadencja)',
  organisation: 'Sejm Rzeczypospolitej Polskiej — przykład',
  status: 'current',
  official_profile_url: 'https://przyklad.invalid/sejm/posel/0',
  evidence_url: 'https://przyklad.invalid/sejm/lista-poslow',
  source_checked_at: '2026-09-20T09:00:00+02:00',
  organisations: [
    { id: 1, name: 'Fundacja Przykładowa Rzeka (fikcyjna)', krs_number: '0000000000', kind: 'foundation', official_register_url: 'https://przyklad.invalid/krs/1', public_role: 'członek rady fundacji', relation_status: 'current', evidence_url: 'https://przyklad.invalid/dowod/1', verified_at: '2026-09-15T12:00:00+02:00' },
    { id: 2, name: 'Stowarzyszenie Miłośników Mostów (fikcyjne)', krs_number: '0000000000', kind: 'association', official_register_url: 'https://przyklad.invalid/krs/2', public_role: 'członek zarządu', relation_status: 'former', evidence_url: 'https://przyklad.invalid/dowod/2', verified_at: '2026-09-11T12:00:00+02:00' },
    { id: 3, name: 'Przykładowa Spółka Komunalna sp. z o.o. (fikcyjna)', krs_number: '0000000000', kind: 'company', official_register_url: 'https://przyklad.invalid/krs/3', public_role: 'członek rady nadzorczej', relation_status: 'former', evidence_url: 'https://przyklad.invalid/dowod/3', verified_at: '2026-09-10T12:00:00+02:00' },
  ],
  votes: {
    available: true,
    source_url: 'https://przyklad.invalid/sejm/posel/0/glosowania',
    results: [
      { date: '2026-09-10T11:20:00+02:00', topic: 'Przepisy o utrzymaniu mostów miejskich', vote: 'YES', article_url: 'https://przyklad.invalid/sejm/glosowanie/1', source: 'Sejm RP (przykład)' },
      { date: '2026-09-10T11:05:00+02:00', topic: 'Poprawka o finansowaniu remontów dróg lokalnych', vote: 'NO', article_url: 'https://przyklad.invalid/sejm/glosowanie/2', source: 'Sejm RP (przykład)' },
      { date: '2026-08-28T16:40:00+02:00', topic: 'Dostępność przystanków komunikacji miejskiej', vote: 'ABSTAIN', article_url: 'https://przyklad.invalid/sejm/glosowanie/3', source: 'Sejm RP (przykład)' },
      { date: '2026-08-27T10:00:00+02:00', topic: 'Wniosek o przerwę w obradach', vote: 'ABSENT', article_url: 'https://przyklad.invalid/sejm/glosowanie/4', source: 'Sejm RP (przykład)' },
      { date: '2026-07-24T13:15:00+02:00', topic: 'Fundusz dróg samorządowych na 2027 r. — wniosek o odrzucenie projektu w pierwszym czytaniu wraz z poprawkami komisji infrastruktury', vote: 'YES', article_url: 'https://przyklad.invalid/sejm/glosowanie/5', source: 'Sejm RP (przykład)' },
    ],
  },
  x_account: null,
};

/** Fikcyjne materiały w kształcie wiersza listy profilu (podzbiór pól Article z /api/feed/). */
export type FigureMaterial = {
  id: number;
  title: string;
  url: string;
  category: string;
  published_date: string | null;
  source_id: number;
  source_name: string;
  topics?: string[];
};

export const DEMO_FIGURE_SOURCES = [
  { id: 901, name: 'Portal A (fikcyjny)' },
  { id: 902, name: 'Radio B (fikcyjne)' },
  { id: 903, name: 'BIP Rady Miasta (fikcyjny)' },
  { id: 904, name: 'Konto posła — przykład' },
];

export const DEMO_FIGURE_MATERIALS: FigureMaterial[] = [
  { id: -1, title: 'Posłowie o przepisach dotyczących mostów miejskich', url: 'https://przyklad.invalid/a/1', category: 'article', published_date: '2026-09-10T15:00:00+02:00', source_id: 901, source_name: 'Portal A (fikcyjny)', topics: ['polityka'] },
  { id: -2, title: 'Wywiad: czy mosty miejskie potrzebują osobnej ustawy?', url: 'https://przyklad.invalid/a/2', category: 'interview', published_date: '2026-09-11T08:10:00+02:00', source_id: 902, source_name: 'Radio B (fikcyjne)', topics: ['polska'] },
  { id: -3, title: 'Komunikat biura poselskiego po głosowaniu', url: 'https://przyklad.invalid/a/3', category: 'statement', published_date: '2026-09-10T18:30:00+02:00', source_id: 904, source_name: 'Konto posła — przykład', topics: ['polityka'] },
  { id: -4, title: 'Porządek obrad komisji infrastruktury', url: 'https://przyklad.invalid/a/4', category: 'document', published_date: '2026-09-15T11:00:00+02:00', source_id: 903, source_name: 'BIP Rady Miasta (fikcyjny)', topics: ['polska'] },
  { id: -5, title: 'Nagranie posiedzenia komisji infrastruktury', url: 'https://przyklad.invalid/a/5', category: 'video', published_date: '2026-09-15T19:00:00+02:00', source_id: 903, source_name: 'BIP Rady Miasta (fikcyjny)', topics: ['polska'] },
  { id: -6, title: 'Jeden most, dwa brzegi. Tydzień objazdów', url: 'https://przyklad.invalid/a/6', category: 'reportage', published_date: '2026-09-17T06:00:00+02:00', source_id: 901, source_name: 'Portal A (fikcyjny)', topics: ['polska'] },
  { id: -7, title: 'Wpis posła o terminie remontu', url: 'https://przyklad.invalid/a/7', category: 'tweet', published_date: '2026-09-16T12:45:00+02:00', source_id: 904, source_name: 'Konto posła — przykład', topics: ['polityka'] },
  { id: -8, title: 'Fundusz dróg samorządowych: co zmienia projekt', url: 'https://przyklad.invalid/a/8', category: 'article', published_date: '2026-07-25T09:30:00+02:00', source_id: 901, source_name: 'Portal A (fikcyjny)', topics: ['biznes'] },
];

export const DEMO_FIGURE_TOPICS = [
  { value: 'polityka', label: 'Polityka' },
  { value: 'polska', label: 'Polska' },
  { value: 'biznes', label: 'Biznes' },
];
