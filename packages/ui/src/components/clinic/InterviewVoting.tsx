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

type Candidate = { id: number; video_id: string; title: string; guest_name: string; channel: string;
  duration: number; views: number; votes: number; thumbnail_url: string };
type Ballot = {
  day: string; closes_at: string; open: boolean; accounts_enabled: boolean; mine: number | null;
  min_votes?: number; min_account_days?: number; messages_left?: number;
  dr_spin?: { id: number; video_id: string; title: string; guest_name: string; channel: string; ready: boolean } | null;
  results: Candidate[];
};
const endpoint = "/api/clinic/interviews/voting/";
const dateLabel = (date: string) => new Date(`${date}T12:00:00`).toLocaleDateString("pl-PL", { day: "numeric", month: "long" });
const durationLabel = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
const votesWord = (n: number) => n === 1 ? "głos" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "głosy" : "głosów";

function timeLeft(ms: number) {
  if (ms <= 0) return "";
  const hours = Math.floor(ms / 3_600_000), minutes = Math.floor((ms % 3_600_000) / 60_000);
  return hours ? `${hours} h ${minutes} min` : `${minutes} min`;
}

/** Dwa wywiady dnia (właściciel 4.10): pierwszy wybiera Dr. Spin, drugi czytelnicy głosami według jawnych zasad. */
export function InterviewVoting() {
  const account = useAccount();
  const featureEnabled = useFeature("ACCOUNTS_ENABLED");
  const ownerId = account.data?.user?.id;
  const verified = Boolean(ownerId && emailVerified(account.data));
  const cache = useQueryClient();
  const [day, setDay] = useState("");
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState("");
  const [login, setLogin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [addError, setAddError] = useState("");
  const [status, setStatus] = useState("");
  const [now, setNow] = useState(0);
  useEffect(() => {
    const requestedDay = new URLSearchParams(window.location.search).get('day');
    if (requestedDay && /^\d{4}-\d{2}-\d{2}$/.test(requestedDay)) setDay(requestedDay);
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);
  const query = useQuery({ queryKey: ["interview-voting", day, ownerId],
    queryFn: () => apiFetch<Ballot>(`${endpoint}${day ? `?day=${day}` : ""}`), refetchInterval: 30_000 });
  const data = query.data;
  const enabled = featureEnabled && data?.accounts_enabled;
  const open = Boolean(data?.open && now < Date.parse(data.closes_at));
  const today = now ? new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Warsaw", year: "numeric", month: "2-digit", day: "2-digit" }).format(now) : "";
  const isToday = Boolean(day && day === today);
  const minVotes = data?.min_votes ?? 3;
  const minDays = data?.min_account_days ?? 0;
  const leader = data?.results.find(row => row.votes > 0 && row.video_id !== data?.dr_spin?.video_id);
  const refresh = () => cache.invalidateQueries({ queryKey: ["interview-voting"] });
  const reset = (next: string) => { setDay(next); setError(""); setAddError(""); setStatus(""); };
  async function run(task: () => Promise<unknown>, done: string, fail: (text: string) => void, fallback: string) {
    if (busy || !data) return;
    setBusy(true); setError(""); setAddError(""); setStatus("");
    try { await task(); setStatus(done); await refresh(); }
    catch (problem) { fail(problem instanceof Error ? problem.message : fallback); }
    finally { setBusy(false); }
  }
  const vote = (id: number) => run(() => apiWrite(`${endpoint}vote/`, { day: data!.day, candidate_id: id }),
    "Głos zapisany. Do 7:00 możesz go zmienić.", setError, "Nie udało się zapisać głosu.");
  const add = (event: FormEvent) => { event.preventDefault();
    void run(async () => { await apiWrite(endpoint, { day: data!.day, url: url.trim() }); setUrl(""); },
      "Wywiad jest na liście. Możesz na niego zagłosować.", setAddError, "Nie udało się dodać wywiadu."); };
  const send = (event: FormEvent) => { event.preventDefault();
    void run(async () => { await apiWrite(`${endpoint}message/`, { day: data!.day, text: message.trim() }); setMessage(""); },
      "Wiadomość trafiła do zespołu Dr. Spina.", setAddError, "Nie udało się wysłać wiadomości."); };
  return <section className="sc-interview-voting">
    <ClinicNav />
    <header className="sc-interview-voting__header">
      <h1>Drugi wywiad dnia wybierają czytelnicy</h1>
      <p>{data ? !enabled ? "Głosowanie ruszy wkrótce." : open ? `Głosowanie trwa jeszcze ${timeLeft(Date.parse(data.closes_at) - now)}, do 7:00 (${dateLabel(data.closes_at.slice(0, 10))}).` : "Głosowanie zakończone o 7:00." : "Wczytywanie głosowania…"}</p>
    </header>
    {enabled ? <nav className="sc-interview-voting__days" aria-label="Dzień wywiadów">
      <Button variant="quiet" aria-pressed={!isToday} onClick={() => reset("")}>Wczoraj</Button>
      {today ? <Button variant="quiet" aria-pressed={isToday} onClick={() => reset(today)}>Dzisiaj</Button> : null}
    </nav> : null}
    {query.isError ? <p role="alert">Nie udało się wczytać kandydatów. <Button onClick={() => void query.refetch()}>Spróbuj ponownie</Button></p> : null}
    {data ? <>
      <div className="sc-iv-pair">
        <article className="sc-iv-pick">
          <span className="sc-iv-pick__k">Wybór Dr. Spina</span>
          {data.dr_spin ? <>
            <strong>{data.dr_spin.guest_name || data.dr_spin.title}</strong>
            <span>{data.dr_spin.channel}</span>
            {data.dr_spin.ready ? <Link href={`/klinika/wywiady/${data.dr_spin.id}`}>Zobacz diagnozę</Link> : <span>Diagnoza w przygotowaniu</span>}
          </> : <><strong>Najczęściej oglądana rozmowa polityka</strong><span>Dr. Spin wybiera ją o 7:00 z kanałów, które obserwujemy.</span></>}
        </article>
        <article className="sc-iv-pick" data-readers="">
          <span className="sc-iv-pick__k">Wybór czytelników</span>
          {leader ? <>
            <strong>{leader.guest_name || leader.title}</strong>
            <span>{leader.channel}</span>
            <span><b>{leader.votes}</b> {votesWord(leader.votes)}{leader.votes < minVotes ? ` · potrzeba co najmniej ${minVotes}` : open ? " · prowadzi" : " · wygrywa"}</span>
          </> : <><strong>Jeszcze bez głosów</strong><span>Wygrywa wywiad z największą liczbą głosów, co najmniej {minVotes}.</span></>}
        </article>
      </div>
      <details className="sc-iv-rules">
        <summary>Zasady wyboru</summary>
        <ol>
          <li><b>Materiał</b> rozmowa z politykiem na YouTube, co najmniej 8 minut, opublikowana {dateLabel(data.day)}.</li>
          <li><b>Gość</b> inny niż w wyborze Dr. Spina i niż wczoraj. Ta sama miara dla rządzących i opozycji.</li>
          <li><b>Głos</b> jeden na osobę, można go zmienić do 7:00. Konto z potwierdzonym e-mailem{minDays ? `, założone co najmniej ${minDays} dni temu` : ""}.</li>
          <li><b>Wynik</b> wygrywa najwięcej głosów, co najmniej {minVotes}. Remis rozstrzyga większy zasięg.</li>
          <li><b>Diagnoza</b> rano po 7:00, tak samo jak wywiad Dr. Spina: gość i prowadzący.</li>
        </ol>
      </details>
      <div className="sc-interview-voting__list">{data.results.map(row => <article className="sc-interview-voting__row" key={row.id} data-mine={data.mine === row.id ? "" : undefined}>
        <img src={row.thumbnail_url} alt="" width={96} height={54} loading="lazy" />
        <div className="sc-interview-voting__info">
          <strong title={row.guest_name || row.title}>{row.guest_name || row.title}</strong>
          <a href={`https://www.youtube.com/watch?v=${row.video_id}`} target="_blank" rel="noopener noreferrer" title={row.title}>{row.title}</a>
          <span title={row.channel}>{row.channel} · {durationLabel(row.duration)}</span>
        </div>
        <div className="sc-interview-voting__actions">
          <span aria-label={`Liczba głosów: ${row.votes}`}><b>{row.votes.toLocaleString("pl-PL")}</b> {votesWord(row.votes)}</span>
          {row.video_id === data.dr_spin?.video_id ? <span>wybór Dr. Spina</span>
            : enabled && verified ? <Button variant="quiet" disabled={busy || !open || data.mine === row.id} aria-pressed={data.mine === row.id} aria-label={data.mine === row.id ? `Twój głos: ${row.title}` : `Głosuj: ${row.title}`} onClick={() => void vote(row.id)}>{data.mine === row.id ? "Twój głos" : "Głosuj"}</Button> : null}
        </div>
      </article>)}</div>
      {!data.results.length ? <p className="sc-interview-voting__note">Nie ma jeszcze kandydatów na ten dzień. Dodaj pierwszy wywiad.</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {enabled && !account.isPending && !ownerId ? <Button onClick={() => setLogin(true)}>Zaloguj się, żeby głosować</Button> : null}
      {enabled && ownerId && !verified ? <p>Potwierdź e-mail, żeby głosować i dodawać wywiady. <Link href="/konto">Przejdź do konta</Link>.</p> : null}
      {enabled && verified ? <div className="sc-iv-forms">
        {open ? <form className="sc-interview-voting__add" onSubmit={add}>
          <label htmlFor="interview-url">Zaproponuj wywiad</label>
          <div><input id="interview-url" type="url" required maxLength={500} placeholder="Link z YouTube" value={url} disabled={busy} onChange={event => setUrl(event.target.value)} aria-describedby="interview-add-note" /><Button type="submit" variant="quiet" disabled={busy || !url.trim()}>Dodaj</Button></div>
          <p id="interview-add-note">Do 3 propozycji dziennie. Sprawdzamy długość, datę i gościa.</p>
        </form> : null}
        <form className="sc-interview-voting__add" onSubmit={send}>
          <label htmlFor="interview-message">Napisz do Dr. Spina</label>
          <div><input id="interview-message" type="text" minLength={10} maxLength={500} placeholder="Temat, rozmowa albo uwaga" value={message} disabled={busy || !data.messages_left} onChange={event => setMessage(event.target.value)} aria-describedby="interview-message-note" /><Button type="submit" variant="quiet" disabled={busy || message.trim().length < 10 || !data.messages_left}>Wyślij</Button></div>
          <p id="interview-message-note">Czyta zespół, nie publikujemy. {data.messages_left ? `Zostało ${data.messages_left} na ten dzień.` : "Limit na ten dzień wykorzystany."}</p>
        </form>
        <p className="sc-iv-forms__err" role="alert">{addError}</p>
      </div> : null}
    </> : null}
    <p role="status">{status}</p>
    {enabled ? <AccountDialog open={login} onClose={() => setLogin(false)} /> : null}
  </section>;
}
