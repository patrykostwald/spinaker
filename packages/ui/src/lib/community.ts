/** Tropy czytelników - typy i zapytania do /api/community/ (backend/news/community.py). */
import { ApiError, apiFetch, apiWrite } from "./api";

export type ThreadElement = ({ item_id?: number; box?: boolean; role?: '' | 'teza' | 'fakt' | 'kontekst' | 'pytanie' | 'opinia' | 'wniosek'; link_kind?: '' | 'bo' | 'ale' | 'czy_na_pewno' | 'przeczy' | 'wynika_z' | 'jak'; image_url?: string; box_type?: 'post' | 'claim' | 'source' | 'technique' | 'diagnosis' | 'message' | 'print' | 'amendment' | 'consultation' | 'registry' | 'declaration' | 'summary'; x_handle?: string; diagnosis_id?: number | null; intensity?: number | null; body?: string; source_name?: string; published_date?: string | null } & (
  | { kind: "article"; id: number; title: string; url: string; category: string; published_date: string | null; source_name: string; note: string; link_note?: string; position: number }
  | { kind: "link"; id: number; title: string; url: string; domain: string; title_origin: "publisher" | "reader" | "system"; hidden?: boolean; note: string; link_note?: string; position: number }));

export type CommunityThreadSummary = {
  id: number;
  title: string;
  description: string;
  /** Rodzaj spinki (właściciel 6.10), np. diagnoza, kontekst; patrz lib/threadKind.ts. */
  kind?: string;
  kind_label?: string;
  author: string;
  display_name?: string;
  x_profile?: string | null;
  /** Kolor nicka autora (puste u Dr. Spina i bez wybranego koloru). */
  author_color?: string;
  narrative?: boolean;
  signal_kind?: '' | 'lobbying' | 'new_narrative';
  admission?: { mode?: 'first'; positive: number; needed: number; ratio: number; ratio_needed: number; days_left: number; open: boolean } | null;
  confidence?: 'niski' | 'średni' | 'wysoki' | null;
  continues?: number | null;
  continuations?: number[];
  /** Przepięcie: id spinki, którą ten autor przepiął, i przepięcia tej spinki (właściciel 3.10). */
  repin_of?: number | null;
  repins?: number[];
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
  score?: { percent: number; reactions: number };
  contexts_count?: number;
  sources_count?: number;
  top_comments?: { id: number; author: string; body: string; created_at: string; author_color?: string }[];
  clips?: { positive: number; doubt: number; negative: number }[];
  boxes?: { positive: number; doubt: number; negative: number }[];
};

export type CommunityThreadDetail = CommunityThreadSummary & { items: ThreadElement[]; is_owner: boolean };

type ResolvedElement = ThreadElement extends infer Element ? Element extends ThreadElement ? Omit<Element, "note" | "link_note" | "position"> : never : never;
export type ResolvedLink = { item: ResolvedElement; status: "in_base" | "existing_link" | "created" };

export const getCommunityThreads = (page = 1, q = "", author = "", options: { ai?: '1'; featured?: '1'; source?: 'all' | 'drspin' | 'readers' | 'izba'; sort?: 'new' | 'best' | 'hot' | 'comments'; topic?: string; article_id?: number; figure_id?: number; url?: string } = {}) => {
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

export type StepPart = 'box' | 'context';
export type StepState = { item_id: number; part: StepPart; counts: { positive: number; doubt: number; negative: number }; mine: 'positive' | 'doubt' | 'negative' | null };
export type StepsData = { steps: StepState[]; progress: { done: number; total: number }; score: { percent: number; reactions: number } };
export const getThreadSteps = (id: number) => apiFetch<StepsData>(`/api/community/threads/${id}/steps/`);
export const rateThreadStep = (id: number, item_id: number, part: StepPart, polarity: string) =>
  apiWrite<StepsData>(`/api/community/threads/${id}/steps/`, { item_id, part, polarity });
export type BoxDetail = { item: ThreadElement; position: number; counts: { positive: number; doubt: number; negative: number };
  context_before: string; context_after: string; other_threads: { id: number; title: string }[] };
export const getThreadBox = (id: number, itemId: number) => apiFetch<BoxDetail>(`/api/community/threads/${id}/boxes/${itemId}/`);
