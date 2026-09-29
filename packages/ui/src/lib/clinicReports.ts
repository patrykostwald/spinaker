import { apiFetch } from "./api";
import type { Camp, SpinDetailData, SpinScale, Verdict } from "./clinic";

export type ReportTechnique = { name: string; count: number; category?: string; original_names?: string[] };
export type ClinicReport = {
  week_start: string; week_end: string; summary: string; created_at: string;
  diagnoses: Record<Camp, number>; scale: SpinScale; spin_of_week: SpinDetailData | null;
  techniques: Record<Camp, ReportTechnique[]>; deleted: Record<Camp, number>;
  interviews: Array<{ id: number; day: string; headline: string; guest: string; channel: string; verdict: Verdict | "" }>;
};
export type ReportResponse = { report: ClinicReport | null; archive: Array<{ week_start: string; week_end: string }> };
export const getClinicReport = (week?: string) => apiFetch<ReportResponse>(week
  ? `/api/clinic/report/${encodeURIComponent(week)}/` : "/api/clinic/report/");

const MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"];
export function reportWeekLabel(start: string, end: string): string {
  const [ys, ms, ds] = start.split("-").map(Number);
  const [ye, me, de] = end.split("-").map(Number);
  if (ms === me && ys === ye) return `${ds}–${de} ${MONTHS[me - 1]} ${ye}`;
  return `${ds} ${MONTHS[ms - 1]}${ys === ye ? "" : ` ${ys}`} – ${de} ${MONTHS[me - 1]} ${ye}`;
}
export function reportPublicationLabel(iso: string): string {
  const date = new Date(iso);
  const day = new Intl.DateTimeFormat("pl-PL", { timeZone: "Europe/Warsaw", day: "numeric", month: "long" }).format(date);
  const time = new Intl.DateTimeFormat("pl-PL", { timeZone: "Europe/Warsaw", hour: "2-digit", minute: "2-digit" }).format(date);
  return `${day}, ${time}`;
}
