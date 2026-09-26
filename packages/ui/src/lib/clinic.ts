/** Klinika spinu — typy i zapytania do /api/clinic/ (backend/news/clinic.py). */
import { apiFetch, apiWrite } from "./api";

export type Camp = "government" | "opposition";
export type Verdict = "spin" | "partial" | "no_spin" | "unclear";

export type Party = { code: string; short: string; name: string };

export type SpinAuthor = {
  name: string;
  handle: string;
  account_url: string;
  avatar_url: string;
  figure_id: number | null;
  role_title: string;
  party: Party | null;
};

export type SpinCardData = {
  id: number;
  camp: Camp;
  camp_label: string;
  verdict: Verdict;
  verdict_label: string;
  intensity: number;
  headline: string;
  summary: string;
  technique_names: string[];
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
  assessment: "supported" | "contradicted" | "misleading" | "unverified";
  assessment_label: string;
  explanation: string;
  sources: Array<{ url: string; title: string }>;
};

export type SpinDetailData = SpinCardData & {
  analysis: string;
  techniques: Array<{ name: string; quote: string; explanation: string }>;
  claims: SpinClaim[];
  limitations: string;
  model: string;
  prompt_version: string;
  created_at: string;
  reviewed_at: string | null;
  notice: string;
};

export type ScaleSide = { spin: number; partial: number; no_spin: number; unclear: number; assessed: number; share: number | null };
export type SpinScale = { window_days: number; min_sample: number; enough_data: boolean; government: ScaleSide; opposition: ScaleSide };

export type DailyMessage = { day: string; message: string; themes: string[]; posts_count: number; model: string };

export type ClinicPageData = {
  notice: string;
  scale: SpinScale;
  messages: Record<Camp, DailyMessage | null>;
  spin_of_day: SpinDetailData | null;
  columns: Record<Camp, SpinCardData[]>;
  accounts_count: number;
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
  last_polled_at: string | null;
};

export const CAMP_LABELS: Record<Camp, string> = { government: "Rządzący", opposition: "Opozycja" };
export const CAMPS: Camp[] = ["government", "opposition"];

export const getClinicPage = () => apiFetch<ClinicPageData>("/api/clinic/");
export const getClinicSpins = (camp: Camp, page: number) =>
  apiFetch<{ results: SpinCardData[]; next_page: number | null }>(`/api/clinic/spins/?camp=${camp}&page=${page}`);
export const getSpin = (id: number | string) => apiFetch<SpinDetailData>(`/api/clinic/spins/${id}/`);
export const getClinicAccounts = () => apiFetch<{ results: ClinicAccount[] }>("/api/clinic/accounts/");

export type FlaggedPost = { id: number; score: number | null; reason: string; screened_by: string; camp_label: string; author: SpinAuthor; post: { url: string; text: string; published_at: string } };

export type ClinicQueue = {
  flagged: FlaggedPost[];
  diagnoses: Array<SpinDetailData & { status: string; triage: Record<string, unknown>; usage: Record<string, unknown> }>;
  messages: Array<{ id: number; day: string; camp: Camp; camp_label: string; message: string; themes: string[]; posts_count: number; model: string }>;
  counts: { pending: number; flagged: number; queued: number; diagnosed_today: number; daily_limit: number; approved: number; rejected: number; not_applicable: number; failed: Record<string, number>; suggestions: number };
};
export const getClinicQueue = () => apiFetch<ClinicQueue>("/api/staff/clinic/queue/");
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
