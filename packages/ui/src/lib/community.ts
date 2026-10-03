/** Nitki czytelników - typy i zapytania do /api/community/ (backend/news/community.py). */
import { ApiError, apiFetch, apiWrite } from "./api";

export type ThreadElement = ({ box_type?: 'post' | 'claim' | 'source' | 'technique' | 'diagnosis' | 'message'; x_handle?: string; diagnosis_id?: number | null; intensity?: number | null; body?: string; source_name?: string; published_date?: string | null } & (
  | { kind: "article"; id: number; title: string; url: string; category: string; published_date: string | null; source_name: string; note: string; link_note?: string; position: number }
  | { kind: "link"; id: number; title: string; url: string; domain: string; title_origin: "publisher" | "reader" | "system"; hidden?: boolean; note: string; link_note?: string; position: number }));

export type CommunityThreadSummary = {
  id: number;
  title: string;
  description: string;
  author: string;
  display_name?: string;
  x_profile?: string | null;
  narrative?: boolean;
  continues?: number | null;
  continuations?: number[];
  is_ai?: boolean;
  diagnosis_id?: number | null;
  author_id?: number;
  topics?: string[];
  published_at: string | null;
  updated_at: string;
  items_count: number;
  preview: ThreadElement[] | null;
  opinions: { positive: number; doubt?: number; negative: number };
  comments_count?: number;
};

export type CommunityThreadDetail = CommunityThreadSummary & { items: ThreadElement[]; is_owner: boolean };

type ResolvedElement = ThreadElement extends infer Element ? Element extends ThreadElement ? Omit<Element, "note" | "link_note" | "position"> : never : never;
export type ResolvedLink = { item: ResolvedElement; status: "in_base" | "existing_link" | "created" };

export const getCommunityThreads = (page = 1, q = "", author = "", options: { ai?: '1'; featured?: '1'; sort?: 'new' | 'best' | 'hot' | 'comments'; topic?: string; article_id?: number; figure_id?: number; url?: string } = {}) => {
  const params = new URLSearchParams({ page: String(page) });
  if (q) params.set("q", q);
  if (author) params.set("author", author);
  Object.entries(options).forEach(([key, value]) => { if (value) params.set(key, String(value)); });
  return apiFetch<{ results: CommunityThreadSummary[]; next_page: number | null; context_filtered?: boolean }>(`/api/community/threads/?${params}`);
};
export const getCommunityThread = (id: number | string) => apiFetch<CommunityThreadDetail>(`/api/community/threads/${id}/`);
/** Link do nitki. `needsTitle` - strona nie podała tytułu, czytelnik musi go przepisać. */
export async function resolveLink(url: string, title = ""): Promise<ResolvedLink | { needsTitle: true; message: string }> {
  const csrf = await apiFetch<{ csrfToken: string }>("/api/auth/csrf/");
  const response = await fetch("/api/community/links/", {
    method: "POST", credentials: "include", cache: "no-store",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf.csrfToken },
    body: JSON.stringify({ url, title }),
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 422 && data.needs_title) return { needsTitle: true, message: data.detail };
  if (!response.ok) {
    const detail = data.detail || data.url?.[0] || data.title?.[0];
    throw new ApiError(response.status, typeof detail === "string" ? detail : "Nie udało się dodać linku.");
  }
  return data as ResolvedLink;
}
export const reportCommunityThread = (id: number, reason: string, details = "") =>
  apiWrite<{ status: string }>(`/api/community/threads/${id}/report/`, { reason, details });

export const REPORT_REASONS = [
  { value: "spam", label: "Spam" },
  { value: "abuse", label: "Naruszenie zasad" },
  { value: "privacy", label: "Dane prywatne" },
  { value: "copyright", label: "Naruszenie praw autorskich" },
  { value: "other", label: "Inne" },
];
