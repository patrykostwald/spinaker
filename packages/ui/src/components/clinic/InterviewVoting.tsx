"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiWrite } from "../../lib/api";
import { emailVerified, useAccount } from "../../lib/account";
import { useFeature } from "../../lib/features";
import { Button } from "../../kit/Button";
import { AccountDialog } from "../AccountDialog";
import { ClinicNav } from "./ClinicNav";

type Ballot = {
  day: string; closes_at: string; open: boolean; accounts_enabled: boolean; mine: number | null;
  results: { id: number; video_id: string; title: string; guest_name: string; channel: string;
    duration: number; views: number; votes: number; thumbnail_url: string }[];
};
const endpoint = "/api/clinic/interviews/voting/";
const dateLabel = (date: string) => new Date(`${date}T12:00:00`).toLocaleDateString("pl-PL", { day: "numeric", month: "long" });
const durationLabel = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

export function InterviewVoting() {
  const account = useAccount();
  const featureEnabled = useFeature("ACCOUNTS_ENABLED");
  const ownerId = account.data?.user?.id;
  const verified = Boolean(ownerId && emailVerified(account.data));
  const cache = useQueryClient();
  const [day, setDay] = useState("");
  const [url, setUrl] = useState("");
  const [login, setLogin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [addError, setAddError] = useState("");
  const [status, setStatus] = useState("");
  const [now, setNow] = useState(0);
  useEffect(() => {
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const query = useQuery({ queryKey: ["interview-voting", day, ownerId],
    queryFn: () => apiFetch<Ballot>(`${endpoint}${day ? `?day=${day}` : ""}`), refetchInterval: 30_000 });
  const data = query.data;
  const enabled = featureEnabled && data?.accounts_enabled;
  const open = Boolean(data?.open && now < Date.parse(data.closes_at));
  const today = now ? new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Warsaw", year: "numeric", month: "2-digit", day: "2-digit" }).format(now) : "";
  const isToday = Boolean(day && day === today);
  const refresh = () => cache.invalidateQueries({ queryKey: ["interview-voting"] });
  async function vote(id: number) {
    if (busy || !data) return;
    setBusy(true); setError(""); setStatus("");
    try {
      await apiWrite(`${endpoint}vote/`, { day: data.day, candidate_id: id });
      setStatus("Głos zapisany. Do 7:00 możesz wybrać inny wywiad.");
      await refresh();
    } catch (error) { setError(error instanceof Error ? error.message : "Nie udało się zapisać głosu."); }
    finally { setBusy(false); }
  }
  async function add(event: FormEvent) {
    event.preventDefault(); if (busy || !data) return;
    setBusy(true); setAddError(""); setStatus("");
    try {
      await apiWrite(endpoint, { day: data.day, url: url.trim() });
      setUrl(""); setStatus("Wywiad jest na liście. Możesz na niego zagłosować.");
      await refresh();
    } catch (error) { setAddError(error instanceof Error ? error.message : "Nie udało się dodać wywiadu."); }
    finally { setBusy(false); }
  }
  return <section className="sc-interview-voting">
    <ClinicNav />
    <header className="sc-interview-voting__header">
      <h1 title={isToday ? "Który wywiad z dzisiaj?" : "Który wywiad z wczoraj?"}>{isToday ? "Który wywiad z dzisiaj?" : "Który wywiad z wczoraj?"}</h1>
      <p>{data ? !enabled ? "Głosowanie ruszy wkrótce." : open ? `Głosowanie do 7:00 (${dateLabel(data.closes_at.slice(0, 10))}, czas Warszawy).` : "Głosowanie zakończone o 7:00 (czas Warszawy)." : "Wczytywanie głosowania…"}</p>
    </header>
    {enabled ? <nav className="sc-interview-voting__days" aria-label="Dzień wywiadów">
      <Button variant="quiet" aria-pressed={!isToday} onClick={() => { setDay(""); setError(""); setAddError(""); setStatus(""); }}>Wczoraj</Button>
      {today ? <Button variant="quiet" aria-pressed={isToday} onClick={() => { setDay(today); setError(""); setAddError(""); setStatus(""); }}>Dzisiaj</Button> : null}
    </nav> : null}
    {query.isError ? <p role="alert">Nie udało się wczytać kandydatów. <Button onClick={() => void query.refetch()}>Spróbuj ponownie</Button></p> : null}
    {data ? <>
      <p className="sc-interview-voting__note">{dateLabel(data.day)} - jeden głos na osobę, można go zmienić. Wygrywa liczba głosów; remis rozstrzyga dotychczasowy ranking zasięgu. Gość nie może wygrać dwa dni z rzędu.</p>
      <div className="sc-interview-voting__list">{data.results.map(row => <article className="sc-interview-voting__row" key={row.id}>
        <img src={row.thumbnail_url} alt="" width={96} height={54} loading="lazy" />
        <div className="sc-interview-voting__info">
          <strong title={row.guest_name || row.title}>{row.guest_name || row.title}</strong>
          <a href={`https://www.youtube.com/watch?v=${row.video_id}`} target="_blank" rel="noopener noreferrer" title={row.title}>{row.title}</a>
          <span title={row.channel}>{row.channel} · {durationLabel(row.duration)}</span>
        </div>
        <div className="sc-interview-voting__actions">
          <span aria-label={`Liczba głosów: ${row.votes}`}><b>{row.votes.toLocaleString("pl-PL")}</b> gł.</span>
          {enabled && verified ? <Button variant="quiet" disabled={busy || !open || data.mine === row.id} aria-pressed={data.mine === row.id} aria-label={data.mine === row.id ? `Twój głos: ${row.title}` : `Głosuj: ${row.title}`} onClick={() => void vote(row.id)}>{data.mine === row.id ? "Twój głos" : "Głosuj"}</Button> : null}
        </div>
      </article>)}</div>
      {!data.results.length ? <p>Nie ma jeszcze kandydatów na ten dzień.</p> : null}
      {enabled && !account.isPending && !ownerId ? <Button onClick={() => setLogin(true)}>Zaloguj się, żeby głosować</Button> : null}
      {enabled && ownerId && !verified ? <p>Potwierdź e-mail, żeby głosować i dodawać wywiady. <Link href="/konto">Przejdź do konta</Link>.</p> : null}
      {enabled && verified && open ? <form className="sc-interview-voting__add" onSubmit={add}>
        <label htmlFor="interview-url">Dodaj wywiad z YouTube</label>
        <div><input id="interview-url" type="url" required maxLength={500} placeholder="Wklej link z YouTube" value={url} disabled={busy} onChange={event => setUrl(event.target.value)} aria-describedby="interview-add-note interview-add-error" /><Button type="submit" disabled={busy || !url.trim()}>{busy ? "Zapisywanie…" : "Dodaj"}</Button></div>
        <p id="interview-add-error" role="alert">{addError}</p>
        <p id="interview-add-note">Do 3 wywiadów na dzień. Minimum 8 minut, rozmowa z politykiem, publikacja {dateLabel(data.day)}.</p>
      </form> : null}
    </> : null}
    {error ? <p role="alert">{error}</p> : null}
    <p role="status">{status}</p>
    {enabled ? <AccountDialog open={login} onClose={() => setLogin(false)} /> : null}
  </section>;
}
