/** Klinika spinu - typy i zapytania do /api/clinic/ (backend/news/clinic.py). */
import type { CSSProperties } from "react";
import { apiFetch, apiWrite } from "./api";

/** Etykiety wspólne dla panelu głosów i pełnej diagnozy. */
export function agreementLabel(value: string | null | undefined): string {
  const match = value?.match(/^(\d+)\s*\/\s*(\d+)$/);
  return match ? `Zgodność oceny: ${match[1]} z ${match[2]} modeli` : "Zgodność oceny: brak danych";
}
export function techniqueLabel(count: number): string {
  return count === 1 ? "technika" : count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 12 || count % 100 > 14) ? "techniki" : "technik";
}
export type Camp = "government" | "opposition";
export type Verdict = "spin" | "partial" | "no_spin" | "unclear";

export type Party = { code: string; short: string; name: string };

export type SpinAuthor = {
  account_id?: number;
  name: string;
  handle: string;
  account_url: string;
  avatar_url: string;
  figure_id: number | null;
  role_title: string;
  party: Party | null;
  eu_group?: string | null;
};

export type SpinCardData = {
  comment_count?: number;
  id: number;
  camp: Camp;
  camp_label: string;
  verdict: Verdict;
  verdict_label: string;
  intensity: number;
  headline: string;
  summary: string;
  technique_names: string[];
  technique_types?: Array<{ name: string; category?: string; family?: string }>;
  claims?: Array<Pick<SpinClaim, "assessment">>;
  council?: { members: Array<{ model: string; verdict: string | null; intensity: number | null; status?: string }> } | null;
  scan?: SpinScan;
  technique_groups?: string[];
  post: {
    id: string;
    url: string;
    text: string;
    published_at: string;
    media: Array<{ type: string; url: string; alt: string }>;
    likes: number;
    reposts: number;
  };
  author: SpinAuthor;
  opinions: { positive: number; negative: number };
};

export type SpinClaim = {
  claim: string;
  assessment: "supported" | "contradicted" | "misleading" | "unverified" | "opinion";
  assessment_label: string;
  explanation: string;
  sources: Array<{ url: string; title: string }>;
};

/** Zmiana zdania (backend news/zmiana_zdania.py): wcześniejsza wypowiedź tej samej osoby z innym stanowiskiem. */
export type PositionChange = {
  kind: "post" | "statement" | "vote";
  kind_label: string;
  date: string;
  url: string;
  title: string;
  quote_then: string;
  quote_now: string;
  explanation: string;
  now_date: string;
  now_url: string;
};

/** Jak zadziałało (backend news/odbior_spinu.py): odbiór wpisu dobę później, tylko liczby zbiorcze. */
export type SpinReception = {
  hours: number;
  checked_at: string | null;
  metrics: Array<{ key: string; label: string; before: number | null; after: number }>;
  sample: number;
  shares: Array<{ key: string; label: string; share: number }>;
  sentiment: Array<{ key: string; label: string; share: number }>;
  phrases: Array<{ text: string; count: number }>;
  figures: Array<{ name: string; handle: string; url: string }>;
  verdict: { key: "podchwycony" | "odrzucony" | "podzielony" | "za_malo"; label: string } | null;
  note: string;
};

