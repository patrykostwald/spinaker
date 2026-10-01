"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../../lib/api";
import { getSpin, getClinicInterview } from "../../lib/clinic";
import { CLINIC_HISTORY_EVENT, CLINIC_HISTORY_KEY, readClinicHistory, writeClinicHistory, visitKey, type ClinicVisit } from "../../lib/clinicHistory";
import { SectionHeader } from "../../kit/SectionHeader";
import { HomeSpinScanner } from "../../kit/home/HomeSpinScanner";
import { InterviewScanner } from "./InterviewScanner";
import { ShareSpinOnX, ShareXCardContent } from "./ShareSpinOnX";

function RecentCard({ item }: { item: ClinicVisit }) {
  const [copyStatus, setCopyStatus] = useState("");
  const query = useQuery({
    queryKey: ["clinic-recent", item.type, item.id],
    staleTime: 0, refetchOnMount: "always",
    queryFn: async () => item.type === "diagnosis"
      ? { type: "diagnosis" as const, data: await getSpin(item.id) }
      : { type: "interview" as const, data: await getClinicInterview(item.id) },
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });
  const missing = (query.error instanceof ApiError && query.error.status === 404)
    || (query.data?.type === "diagnosis" && query.data.data.status === "withdrawn");
  useEffect(() => {
    if (missing) writeClinicHistory(readClinicHistory().filter(old => visitKey(old) !== visitKey(item)));
  }, [missing, item.type, item.id]);
  if (missing) return null;
  if (query.isPending || query.isFetching) return <p role="status">Wczytywanie karty…</p>;
  if (query.isError) return <p role="alert">Nie udało się wczytać karty. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p>;
  const result = query.data;
  if (result.type === "diagnosis" && result.data.status === "withdrawn") return null;
  const path = item.type === "diagnosis" ? `/klinika/${item.id}` : `/klinika/wywiady/${item.id}`;
  async function copyLink() {
    try { await navigator.clipboard.writeText(new URL(path, window.location.origin).href); setCopyStatus("Link skopiowany."); }
    catch { setCopyStatus("Nie udało się skopiować linku. Użyj menu odnośnika „Otwórz”."); }
  }
  return <div className="sc-clinic-recent__card">
    {result.type === "diagnosis" ? (result.data.status !== "withdrawn" ? <HomeSpinScanner spin={result.data} /> : null) : <InterviewScanner interview={result.data} />}
    <div className="sc-clinic-recent__actions">
      <Link href={path}>Otwórz</Link>
      {result.type === "diagnosis" ? (result.data.status !== "withdrawn" ? <ShareSpinOnX id={item.id} spin={result.data} /> : null)
        : <a className="sc-share-cta" target="_blank" rel="noopener noreferrer" href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(result.data.headline)}&url=${encodeURIComponent(new URL(path, window.location.origin).href)}`}><ShareXCardContent interview /></a>}
      <button type="button" onClick={() => void copyLink()}>Kopiuj link</button>
    </div>
    <p role="status">{copyStatus}</p>
  </div>;
}

export function ClinicRecentlyViewed() {
  const [items, setItems] = useState<ClinicVisit[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => {
    const sync = (event?: Event) => setItems(event instanceof CustomEvent ? event.detail : readClinicHistory());
    const storage = (event: StorageEvent) => { if (!event.key || event.key === CLINIC_HISTORY_KEY) sync(); };
    sync();
    window.addEventListener("storage", storage);
    window.addEventListener(CLINIC_HISTORY_EVENT, sync);
    return () => { window.removeEventListener("storage", storage); window.removeEventListener(CLINIC_HISTORY_EVENT, sync); };
  }, []);
  const active = items.find(item => visitKey(item) === selected) ?? items[0];
  if (!active) return null;
  return <section className="sc-clinic-group sc-clinic-recent" aria-labelledby="clinic-recent-title">
    <SectionHeader titleId="clinic-recent-title" title="Ostatnio przeglądane"
      action={<button type="button" onClick={() => { setItems([]); writeClinicHistory([]); }}>Wyczyść historię</button>} />
    <div className="sc-clinic-recent__chips" role="group" aria-label="Wybierz przeglądaną kartę">
      {items.map(item => <button key={visitKey(item)} type="button" aria-pressed={visitKey(active) === visitKey(item)}
        title={item.title} onClick={() => setSelected(visitKey(item))}>
        <small>{item.type === "diagnosis" ? "Diagnoza" : "Wywiad"}</small><span>{item.title}</span>
      </button>)}
    </div>
    <RecentCard key={visitKey(active)} item={active} />
  </section>;
}
