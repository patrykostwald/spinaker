import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './api';

/*
 * Typy odpowiadają backend/news/public_figures.py (figure_data, votes_data).
 * API zwraca wyłącznie relacje potwierdzone przez redakcję i głosowania dopiero
 * po ręcznym połączeniu profilu z mandatem. Nie ma tu PESEL-i, dat urodzenia ani adresów.
 */

export type PublicFigureRoleCategory = 'government' | 'party' | 'parliamentary' | 'european' | 'local' | 'political';
export type OrganisationKind = 'foundation' | 'association' | 'company' | 'other';

export type PublicFigureSummary = {
  id: number;
  name: string;
  role_category: PublicFigureRoleCategory;
  role_title: string;
  organisation: string;
  status: 'current' | 'former';
  official_profile_url: string;
  evidence_url: string;
  source_checked_at: string | null;
  /** Tylko na liście: czy osoba ma konto X potwierdzone oficjalnym dowodem. */
  has_x_account?: boolean;
};

export type OrganisationSector = 'state' | 'municipal' | 'public' | 'private' | 'ngo' | 'unknown';
export type OrganisationVerification = 'editor' | 'krs_register' | 'public_sources';

export type PublicFigureOrganisation = {
  id: number;
  name: string;
  krs_number: string;
  kind: OrganisationKind;
  legal_form?: string;
  sector?: OrganisationSector;
  /** Publiczna strona podmiotu z danymi KRS. */
  official_register_url: string;
  public_role: string;
  organ?: string;
  relation_status: 'current' | 'former';
  /** Daty wpisu i wykreślenia w KRS (albo puste, gdy relację potwierdzają tylko źródła). */
  since?: string | null;
  until?: string | null;
  verification_method?: OrganisationVerification;
  sources?: Array<{ url: string; title: string }>;
  evidence_url: string;
  verified_at: string | null;
};

/** Oś kariery: funkcje publiczne i funkcje w spółkach Skarbu Państwa, komunalnych i innych publicznych (z KRS). */
export type EmploymentEntry = {
  position: string;
  organisation: string;
  status: 'current' | 'former';
  checked_at: string | null;
  since?: string | null;
  until?: string | null;
  sector?: OrganisationSector;
  /** Klub albo partia w czasie tej funkcji (np. klub w danej kadencji Sejmu). */
  party?: string;
  source: { label: string; url: string };
};

export const SECTOR_LABELS: Record<OrganisationSector, string> = {
  state: 'spółka Skarbu Państwa',
  municipal: 'spółka komunalna',
  public: 'podmiot publiczny',
  private: 'podmiot prywatny',
  ngo: 'organizacja pozarządowa',
  unknown: '',
};

export const VERIFICATION_LABELS: Record<OrganisationVerification, string> = {
  editor: 'potwierdzone przez zespół',
  krs_register: 'potwierdzone w KRS',
  public_sources: 'potwierdzone w źródłach',
};

export type PublicFigureVote = { date: string | null; topic: string; vote: string; article_url: string; source: string };

export type PublicFigureVotes =
  | { available: true; source_url: string; results: PublicFigureVote[] }
  | { available: false; reason?: string; results: PublicFigureVote[] };

/**
 * Konto X z backend/news/public_figures.py::verified_x_account_data - obecne wyłącznie po
 * przeglądzie linku z oficjalnego profilu, potwierdzeniu przez oficjalne API X i potwierdzeniu
 * redakcyjnym. W innym wypadku `null`. Interfejs nigdy nie zgaduje handle'a.
 */
export type VerifiedXAccount = { account_id?: number; handle: string; url: string; evidence_url: string; posts_collected: number };
export type PublicFigureXPost = {
  id: number;
  post_id: string;
  url: string;
  text: string;
  published_at: string;
  likes_count: number;
  reposts_count: number;
};

export type PublicFigureDetail = PublicFigureSummary & {
  organisations: PublicFigureOrganisation[];
  employment_timeline?: EmploymentEntry[];
  /** Obecny klub lub partia (z rejestru Sejmu albo notatki). */
  party?: { code: string; short: string; name: string } | null;
  votes: PublicFigureVotes;
  x_account?: VerifiedXAccount | null;
  /** Wpisy wyłącznie z potwierdzonego konta X tej osoby, bez dopasowania po nazwisku. */
  x_posts?: { available: boolean; results: PublicFigureXPost[] };
};

export const ROLE_CATEGORY_LABELS: Record<PublicFigureRoleCategory, string> = {
  government: 'Rząd i administracja',
  party: 'Partia lub klub parlamentarny',
  parliamentary: 'Parlament krajowy',
  european: 'Parlament Europejski',
  local: 'Samorząd',
  political: 'Inna osoba politycznie wpływowa',
};