export type SpinDetailData = Omit<SpinCardData, "claims" | "council"> & {
  plain?: { title: string; gist: string; top: Array<{ name: string; quote: string }> } | null;
  status?: "approved";
  author_replies?: ClinicAuthorReply[];
  scan?: SpinScan;
  /** Gotowy wątek na X (2–3 wpisy): synteza, diagnoza, terapia ze źródłami - backend news/x_share.py. */
  x_share?: string[];
  analysis: string;
  techniques: Array<{ name: string; quote: string; explanation: string; category?: string }>;
  claims: SpinClaim[];
  limitations: string;
  readability_edit?: { at: string | null; original: { headline?: string; summary?: string; analysis?: string } } | null;
  /** Synteza diagnozy do wątku na X (pusta, dopóki darmowy model jej nie przygotuje). */
  x_thread?: string[];
  /** Konsylium Dr. Spina: członkowie (model, werdykt, siła), zgodność, przewodniczący, językoznawca, recenzja, docisk. */
  council?: {
    agreement: string; chair: string; linguist: string; escalated: boolean;
    review: { ok: boolean | null; issues: string[]; model: string; revised?: boolean };
    members: Array<{ model: string; verdict: string | null; intensity: number | null; status?: string }>;
  } | null;
  model: string;
  prompt_version: string;
  created_at: string;
  reviewed_at: string | null;
  auto_published?: boolean;
  notice: string;
  /** Tylko pary powyżej progu (ten sam dla każdej partii); null, gdy nic nie przeszło. */
  position_changes?: { items: PositionChange[]; note: string } | null;
  /** Odbiór po dobie; null, gdy wpisu nie sprawdzano (słaby spin albo funkcja wyłączona). */
  reception?: SpinReception | null;
  /** Raport źródeł 6.10: weryfikacje tej samej tezy (Google Fact Check API) i kopie cytowanych artykułów (Wayback). */
  factchecks?: FactCheck[];
  source_archives?: Record<string, SourceArchive>;
};

export type FactCheck = { publisher: string; rating: string; url: string; title: string; reviewed_claim: string };
export type SourceArchive = { archive_url: string; archived_at: string | null; changed_at: string | null; compare_url: string };

/** Wystąpienie z nagrania Sejmu z diagnozą (backend news/sejm_wideo.py). */
export type SejmVideoSpin = {
  id: number; day: string; place: "sala" | "komisja"; place_label: string;
  person: { id: number; name: string; slug: string } | null;
  title: string; headline: string; summary: string; verdict: string; intensity: number; techniques: string[];
  video_url: string; timecode: string; exact: boolean; source_url: string; committee: string;
};
export const getSejmVideoSpins = (figureId?: number) =>
  apiFetch<{ results: SejmVideoSpin[]; source: { label: string; url: string } }>(`/api/clinic/sejm-wideo/${figureId ? `?osoba=${figureId}` : ""}`);

/** Opcjonalne dane skanera; starsze API nadal korzysta z pól diagnozy. */
export type SpinScan = {
  families?: Record<string, { technique_types?: number }>;
  techniques?: Array<{ category?: string; family?: string; name: string; quote?: string; explanation?: string }>;
  claims?: { checked?: number; supported?: number; misleading?: number; contradicted?: number; opinions?: number; distinct?: number; unverified?: number };
  sources?: number;
  source_domains?: string[];
  scope?: { text?: boolean; image?: boolean; video?: boolean; analyzed?: string[]; not_analyzed?: string[] };
  council?: {
    models?: number; agreement?: string | null; verdict_agreement?: string | null;
    range?: number[] | null; votes?: Array<{ model: string; verdict: string | null; intensity: number | null }>;
    method?: string; chair?: string; escalated?: boolean; reviewed?: boolean;
  };
  synthesis?: { lead?: string; points?: string[] } | null;
  share?: { single?: string };
  diagnosed_at?: string | null;
};

export type ScaleSide = { spin: number; partial: number; no_spin: number; unclear: number; assessed: number; share: number | null };
export type SpinScale = { window_days: number; min_sample: number; enough_data: boolean; government: ScaleSide; opposition: ScaleSide };

