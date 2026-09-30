import type { DataPeriod } from "./clinic";
import { formatDatePl, formatDateTimePl } from "./utils";

/** Czas pobrania nie jest czasem wygenerowania danych. */
export function clinicPeriodLabel(period: DataPeriod | undefined, fetchedAt: number): string {
  if (period?.since && period.generated_at) {
    return `od ${formatDatePl(period.since)} · stan na ${formatDateTimePl(period.generated_at)}`;
  }
  return fetchedAt ? `Pobrano ${formatDateTimePl(new Date(fetchedAt).toISOString())}` : "";
}