export const ORGANISATION_KIND_LABELS: Record<OrganisationKind, { singular: string; plural: string }> = {
  foundation: { singular: 'fundacja', plural: 'Fundacje' },
  association: { singular: 'stowarzyszenie', plural: 'Stowarzyszenia' },
  company: { singular: 'spółka', plural: 'Spółki' },
  other: { singular: 'inny podmiot rejestrowy', plural: 'Inne podmioty rejestrowe' },
};

export const ORGANISATION_KIND_ORDER: OrganisationKind[] = ['foundation', 'association', 'company', 'other'];

/** Grupy typów materiałów w Bazie → kategorie ArticleCategory używane przez /api/feed/?categories=. */
export const MATERIAL_GROUPS = [
  { key: 'artykuly', label: 'Artykuły', categories: ['article', 'opinion', 'context', 'mention'] },
  { key: 'reportaze', label: 'Reportaże', categories: ['reportage'] },
  { key: 'wywiady', label: 'Wywiady', categories: ['interview', 'podcast'] },
  { key: 'dokumenty', label: 'Dokumenty', categories: ['document', 'legislation', 'parliamentary_print', 'voting'] },
  { key: 'filmy', label: 'Filmy', categories: ['video'] },
  { key: 'posty', label: 'Posty', categories: ['tweet'] },
  { key: 'komunikaty', label: 'Komunikaty', categories: ['statement'] },
] as const;

export type MaterialGroupKey = typeof MATERIAL_GROUPS[number]['key'];
export const ALL_GROUP_CATEGORIES: string[] = MATERIAL_GROUPS.flatMap(group => [...group.categories]);

export function groupOfCategory(category: string): MaterialGroupKey | null {
  return MATERIAL_GROUPS.find(group => (group.categories as readonly string[]).includes(category))?.key ?? null;
}

const X_HANDLE = /^[A-Za-z0-9_]{1,15}$/;

/** Konto X pokazujemy tylko przy kompletnym rekordzie: poprawny handle, adres x.com tego handle'a i link do dowodu. */
export function verifiedXAccount(figure: Pick<PublicFigureDetail, 'x_account'>): VerifiedXAccount | null {
  const account = figure.x_account;
  if (!account || !X_HANDLE.test(account.handle)) return null;
  if (account.url !== `https://x.com/${account.handle}`) return null;
  if (!/^https?:\/\//i.test(account.evidence_url)) return null;
  return account;
}

export function getPublicFigures(query = '', roleCategory = '', page = 1) {
  const params = new URLSearchParams({ page: String(page), page_size: '30' });
  if (query) params.set('q', query);
  if (roleCategory) params.set('role_category', roleCategory);
  const suffix = params.toString() ? `?${params}` : '';
  return apiFetch<{ count: number; page: number; page_size: number; results: PublicFigureSummary[] }>(`/api/public-figures/${suffix}`);
}

export function getPublicFigure(id: number) {
  return apiFetch<PublicFigureDetail>(`/api/public-figures/${id}/`);
}

export function usePublicFigures(query: string, roleCategory: string, page = 1) {
  return useQuery({ queryKey: ['public-figures', query, roleCategory, page], queryFn: () => getPublicFigures(query, roleCategory, page), retry: false, staleTime: 60_000 });
}

export function usePublicFigure(id: number | null) {
  return useQuery({ queryKey: ['public-figure', id], queryFn: () => getPublicFigure(id!), enabled: id !== null, retry: false, staleTime: 60_000 });
}

/** GET /api/public-figures/<id>/slad/ - bezpłatny „Ślad w dokumentach” (backend/news/przeszlosc_osoba.py: free_trace). */
export type PublicFigureTrace = {
  available: boolean;
  reason: string;
  votes: Array<{ date: string | null; title: string; vote: string; club: string; club_vote: string; relation: '' | 'zgodnie z klubem' | 'inaczej niż klub' | 'brak większości w klubie'; url: string }>;
  documents: Array<{ kind: string; label: string; title: string; date: string | null; url: string; answered: boolean | null }>;
  year: { votes: number; documents: number };
  full_profile: { url: string; features: string[] } | null;
};

export function usePublicFigureTrace(id: number) {
  return useQuery({ queryKey: ['public-figure-trace', id], queryFn: () => apiFetch<PublicFigureTrace>(`/api/public-figures/${id}/slad/`), retry: false, staleTime: 300_000 });
}
