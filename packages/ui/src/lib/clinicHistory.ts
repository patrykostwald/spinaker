import type { Camp, Verdict } from "./clinic";

export const CLINIC_HISTORY_KEY = "spin.clinic:history:v1";
export const CLINIC_HISTORY_EVENT = "clinic-history-change";
export type ClinicVisit = {
  type: "diagnosis" | "interview"; id: number; title: string; camp: Camp | null;
  verdict: Verdict; intensity: number; author?: string; guest?: string; viewed_at: string;
};
export const visitKey = (item: Pick<ClinicVisit, "type" | "id">) => `${item.type}:${item.id}`;

export function readClinicHistory(): ClinicVisit[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(CLINIC_HISTORY_KEY) || "[]");
    if (!Array.isArray(value)) return [];
    const seen = new Set<string>();
    return value.filter((item): item is ClinicVisit => {
      if (!item || !["diagnosis", "interview"].includes(item.type) || !Number.isSafeInteger(item.id) || item.id <= 0
        || typeof item.title !== "string" || ![null, "government", "opposition"].includes(item.camp)
        || !["spin", "partial", "no_spin", "unclear"].includes(item.verdict)
        || !Number.isFinite(item.intensity) || item.intensity < 0 || item.intensity > 100
        || typeof item.viewed_at !== "string" || !Number.isFinite(Date.parse(item.viewed_at))
        || (item.type === "diagnosis" ? typeof item.author !== "string" : typeof item.guest !== "string")) return false;
      const key = visitKey(item);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 12);
  } catch { return []; }
}

export function writeClinicHistory(items: ClinicVisit[]) {
  try {
    if (items.length) localStorage.setItem(CLINIC_HISTORY_KEY, JSON.stringify(items.slice(0, 12)));
    else localStorage.removeItem(CLINIC_HISTORY_KEY);
  } catch { /* Historia jest opcjonalna także przy zablokowanej pamięci. */ }
  window.dispatchEvent(new CustomEvent(CLINIC_HISTORY_EVENT, { detail: items.slice(0, 12) }));
}

export function rememberClinicVisit(item: Omit<ClinicVisit, "viewed_at">) {
  writeClinicHistory([{ ...item, viewed_at: new Date().toISOString() },
    ...readClinicHistory().filter(old => visitKey(old) !== visitKey(item))]);
}
