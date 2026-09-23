import type { Article, Source, ThreadDetail } from '../types';
import { apiFetch } from './api';

export type CategoryOption = { value: string; label: string };
export type PortalConfig = { categories: CategoryOption[]; topics?: CategoryOption[]; sources?: Source[]; source_stats?: { catalog_total: number; active: number; awaiting_response: number }; top_sources: Source[]; editorial: { government: ThreadDetail | null; opposition: ThreadDetail | null }; x_editorial: { configured: boolean; status: string }; platforms?: { youtube: { enabled: boolean; publication: string }; x: { enabled: boolean; publication: string } } };
export type NewsFeed = { results: Article[]; total: number; next_page: number | null; checked_at: string; latest_published_at: string | null; mode: string; selection_note: string; top_sources: Source[] };
export type ContextCount = { category: string; label: string; count: number };
export type ArticleContext = { query: string; keywords: string[]; match_basis: string; counts: ContextCount[]; total: number; timeline: Record<string, Article[]>; next_page: number | null; complete: boolean; checked_at: string };
export function getPortalConfig() { return apiFetch<PortalConfig>('/api/portal/config/'); }
export function getNewsFeed({ mode = 'latest', query = '', categories = [], topics = [], sources = [], platforms = [], page = 1, pageSize = 20, match = 'substring' }: { mode?: string; query?: string; categories?: string[]; topics?: string[]; sources?: number[]; platforms?: ('youtube')[]; page?: number; pageSize?: number; match?: 'substring' | 'words' } = {}) {
  const params = new URLSearchParams({ mode, page: String(page), page_size: String(pageSize) });
  if (query) params.set('q', query);
  if (match === 'words') params.set('match', match);
  if (categories.length) params.set('categories', categories.join(','));
  if (topics.length) params.set('topics', topics.join(','));
  if (sources.length) params.set('sources', sources.join(','));
  if (platforms.length) params.set('platforms', platforms.join(','));
  return apiFetch<NewsFeed>(`/api/feed/?${params}`);
}