export type MessagePost = { url: string; text: string; published_at: string; author: string; handle: string; available?: boolean };
export type MessageStats = {
  version: number; posts: number; authors: number; noise: number; concrete_count: number; concrete_pct: number;
  coherence_authors: number | null; coherence_pct: number | null;
  tone: { atak: number; osiagniecie: number; apel: number; inne: number } | null; tone_classified: number;
};
export type MessagePoint = { title: string; summary: string; post_ids: string[]; authors: string[] };
export type DailyMessage = {
  opinions?: { positive: number; negative: number };
  comment_count?: number;
  thesis?: string; points?: MessagePoint[]; stats?: MessageStats;
  readability_edit?: { original: { thesis?: string; message?: string; analysis?: string } } | null;
  id?: number; day: string; camp?: Camp; message: string; analysis?: string; themes: string[]; posts_count: number; model: string;
  posts?: MessagePost[];
  created_at?: string;
  reviewed_at?: string | null;
  scope?: { date_from: string | null; date_to: string | null; timezone: string };
};

export type InterviewQuote = { name: string; category?: string; quote: string; time: string; seconds: number | null; explanation: string };
export type InterviewClaim = SpinClaim & { time: string; seconds: number | null };
/** Optional participant list; legacy responses are adapted in the reader. */
export type InterviewParticipant = {
  id: string; role: "guest" | "host"; name: string; function?: string;
  verdict?: Verdict; verdict_label?: string; intensity?: number; summary: string;
  techniques: InterviewQuote[]; claims: InterviewClaim[]; limitations?: string;
};
export type Interview = {
  selection_label?: string; selection_method?: string; selection_votes?: number;
  opinions?: { positive: number; negative: number };
  comment_count?: number;
  participants?: InterviewParticipant[];
  id: number; day: string; url: string; video_id: string; title: string; channel: string; thumbnail_url: string;
  guest_name: string; guest_role: string; host_name: string; headline: string; summary: string; overall: string;
  guest: { verdict: Verdict; verdict_label: string; intensity: number; summary: string; techniques: InterviewQuote[]; claims: InterviewClaim[] };
  /** Werdykt i siła prowadzącego - w wywiadach ocenionych od 27.09.2026 (wcześniejsze: puste). */
  host: { summary: string; notes: InterviewQuote[]; verdict?: Verdict; verdict_label?: string; intensity?: number };
  limitations: string; model: string; diagnosed_at: string | null;
};

export type DataPeriod = { generated_at?: string; since?: string | null };

export type ClinicPageData = DataPeriod & {
  notice: string;
  scale: SpinScale;
  messages: Record<Camp, DailyMessage | null>;
  spin_of_day: SpinDetailData | null;
  /** Spin dnia każdej strony; `order` - najpierw strona z mocniejszym (świeższym) spinem. `window`: today | 24h | 72h | latest. */
  spin_by_camp?: { spins: Record<Camp, (SpinDetailData & { window: string; pool?: number; window_label?: string }) | null>; order: Camp[] };
  latest_spin: SpinDetailData | null;
  interview: Interview | null;
  /** Drugi wywiad dnia - dodany ręcznie tego samego dnia (pokazywany pod pierwszym). */
  interview_second?: Interview | null;
  /** Wcześniejsze wywiady dnia (bez aktualnego), najnowsze najpierw. */
  interview_archive?: Interview[];
  message_history: Record<Camp, DailyMessage[]>;
  columns: Record<Camp, SpinCardData[]>;
  accounts_count: number;
  /** Liczniki pracy Kliniki: łącznie i dziś. */
  stats?: Record<"read" | "screened" | "rejected" | "diagnosed" | "spins", { total: number; today: number }> & {
    /** Obie strony obok siebie: konta, przeczytane wpisy, opublikowane diagnozy, spiny (od startu). */
    by_camp?: Record<Camp, { accounts: number; read: number; diagnosed: number; spins: number }>;
  };
};

export type ClinicAccount = {
  handle: string;
  url: string;
  display_name: string;
  camp: Camp;
  camp_label: string;
  figure_id: number | null;
  figure_name: string;
  party: Party | null;
  posts_collected: number;
  posts_screened: number;
  partial_spins: number;
  spins: number;
  last_polled_at: string | null;
};

export const CAMP_LABELS: Record<Camp, string> = { government: "Rządzący", opposition: "Opozycja" };
export const CAMPS: Camp[] = ["government", "opposition"];

