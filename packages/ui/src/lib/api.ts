import type { Article, Paginated, ThreadDetail, ThreadListItem, TimelineResponse } from '../types';
import { typographize } from './typography';
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN ?? process.env.NEXT_PUBLIC_FRONTEND_DOMAIN ?? 'spin.clinic';
export class ApiError extends Error { constructor(public status: number, message?: string) {
  super(message ?? (status === 403 ? 'Brak dostępu. Zaloguj się ponownie.' : status === 404 ? 'Nie znaleziono materiału.' : status === 429 ? 'Zbyt wiele zapytań. Spróbuj ponownie za chwilę.' : 'Nie udało się połączyć z serwisem. Spróbuj ponownie.'));
} }
export async function apiFetch<T>(path: string): Promise<T> {
  const base = typeof window === 'undefined' ? API_URL : '';
  const response = await fetch(`${base}${path}`, {
    cache: 'no-store', credentials: 'include',
    headers: { Accept: 'application/json', 'X-Frontend-Domain': DOMAIN },
  });
  if (!response.ok) throw new ApiError(response.status);
  const data = await response.json() as T;
  // Teksty Kliniki do wyświetlenia: bez jednoliterowych słów na końcu wiersza (nie dotyczy paneli edycji).
  return path.startsWith('/api/clinic') && !/admin|moderat|edit/.test(path) ? typographize(data) : data;
}
export function searchTimeline(q: string, categories = '', fromDate = '', toDate = '', page = 1): Promise<TimelineResponse> {
  const params = new URLSearchParams({ q, page: String(page) });
  if (categories) params.set('categories', categories);
  if (fromDate) params.set('from_date', fromDate);
  if (toDate) params.set('to_date', toDate);
  return apiFetch(`/api/search/?${params}`);
}
export async function getRelatedArticles(id: number): Promise<Article[]> {
  return (await apiFetch<{ related: Article[] }>(`/api/articles/${id}/related/`)).related;
}
export function getThreads(featured = false): Promise<Paginated<ThreadListItem>> {
  return apiFetch(`/api/threads/${featured ? '?featured=true' : ''}`);
}
export function getThread(slug: string): Promise<ThreadDetail> {
  return apiFetch(`/api/threads/${encodeURIComponent(slug)}/`);
}
export function getMe(): Promise<{ authenticated: boolean; is_editor: boolean; is_journalist?: boolean; can_edit_threads?: boolean; can_publish?: boolean; username: string; patronite_url: string; buycoffee_url: string }> {
  return apiFetch('/api/me/');
}
export { API_URL, DOMAIN };

// Błąd zapisu z polami formularza; dziedziczy ApiError, żeby kod sprawdzający status (404 — funkcja jeszcze wyłączona) działał dalej.
export class ApiValidationError extends ApiError {
  constructor(message: string, public fields: Record<string, string> = {}, status = 400) { super(status, message); }
}

export async function apiWrite<T>(path: string, body: unknown, method = 'POST'): Promise<T> {
  const csrf = await apiFetch<{csrfToken: string}>('/api/auth/csrf/');
  const response = await fetch(path, { method, credentials: 'include', cache: 'no-store',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf.csrfToken }, body: JSON.stringify(body) });
  if (!response.ok) {
    let message = 'Nie udało się zapisać. Sprawdź formularz i spróbuj ponownie.';
    const fields: Record<string, string> = {};
    try {
      const labels: Record<string, string> = { name: 'Nazwa', source_type: 'Rodzaj źródła', rss_url: 'Adres RSS', catalog_notes: 'Notatki', catalog_stage: 'Etap', scrape_frequency_minutes: 'Odstęp między pobraniami', is_active: 'Aktywność', scrape_enabled: 'Pobieranie', title: 'Tytuł', url: 'Adres źródła', source_name: 'Nazwa źródła', category: 'Kategoria', published_date: 'Data publikacji', items: 'Materiały', description: 'Opis', evidence_note: 'Uwagi o źródle' };
      const explain = (value: unknown): string => {
        if (typeof value === 'string') return value;
        if (Array.isArray(value)) return value.map(explain).join(' ');
        if (value && typeof value === 'object') return Object.entries(value).map(([key, item]) => `${labels[key] ? labels[key] + ': ' : ''}${explain(item)}`).join(' ');
        return '';
      };
      const data = await response.json();
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        for (const [key, value] of Object.entries(data)) fields[key] = explain(value);
      }
      message = explain(data) || message;
    } catch {}
    throw new ApiValidationError(message, fields, response.status);
  }
  return response.status === 204 ? undefined as T : response.json();
}
