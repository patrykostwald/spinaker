"use client";

import { useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { CAMPS, CAMP_LABELS, getClinicMessage, messageSpinStrength, type Camp, type ClinicPageData, type DailyMessage, type MessagePost } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl, formatTimePl } from "../../lib/utils";
import { initials } from "../../lib/spinScale";
import { Button } from "../Button";
import { ArrowUpRightIcon } from "../icons/ArrowUpRightIcon";
import { BugReportButton } from "../../components/BugReport";
import { CausalChain, CAUSAL_CHAIN_ENABLED as CAUSAL_CHAIN_ON, approvedChainSteps } from "../CausalChain";
import { SpinMeter } from "../SpinMeter";

/** Polska odmiana liczebnika: 1 wpis, 2-4 wpisy, 5+ wpisów. */
export function plural(n: number, one: string, few: string, many: string): string {
  const n10 = n % 10, n100 = n % 100;
  if (n === 1) return one;
  return n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14) ? few : many;
}

const NBSP = " ";
const shortDate = (day: string) => new Intl.DateTimeFormat("pl-PL", { timeZone: "Europe/Warsaw", day: "numeric", month: "short" }).format(new Date(`${day}T12:00:00Z`)).replace(".", "");
const capital = (text: string) => text ? text[0].toLocaleUpperCase("pl-PL") + text.slice(1) : text;
/** Skrócone adresy t.co nie niosą treści - w podglądzie cytatu zastępujemy je „[link]” (pełny wpis pod odnośnikiem). */
const quoteText = (text: string) => text.replace(/https?:\/\/t\.co\/\S+/g, "[link]").replace(/\s+/g, " ").trim();
/** Krótka lista autorów: dwa nazwiska i liczba pozostałych. */
const authorsShort = (authors: string[]) => authors.length <= 2 ? authors.join(" i ") : `${authors.slice(0, 2).join(", ")} i${NBSP}${authors.length - 2}${NBSP}${plural(authors.length - 2, "inna osoba", "inne osoby", "innych osób")}`;

/** Trzy cytaty do karty: najpierw wpisy przypisane do wątków (po jednym na autora), dostępne w źródle. */
function pickQuotes(message: DailyMessage): MessagePost[] {
  const posts = (message.posts ?? []).filter(post => post.available !== false && post.text?.trim());
  const ids = new Set((message.points ?? []).flatMap(point => point.post_ids));
  const ordered = [...posts.filter(post => ids.has(post.url.split("/").pop() ?? "") || ids.has((post as MessagePost & { id?: string }).id ?? "")), ...posts];
  const seen = new Set<string>();
  const result: MessagePost[] = [];
  for (const post of ordered) {
    if (seen.has(post.handle) || result.includes(post)) continue;
    seen.add(post.handle);
    result.push(post);
    if (result.length === 3) break;
  }
  return result;
}