export const getClinicPage = () => apiFetch<ClinicPageData>("/api/clinic/");
export type ArchivePage<T> = { results: T[]; next_page: number | null; count: number };
export type InterviewSearchParams = { page?: number; q?: string; channel?: string };
export type MessageDay = { day: string; government: DailyMessage | null; opposition: DailyMessage | null };
export const getClinicInterviews = (params: InterviewSearchParams = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return apiFetch<ArchivePage<Interview> & { channels: string[] }>(`/api/clinic/interviews/?${query}`);
};
export const getClinicInterview = (id: number | string) => apiFetch<Interview>(`/api/clinic/interviews/${encodeURIComponent(id)}/`);
export const getClinicMessages = (page = 1) => apiFetch<ArchivePage<MessageDay>>(`/api/clinic/messages/?page=${page}`);
export const getClinicMessage = (day: string) => apiFetch<MessageDay>(`/api/clinic/messages/${encodeURIComponent(day)}/`);
export type ClinicSearchParams = {
  page?: number;
  page_size?: number;
  q?: string;
  camp?: Camp;
  verdict?: Verdict;
  party?: string;
  /** Identyfikator rekordu konta X (account_id ze statystyk), nie nazwisko ani handle. */
  account?: string;
  technique?: string;
  intensity_min?: number;
  intensity_max?: number;
  date_from?: string;
  date_to?: string;
  sort?: "new" | "strong";
};
export type ClinicSearchResult = {
  results: SpinCardData[];
  next_page: number | null;
  /** Starsze API nie zwraca jeszcze liczby wyników. */
  count?: number;
};
export const searchClinicSpins = (params: ClinicSearchParams = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return apiFetch<ClinicSearchResult>(`/api/clinic/spins/?${query}`);
};
export type ClinicStats = DataPeriod & {
  totals: {
    diagnosed: { total: number; today: number };
    read: { total: number; today: number };
    by_camp: Record<Camp, { accounts: number }>;
  };
  by_party: Record<string, { party: Party | null }>;
  accounts?: Array<{ account_id: number; name: string; handle: string }>;
  technique_definitions?: Record<string, { definition: string; semeval: string[] }>;
  techniques: Record<string, Record<Camp, { count: number; enough_data: boolean }>>;
};
export const getClinicStats = () => apiFetch<ClinicStats>("/api/clinic/stats/");
export const getClinicSpins = (camp: Camp, page: number) =>
  apiFetch<{ results: SpinCardData[]; next_page: number | null }>(`/api/clinic/spins/?camp=${camp}&page=${page}`);
export type ClinicAuthorReply = { id: number; body: string; source_url: string; received_at: string; published_at: string };
export type WithdrawnDiagnosis = {
  id: number; status: "withdrawn"; withdrawn_at: string; withdrawn_reason: string;
  author: SpinAuthor; camp: Camp; camp_label: string; post: { url: string; published_at: string };
  author_replies: ClinicAuthorReply[];
};
export type ClinicCorrection = {
  id: string; type: "withdrawal" | "hiding" | "author_reply" | "revision" | "sejm_withdrawal" | "sejm_hiding"; date: string;
  author: SpinAuthor | null; camp: Camp | null; camp_label: string | null; post_date: string | null;
  diagnosis_url: string | null; reason: string; reply_excerpt: string; notice?: string;
};
export type ClinicCorrectionsData = {
  results: ClinicCorrection[]; count: number; next_page: number | null;
  counts: { published: number; withdrawn: number; hidden: number; replies: number; revisions?: number; sejm?: number };
};
export const getClinicCorrections = (page = 1) => apiFetch<ClinicCorrectionsData>(`/api/clinic/corrections/?page=${page}`);
export const getSpin = (id: number | string) => apiFetch<SpinDetailData | WithdrawnDiagnosis>(`/api/clinic/spins/${id}/`);
export const getClinicAccounts = () => apiFetch<{ results: ClinicAccount[] }>("/api/clinic/accounts/");

