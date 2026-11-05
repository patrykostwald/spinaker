import Link from "next/link";
import { exportHref, type ExportDataset } from "../lib/exports";

/** „Pobierz dane (CSV / JSON)”: linki do eksportu z tymi samymi filtrami, które są aktywne na liście. */
export function DataExport({ dataset, params, className }: {
  dataset: ExportDataset; params?: Record<string, string | number | undefined | null>; className?: string;
}) {
  const filtered = Object.values(params ?? {}).some(value => value !== undefined && value !== null && String(value) !== "");
  return <p className={`sc-data-export${className ? ` ${className}` : ""}`}>
    <span>Pobierz dane{filtered ? " (z aktywnymi filtrami)" : ""}:</span>
    <a href={exportHref(dataset, "csv", params)} download>CSV</a>
    <a href={exportHref(dataset, "json", params)} download>JSON</a>
    <Link href="/dane">Dane i licencja</Link>
  </p>;
}
