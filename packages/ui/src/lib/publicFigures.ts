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

export type PublicFigureOrganisation = {
  id: number;
  name: string;
  krs_number: string;
  kind: OrganisationKind;
  official_register_url: string;
  public_role: string;
  relation_status: 'current' | 'former';
  evidence_url: string;
  verified_at: string | null;
};

export type PublicFigureVote = { date: string | null; topic: string; vote: string; article_url: string; source: string };

export type PublicFigureVotes =
  | { available: true; source_url: string; results: PublicFigureVote[] }
  | { available: false; reason?: string; results: PublicFigureVote[] };

/**
 * Konto X z backend/news/public_figures.py::verified_x_account_data — obecne wyłącznie po
 * przeglądzie linku z oficjalnego profilu, potwierdzeniu przez oficjalne API X i potwierdzeniu
 * redakcyjnym. W innym wypadku `null`. Interfejs nigdy nie zgaduje handle'a.
 */
export type VerifiedXAccount = { handle: string; url: string; evidence_url: string; posts_collected: number };
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

export function getPublicFigures(query = '', roleCategory = '') {
  const params = new URLSearchParams();
  if (query) params.set('q', query);
  if (roleCategory) params.set('role_category', roleCategory);
  const suffix = params.toString() ? `?${params}` : '';
  return apiFetch<{ results: PublicFigureSummary[] }>(`/api/public-figures/${suffix}`);
}

export function getPublicFigure(id: number) {
  return apiFetch<PublicFigureDetail>(`/api/public-figures/${id}/`);
}

export function usePublicFigures(query: string, roleCategory: string) {
  return useQuery({ queryKey: ['public-figures', query, roleCategory], queryFn: () => getPublicFigures(query, roleCategory), retry: false, staleTime: 60_000 });
}

export function usePublicFigure(id: number | null) {
  return useQuery({ queryKey: ['public-figure', id], queryFn: () => getPublicFigure(id!), enabled: id !== null, retry: false, staleTime: 60_000 });
}