export function PrzekazDniaCard({ data }: { data: ClinicPageData }) {
  const firstCamp = CAMPS.find(camp => data.messages[camp]) ?? CAMPS[0];
  const [camp, setCamp] = useState<Camp>(firstCamp);
  const [day, setDay] = useState<string | null>(null);

  // dni z obu stron (najnowsze najpierw, maks. 7), żeby pasek nie zmieniał się przy przełączaniu strony
  const days = useMemo(() => {
    const all = new Set<string>();
    CAMPS.forEach(side => {
      if (data.messages[side]?.day) all.add(data.messages[side]!.day);
      (data.message_history?.[side] ?? []).forEach(message => all.add(message.day));
    });
    return [...all].sort((a, b) => b.localeCompare(a)).slice(0, 7);
  }, [data]);
  const activeDay = day ?? days[0] ?? null;

  const findMessage = (side: Camp, onDay: string | null): DailyMessage | null => {
    if (!onDay) return null;
    const current = data.messages[side];
    if (current?.day === onDay) return current;
    return (data.message_history?.[side] ?? []).find(message => message.day === onDay) ?? null;
  };
  const base = findMessage(camp, activeDay);
  // historia z /api/clinic/ nie ma wpisów źródłowych - dociągamy je tylko dla wybranego starszego dnia
  const needsPosts = Boolean(base && !base.posts?.length && activeDay);
  const detail = useQuery({ queryKey: ["clinic-message", activeDay], queryFn: () => getClinicMessage(activeDay!), enabled: needsPosts, staleTime: 5 * 60_000 });
  const message: DailyMessage | null = (needsPosts ? detail.data?.[camp] : null) ?? base;

  const quotes = message ? pickQuotes(message) : [];
  const stats = message?.stats?.version === 1 ? message.stats : null;
  const posts = stats?.posts ?? message?.posts_count ?? 0;
  const structured = Boolean(message?.thesis?.trim());
  const points = message?.points ?? [];
  // seria 2 (API-v3): łańcuch tylko zatwierdzony i poprawny (plus flaga NEXT_PUBLIC_CAUSAL_CHAIN w komponencie); siła dnia tylko przy n >= 3
  const chainSteps = approvedChainSteps(message?.causal_chain);
  const hasChain = CAUSAL_CHAIN_ON && chainSteps !== null;
  const strength = messageSpinStrength(message);
  const windowLabel = message?.scope?.date_from && message.scope.date_to ? `${formatTimePl(message.scope.date_from)}-${formatTimePl(message.scope.date_to)}` : null;

  return <div className="sc-v3-pdwrap">
    <section className="sc-v3-pd" data-side={camp} aria-labelledby="sc-v3-pd-title">
      <header className="sc-v3-pd__h">
        <h2 id="sc-v3-pd-title" className="sc-v3-pd__k sc-v3-sans">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12a7 7 0 0 1 14 0M8.5 12a3.5 3.5 0 0 1 7 0" /><circle cx="12" cy="12" r="1" /><path d="M3 12a9 9 0 0 1 1-4M21 12a9 9 0 0 0-1-4" /></svg>
          Przekaz dnia{activeDay && <time dateTime={activeDay}>{formatDatePl(activeDay)}</time>}
        </h2>
        <div className="sc-v3-seg" role="group" aria-label="Strona sceny politycznej">
          {CAMPS.map(side => <button key={side} type="button" data-side={side} aria-pressed={camp === side} onClick={() => setCamp(side)}>{CAMP_LABELS[side]}</button>)}
        </div>
        <span className="sc-v3-tag" data-tone="accent" title="Wygenerowane z udziałem AI">AI</span>
        
      </header>

      {message ? <div className="sc-v3-pd__b sc-v3-pd__body" aria-live="polite">
        <div className="sc-v3-pd__l">
          <div className="sc-v3-pd__ebrow">
            <p className="sc-v3-pd__eb">Dziś w obiegu · <span className="sc-v3-sidew">{CAMP_LABELS[camp]}</span></p>
            {strength ? <SpinMeter value={strength.value} bare label="Siła spinu dnia" title={`Siła spinu dnia: ${strength.value}/100 - mediana z ${strength.n}${NBSP}diagnoz wpisów tego przekazu`} /> : null}
          </div>
          <p className="sc-v3-pd__thesis">{structured ? message.thesis : message.message}</p>
          <ul className="sc-v3-pd__stats" aria-label="Zakres przekazu">
            <li><b>{posts}</b>{plural(posts, "wpis", "wpisy", "wpisów")}</li>
            <li><b>{stats ? stats.authors : "–"}</b>{stats ? plural(stats.authors, "autor", "autorów", "autorów") : "autorów"}</li>
            <li title="Odsetek wpisów z liczbą lub linkiem. Nie oznacza potwierdzenia ich prawdziwości."><b>{stats ? `${stats.concrete_pct}%` : "–"}</b>z liczbą lub linkiem</li>
            {windowLabel ? <li><b>{windowLabel}</b>okno wpisów, X</li> : <li><b>X</b>platforma</li>}
          </ul>
          {quotes.length ? <>
            <ul className="sc-v3-pd__q" aria-label="Przykładowe wpisy">
              {quotes.map(post => <li key={post.url}>
                <span className="sc-v3-av" aria-hidden="true">{initials(post.author)}</span>
                <div style={{ minWidth: 0 }}>
                  <p className="sc-v3-who"><span className="sc-v3-who__n">{post.author}</span><span className="sc-v3-who__d"><span className="sc-v3-who__sep"> · </span>{formatDateTimePl(post.published_at)}</span></p>
                  <q>{quoteText(post.text)}</q>
                </div>
                <a className="sc-v3-src" href={post.url} target="_blank" rel="noopener noreferrer" aria-label={`Oryginał wpisu: ${post.author}, otwiera X w nowym oknie`}><ArrowUpRightIcon /></a>
              </li>)}
            </ul>
            <p className="sc-v3-pd__qnote">Fragmenty wpisów z X w brzmieniu oryginalnym. Treść mogła zostać zmieniona lub usunięta po pobraniu.</p>
          </> : detail.isFetching ? <p className="sc-v3-pd__qnote" role="status">Wczytujemy wpisy źródłowe…</p> : null}
        </div>

        <div className="sc-v3-pd__r">
          {hasChain ? <>
            <p className="sc-v3-pd__eb">Dr Spin wyjaśnia</p>
            <CausalChain steps={chainSteps} />
            {message.causal_chain?.notice ? <p className="sc-v3-step__meta sc-v3-pd__chainnote">{message.causal_chain.notice}</p> : null}
          </> : points.length ? <>
            <p className="sc-v3-pd__eb">Główne wątki dnia</p>
            <ol className="sc-v3-steps" aria-label="Główne wątki dnia">
              {points.map((point, index) => <li key={index} style={{ "--d": index } as CSSProperties}>
                <span className="sc-v3-step__n" aria-hidden="true">{index + 1}</span>
                <p className="sc-v3-step__t">{point.title}</p>
                <p className="sc-v3-step__p">{point.summary}</p>
                <p className="sc-v3-step__meta">{point.post_ids.length}{NBSP}{plural(point.post_ids.length, "wpis", "wpisy", "wpisów")} · {authorsShort(point.authors)}</p>
              </li>)}
            </ol>
          </> : <>
            <p className="sc-v3-pd__eb">Przekaz</p>
            <p className="sc-v3-step__p" style={{ marginTop: 12 }}>{message.message}</p>
          </>}
          {message.themes?.length ? <p className="sc-v3-step__meta sc-v3-pd__rf">Tematy: {message.themes.map(capital).join(", ")}</p> : null}
        </div>
      </div> : <p className="sc-v3-pd__empty">Brak opublikowanego przekazu tej strony w tym dniu. Przekaz pojawia się, gdy strona opublikuje co najmniej kilka wpisów.</p>}

      <footer className="sc-v3-pd__f">
        <p className="sc-v3-pd__ai"><b>Wygenerowane z udziałem AI</b>{message?.model ? ` · model ${message.model}` : ""}{message?.reviewed_at ? ` · zatwierdzono ${formatDateTimePl(message.reviewed_at)}` : ""}. Wątki, ton i spójność to przypisania AI, nie ustalenie faktów.</p>
        <div className="sc-v3-pd__act">
          <BugReportButton className="sc-v3-qbtn" label="Zgłoś błąd lub sprostowanie" />
          {message && activeDay ? <Button variant="primary" href={`/klinika/przekazy/${activeDay}#message-${activeDay}-${camp}`} iconEnd={<span className="sc-v3-ar" aria-hidden="true">→</span>}>Zobacz pełną analizę</Button>
            : <Button variant="primary" href="/klinika/przekazy">Archiwum przekazów</Button>}
        </div>
      </footer>
    </section>

    {days.length > 1 && <div className="sc-v3-days" role="group" aria-label="Przekaz z poprzednich dni">
      {days.map((d, index) => {
        const m = findMessage(camp, d);
        return <button key={d} type="button" aria-pressed={d === activeDay} onClick={() => setDay(d)}>
          <span className="sc-v3-dd">{index === 0 ? "Najnowszy" : shortDate(d)}</span>
          <span className="sc-v3-dt">{m?.themes?.[0] ? capital(m.themes[0]) : "brak przekazu"}</span>
        </button>;
      })}
    </div>}
  </div>;
}
