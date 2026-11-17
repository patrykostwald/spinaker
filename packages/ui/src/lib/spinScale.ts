/**
 * Jedna miara siły spinu w całym serwisie (v3, właściciel 13.10.2026): trzy czyste strefy koloru,
 * bez mieszania niebieskiego z czerwonym (dawało brudny fiolet).
 *   0-33 zielony (--sc-spin-lo), 34-66 niebieski (--sc-spin-mid), 67-100 czerwony (--sc-spin-hi).
 */
export type SpinZone = "lo" | "mid" | "hi";

export function clampSpin(value: number): number {
  return Math.max(0, Math.min(100, Math.round(Number.isFinite(value) ? value : 0)));
}

export function spinZone(value: number): SpinZone {
  const v = clampSpin(value);
  return v <= 33 ? "lo" : v <= 66 ? "mid" : "hi";
}

export const SPIN_ZONE_LABELS: Record<SpinZone, string> = { lo: "zielona do 33", mid: "niebieska do 66", hi: "czerwona od 67" };

/** Inicjały do awatara: dwie pierwsze litery imienia i nazwiska (bez znaków specjalnych). */
export function initials(name: string | null | undefined): string {
  const parts = (name ?? "").replace(/[^\p{L}\s-]/gu, " ").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  const first = parts[0][0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] ?? "" : parts[0][1] ?? "";
  return (first + last).toUpperCase();
}