/** Usunięte posty polityków - sam fakt (kto, kiedy, czy był spinem), bez treści (zasady X). */
export type DeletedPost = {
  author: SpinAuthor; camp: Camp; camp_label: string; published_at: string; unavailable_at: string;
  verdict: Verdict | ""; verdict_label: string;
  /** Godziny od publikacji do wykrycia usunięcia (górna granica - sprawdzamy co 3 godziny). */
  hours_visible: number;
  /** Kopia w Wayback Machine sprzed usunięcia (tylko link) albo "". */
  archive_url: string;
  archive_search_url: string;
};
export const getClinicDeleted = () =>
  apiFetch<{
    days: number; items: DeletedPost[]; week_by_camp: Partial<Record<Camp, number>>;
    top_deleters: Array<{ author: SpinAuthor; count: number }>;
  }>("/api/clinic/deleted/");

export type FlaggedPost = { id: number; score: number | null; reason: string; screened_by: string; camp_label: string; author: SpinAuthor; post: { url: string; text: string; published_at: string } };

export type ClinicVideoStats = {
  as_of: string;
  warning: string;
  monthly: { month: string; usd: number; pln: number; threshold_pln: number; usd_pln: number };
  periods: Array<{
    label: string; start: string; end: string; unassigned_usd: number;
    camps: Record<Camp, {
      label: string; posts: number; videos: number; full: number; partial: number;
      thumbnail: number; unseen: number; reasons: Record<string, number>;
      unwatched_share: number | null; cost_usd: number; cost_pln: number;
    }>;
  }>;
};
export type ClinicQueue = {
  video_stats: ClinicVideoStats;
  flagged: FlaggedPost[];
  recent: SpinCardData[];
  diagnoses: Array<SpinDetailData & { status: string; triage: Record<string, unknown>; usage: Record<string, unknown> }>;
  messages: Array<{ id: number; day: string; camp: Camp; camp_label: string; message: string; themes: string[]; posts_count: number; model: string }>;
  counts: { pending: number; flagged: number; queued: number; diagnosed_today: number; daily_limit: number; approved: number; rejected: number; not_applicable: number; failed: Record<string, number>; suggestions: number };
};
export const getClinicQueue = () => apiFetch<ClinicQueue>("/api/staff/clinic/queue/");
/** Newsletter: liczba zapisów (tylko dla zespołu). */
export type NewsletterStats = { confirmed: number; pending: number; unsubscribed: number; confirmed_last_7_days: number; smtp_ready: boolean; daily: Array<{ day: string; confirmed: number }> };
export const getNewsletterStats = () => apiFetch<NewsletterStats>("/api/staff/newsletter/");
export const reviewSpin = (id: number, decision: "approve" | "reject") =>
  apiWrite(`/api/staff/clinic/diagnoses/${id}/review/`, { decision });
export const decideFlag = (id: number, decision: "investigate" | "dismiss") =>
  apiWrite(`/api/staff/clinic/diagnoses/${id}/flag/`, { decision });
export const reviewDailyMessage = (id: number, decision: "approve" | "reject") =>
  apiWrite(`/api/staff/clinic/messages/${id}/review/`, { decision });

export const suggestXAccount = (figureId: number, url: string, note = "") =>
  apiWrite<{ status: "received" | "already_suggested"; handle: string }>(`/api/public-figures/${figureId}/x-suggestions/`, { url, note });

/** Udział w procentach z dokładnością do całości; null, gdy brak ocenionych postów. */
export function sharePercent(side: ScaleSide): number | null {
  return side.share === null ? null : Math.round(side.share * 100);
}

/** Kolor siły spinu (właściciel 2.10): pasek i liczba od zielonego (0) przez niebieski (50) do czerwonego (100). */
export const spinVar = (value: number) => ({ "--spin": Math.max(0, Math.min(100, Math.round(value))) }) as CSSProperties;
