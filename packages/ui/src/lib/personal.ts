import { useQuery, type QueryClient } from '@tanstack/react-query';
import { ApiError, apiFetch, apiWrite } from './api';
import { useAccount, type SavedTopic } from './account';

/* ——— Kształty odpowiedzi z backend/news/personal_context.py, profiles.py i accounts.py ——— */

export type PersonalArticleRef = {
  id: number;
  title: string;
  url: string;
  category: string;
  published_date: string | null;
  position?: number;
  /** Tylko w interfejsie — backend nitki nie zwraca nazwy źródła. */
  source_name?: string;
};

export type PersonalContextThread = {
  id: number;
  title: string;
  description: string;
  query: string;
  categories: string[];
  topics: string[];
  source_ids: number[];
  articles: PersonalArticleRef[];
  /** Wszystkie elementy (materiały z Bazy i linki) z notatkami, w kolejności. */
  elements?: import('./community').ThreadElement[];
  is_public?: boolean;
  published_at?: string | null;
  hidden_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type PersonalThreadItemInput = { article_id?: number; link_id?: number; note?: string };

export type PersonalContextThreadInput = {
  title: string;
  description: string;
  query: string;
  categories: string[];
  source_ids: number[];
  article_ids?: number[];
  items?: PersonalThreadItemInput[];
  is_public?: boolean;
};

export type ArticleFavoriteRow = { id: number; article: PersonalArticleRef; created_at: string };
export type ThreadFavoriteRow = { id: number; thread: { id: number; slug: string; title: string }; created_at: string };
export type HistoryRow = { id: number; article_id: number; polarity: 'positive' | 'negative'; body: string; created_at: string };

export type CommentReportReason = 'spam' | 'abuse' | 'privacy' | 'off_topic' | 'other';
export const COMMENT_REPORT_REASONS: Array<{ value: CommentReportReason; label: string }> = [
  { value: 'abuse', label: 'Narusza zasady (np. obraża)' },
  { value: 'privacy', label: 'Ujawnia dane prywatne' },
  { value: 'spam', label: 'Spam lub reklama' },
  { value: 'off_topic', label: 'Nie dotyczy materiału' },
  { value: 'other', label: 'Inny powód' },
];

/** Neutralne etykiety reakcji. Backend przechowuje je jako positive/negative. */
export const REACTION_LABELS = {
  positive: 'Przydatne',
  negative: 'Nieprzydatne',
} as const;

export const MAX_THREAD_ARTICLES = 100;
export const THREAD_LIMITS = { title: 140, description: 500, query: 200 };

export const personalKeys = {
  threads: (ownerId?: number) => ['personal-threads', ownerId] as const,
  thread: (ownerId: number | undefined, id: number) => ['personal-thread', ownerId, id] as const,
  articleFavorites: (ownerId?: number) => ['article-favorites', ownerId] as const,
  threadFavorites: (ownerId?: number) => ['account-favorites', ownerId, 'first-page'] as const,
  topics: (ownerId?: number) => ['account-topics', ownerId] as const,
  history: (ownerId?: number) => ['account-history', ownerId, 'first-page'] as const,
};

/** Endpoint nieobecny na serwerze (np. starsza wersja backendu) — pokazujemy pusty stan, bez udawania zapisu. */
export function isUnavailable(error: unknown) {
  return error instanceof ApiError && (error.status === 404 || error.status === 405 || error.status === 501);
}

export function useOwnerId() {
  const account = useAccount();
  return { account, ownerId: account.data?.authenticated ? account.data.user?.id : undefined };
}

export function usePersonalThreads() {
  const { ownerId } = useOwnerId();
  return useQuery({
    queryKey: personalKeys.threads(ownerId),
    queryFn: () => apiFetch<{ results: PersonalContextThread[] }>('/api/account/context-threads/'),
    enabled: Boolean(ownerId),
    retry: false,
  });
}

export function useArticleFavorites() {
  const { ownerId } = useOwnerId();
  return useQuery({
    queryKey: personalKeys.articleFavorites(ownerId),
    queryFn: () => apiFetch<{ results: ArticleFavoriteRow[] }>('/api/account/article-favorites/'),
    enabled: Boolean(ownerId),
    staleTime: 30_000,
    retry: false,
  });
}

export function useThreadFavorites() {
  const { ownerId } = useOwnerId();
  return useQuery({
    queryKey: personalKeys.threadFavorites(ownerId),
    queryFn: () => apiFetch<{ results: ThreadFavoriteRow[]; next_page: number | null }>('/api/account/favorites/?page=1'),
    enabled: Boolean(ownerId),
    retry: false,
  });
}

export function useSavedTopics() {
  const { ownerId } = useOwnerId();
  return useQuery({
    queryKey: personalKeys.topics(ownerId),
    queryFn: () => apiFetch<{ topics: SavedTopic[]; max_topics: number }>('/api/account/topics/'),
    enabled: Boolean(ownerId),
    retry: false,
  });
}

export function useRecentHistory() {
  const { ownerId } = useOwnerId();
  return useQuery({
    queryKey: personalKeys.history(ownerId),
    queryFn: () => apiFetch<{ results: HistoryRow[]; next_page: number | null }>('/api/account/history/?page=1'),
    enabled: Boolean(ownerId),
    retry: false,
  });
}

export async function setArticleFavorite(cache: QueryClient, ownerId: number, articleId: number, save: boolean) {
  if (save) await apiWrite('/api/account/article-favorites/', { article_id: articleId });
  else await apiWrite(`/api/account/article-favorites/${articleId}/`, {}, 'DELETE');
  await cache.invalidateQueries({ queryKey: personalKeys.articleFavorites(ownerId) });
}

export async function removeThreadFavorite(cache: QueryClient, ownerId: number, threadId: number) {
  await apiWrite(`/api/account/favorites/${threadId}/`, {}, 'DELETE');
  await Promise.all([
    cache.invalidateQueries({ queryKey: ['account-favorites', ownerId] }),
    cache.invalidateQueries({ queryKey: ['thread-favorite', ownerId, threadId] }),
  ]);
}

export function savePersonalThread(input: PersonalContextThreadInput, id?: number) {
  return id
    ? apiWrite<PersonalContextThread>(`/api/account/context-threads/${id}/`, input, 'PATCH')
    : apiWrite<PersonalContextThread>('/api/account/context-threads/', input);
}

export function deletePersonalThread(id: number) {
  return apiWrite<void>(`/api/account/context-threads/${id}/`, {}, 'DELETE');
}

export function reportComment(kind: 'article' | 'thread', opinionId: number, reason: CommentReportReason, details: string) {
  return apiWrite<{ id: number; status: string }>('/api/comments/reports/', {
    [kind === 'article' ? 'article_opinion_id' : 'thread_opinion_id']: opinionId,
    reason,
    details,
  });
}

/** Hasła nitki są przechowywane w jednym polu `query` (do 200 znaków), rozdzielone przecinkami. */
export function splitKeywords(query: string) {
  return query.split(',').map(item => item.trim()).filter(Boolean);
}

export function joinKeywords(keywords: string[]) {
  return keywords.join(', ');
}
