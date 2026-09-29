"use client";

import { ClinicNav } from "./ClinicNav";
import { useLongPress } from "../../lib/useLongPress";
import { SectionHeader } from "../../kit/SectionHeader";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "../../kit";
import { Strip } from "../../kit/home/Strip";
import { CAMPS, CAMP_LABELS, getClinicAccounts, getClinicDeleted, getClinicPage, type ClinicPageData, type SpinDetailData } from "../../lib/clinic";
import { NewsletterSignup } from "../NewsletterSignup";
import { AiTag, IntensityMeter, SpinAuthorRow, SpinRow, SpinScale, VerdictTag } from "./SpinParts";
import { ShareSpinOnX } from "./ShareSpinOnX";
import { ClinicShowcase } from "./ClinicIndicators";
import { HomeSpinScanner } from "../../kit/home/HomeSpinScanner";
import { formatDateTimePl } from "../../lib/utils";
import { InterviewScanner } from "./InterviewScanner";
import { InterviewArchive, MessageBox, MessageHistory, PoliticiansTable, SpinSwitch } from "./ClinicExtras";

export { MessageBox } from "./ClinicExtras";

const CONTACT = "kontakt@spin.clinic";

/** Spin dnia jako nitka: box główny (post + diagnoza), a za nim boxy kontekstu — źródła twierdzeń. */
export function SpinOfDay({ spin }: { spin: SpinDetailData }) {
  // Pełna odpowiedź Dr. Spina obok wpisu: tej samej wysokości co post, przewijana po najechaniu; „Rozwiń” pokazuje całość.
  const [expanded, setExpanded] = useState(false);
  // Telefon: wpis przycięty do kilku linii (CSS), żeby licznik i wywiad nie zjeżdżały daleko w dół.
  const [postOpen, setPostOpen] = useState(false);
  const pressPost = useLongPress(() => setPostOpen(true));
  const sources = spin.claims.flatMap(claim => claim.sources.map(source => ({ ...source, label: claim.assessment_label, claim: claim.claim })));
  return (
    <div className="sc-clinic-sotd__body">
      <div className="sc-clinic-sotd__main">
        <div className="sc-clinic-sotd__post">
          <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} size="lg" caption={spin.camp_label} />
          <div className="sc-clinic-sotd__quote" data-open={postOpen || undefined} {...(postOpen ? {} : pressPost)}>
            <blockquote>{spin.post.text}</blockquote>
            {postOpen ? null : <button type="button" className="sc-clinic-sotd__more-post" onClick={() => setPostOpen(true)}>Rozwiń wpis ↓</button>}
            {/* Zdjęcia z wpisu — część przekazu (np. twarz, grafika z hasłem); klik otwiera wpis na X. */}
            {spin.post.media?.length ? (
              <a className="sc-clinic-sotd__media" data-count={Math.min(spin.post.media.length, 2)} href={spin.post.url} target="_blank" rel="noopener noreferrer"
                aria-label="Zdjęcia z wpisu — otwórz na X">
                {spin.post.media.slice(0, 2).map(item => (
                  // eslint-disable-next-line @next/next/no-img-element -- miniatury z X
                  <img key={item.url} src={item.url} alt={item.alt || "Zdjęcie dołączone do wpisu"} loading="lazy" referrerPolicy="no-referrer" />
                ))}
              </a>
            ) : null}
          </div>
          <a href={spin.post.url} target="_blank" rel="noopener noreferrer">Wpis na X ↗</a>
        </div>
        <div className="sc-clinic-sotd__diagnosis">
          <p className="sc-spin-card__verdict"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><IntensityMeter value={spin.intensity} /></p>
          <h3 id="sotd-title"><Link href={`/klinika/${spin.id}`}>{spin.headline}</Link></h3>
          <div className="sc-clinic-sotd__reading" data-expanded={expanded || undefined} tabIndex={0} aria-label="Diagnoza Dr. Spina — przewijaj">
            <p>{spin.summary}</p>
            {spin.analysis && spin.analysis.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>)}
            {spin.techniques.length > 0 && <>
              <h4>Techniki</h4>
              <ul className="sc-clinic-sotd__list">{spin.techniques.map(item => (
                <li key={item.name + item.quote}><strong>{item.name}</strong> — „{item.quote}”. {item.explanation}</li>
              ))}</ul>
            </>}
            {spin.claims.length > 0 && <>
              <h4>Twierdzenia</h4>
              <ul className="sc-clinic-sotd__list">{spin.claims.map(item => (
                <li key={item.claim}><span className="sc-verdict">{item.assessment_label}</span> <strong>{item.claim}</strong> {item.explanation}</li>
              ))}</ul>
            </>}
            {spin.limitations && <p className="sc-clinic-sotd__limits">Ograniczenia: {spin.limitations}</p>}
          </div>
          <p className="sc-clinic-sotd__actions">
            <button type="button" className="sc-clinic-sotd__toggle" aria-expanded={expanded} onClick={event => {
              // Po zwinięciu wracamy do początku diagnozy — czytelnik nie zostaje na dole strony.
              const box = event.currentTarget.closest(".sc-clinic-sotd__diagnosis");
              setExpanded(value => !value);
              if (expanded && box) requestAnimationFrame(() => { if (box.getBoundingClientRect().top < 0) box.scrollIntoView({ block: "start", behavior: "smooth" }); });
            }}>{expanded ? "Zwiń diagnozę ↑" : "Rozwiń diagnozę ↓"}</button>
            <span className="sc-clinic-sotd__share"><ShareSpinOnX id={spin.id} spin={spin} /></span>
            <Link className="sc-clinic-sotd__full" href={`/klinika/${spin.id}`}>Pełna diagnoza →</Link></p>
        </div>
      </div>
      {sources.length > 0 && (
        <Strip label="Źródła diagnozy" slot="260px">
          {sources.map(source => (
            <div key={source.url} className="sc-strip__slot">
              <a className="sc-clinic-source" href={source.url} target="_blank" rel="noopener noreferrer">
                <span className="sc-verdict">{source.label}</span>
                <strong>{source.title || source.url}</strong>
                <span>{new URL(source.url).hostname.replace(/^www\./, "")} ↗</span>
              </a>
            </div>
          ))}
        </Strip>
      )}
    </div>
  );
}

function visibleFor(hours: number) {
  if (hours < 1) return "w ciągu godziny";
  if (hours < 48) return `w ciągu ${Math.ceil(hours)} godz.`;
  return `w ciągu ${Math.ceil(hours / 24)} dni`;
}

/** Strażnica niedostępnych wpisów: kto i kiedy usunął wpis, czy Dr. Spin ocenił go jako spin — bez treści (zasady X). */
function DeletedPosts() {
  const query = useQuery({ queryKey: ["clinic-deleted"], queryFn: getClinicDeleted, staleTime: 10 * 60_000 });
  const data = query.data;
  if (!data) return null;
  const week = CAMPS.map(camp => `${CAMP_LABELS[camp].toLowerCase()} ${data.week_by_camp[camp] ?? 0}`).join(" · ");
  return (
    <section className="sc-deleted" aria-labelledby="deleted-title">
      <header className="sc-deleted__head">
        <p className="sc-clinic-kicker">Strażnica</p>
        <h2 id="deleted-title">Niedostępne wpisy</h2>
        <p>
          Wpisy niedostępne podczas sprawdzania. Nie przesądzamy, czy autor je usunął — przyczyną może być także ograniczenie dostępu. Nie pokazujemy ich treści,
          ale jeśli ktoś zachował go w publicznym archiwum internetu, linkujemy do tej kopii. Ostatnie 7 dni: {week}.
        </p>
        {data.top_deleters.length ? (
          <p className="sc-deleted__top">Konta z największą liczbą niedostępnych wpisów (30 dni): {data.top_deleters.map((row, index) => (
            <span key={row.author.handle}>{index ? " · " : ""}<a href={row.author.account_url} target="_blank" rel="noopener noreferrer">{row.author.name}</a> {row.count}</span>
          ))}</p>
        ) : null}
      </header>
      {data.items.length ? (
        <ul className="sc-deleted__list">{data.items.map(item => (
          <li key={`${item.author.handle}-${item.published_at}`}>
            <span className="sc-deleted__who"><a href={item.author.account_url} target="_blank" rel="noopener noreferrer">{item.author.name}</a>
              <small>@{item.author.handle}{item.author.party ? ` · ${item.author.party.short}` : ""} · {item.camp_label}</small></span>
            <span className="sc-deleted__when">opublikowany {formatDateTimePl(item.published_at)}<br />zniknął {visibleFor(item.hours_visible)} od publikacji</span>
            <span className="sc-deleted__archive">{item.archive_url
              ? <a href={item.archive_url} target="_blank" rel="noopener noreferrer">kopia w archiwum ↗</a>
              : <a className="sc-deleted__search" href={item.archive_search_url} target="_blank" rel="noopener noreferrer">szukaj w archive.today ↗</a>}</span>
            <span>{item.verdict ? <VerdictTag verdict={item.verdict} label={item.verdict_label} /> : <span className="sc-deleted__none">bez diagnozy</span>}</span>
          </li>
        ))}</ul>
      ) : <p className="sc-clinic-empty">W ostatnich {data.days} dniach nie zauważyliśmy niedostępnych wpisów. Sprawdzamy co 3 godziny wpisy z ostatnich dwóch tygodni.</p>}
    </section>
  );
}

function Politicians() {
  const query = useQuery({ queryKey: ["clinic-accounts"], queryFn: getClinicAccounts, staleTime: 10 * 60_000 });
  return query.data ? <PoliticiansTable accounts={query.data.results} /> : null;
}

/**
 * Klinika spinu — kolejność: spin dnia / najnowszy spin, przekazy dnia, wywiad dnia, waga spinu,
 * najnowsze diagnozy w dwóch kolumnach, politycy z licznikami, archiwum przekazów, zaproszenie dla dziennikarzy.
 */
export function ClinicPage({ embedded = false }: { embedded?: boolean }) {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, refetchInterval: 5 * 60_000 });
  const data = query.data;
  return (
    <section className="sc-clinic" id="spin" aria-labelledby="clinic-title" data-embedded={embedded || undefined}>
      {!embedded ? <ClinicNav /> : null}
      <SectionHeader variant={embedded ? "section" : "page"} titleId="clinic-title" kicker="Klinika spinu" title="Dr. Spin"
        subtitle={<><AiTag /> Analizujemy wybrane wpisy i wywiady polityków. Pokazujemy techniki perswazji, oceny modeli AI i źródła dotyczące sprawdzanych twierdzeń.</>}
        link={<Link href="/metodologia">Jak działa analiza</Link>} />

      {query.isError && <p role="alert" className="sc-clinic-empty">Nie udało się pobrać Kliniki. <Button size="sm" variant="quiet" onClick={() => query.refetch()}>Ponów</Button></p>}
      {query.isLoading && <p className="sc-clinic-empty">Ładowanie diagnoz…</p>}

      {data && <>
        <ClinicShowcase fallback={data.stats} fallbackPeriod={data} fetchedAt={query.dataUpdatedAt} />

        <section className="sc-clinic-sotd" aria-labelledby="clinic-drspin-title">
          {/* Nagłówek jak na głównej: „Klinika spinu AI” + „Dr. Spin”, zakładki na środku, link po prawej. */}
          <SpinSwitch spinOfDay={data.spin_of_day} latest={data.latest_spin} render={spin => <HomeSpinScanner key={spin.id} spin={spin} />}
            left={<header>
              <p className="sc-t-caption sc-text-3 sc-home-kicker">Klinika spinu <AiTag /></p>
              <h2 id="clinic-drspin-title">Wybrana diagnoza</h2>
            </header>}
            right={<p className="sc-home-spin__meta"><Link className="sc-home-spin__open" href="/raport">Raport tygodnia →</Link></p>}
            empty={<p className="sc-clinic-empty" id="sotd-title">Spin dnia to diagnoza z najwyższą siłą spinu z dzisiaj. Pojawi się po pierwszych diagnozach.</p>} />
        </section>

        {/* Panel tematyczny: dzisiejsze przekazy obu stron i ich archiwum. */}
        <div className="sc-clinic-group">
          <div className="sc-clinic-split" aria-label="Przekazy dnia">
            {CAMPS.map(camp => <MessageBox key={camp} camp={camp} message={data.messages[camp]} surface="nested" />)}
          </div>
          <MessageHistory history={data.message_history} />
          <p><Link href="/klinika/przekazy">Archiwum przekazów →</Link></p>
        </div>

        {data.interview ? <InterviewScanner interview={data.interview} /> : null}
        {data.interview_second ? <InterviewScanner interview={data.interview_second} /> : null}
        {data.interview_archive?.length ? <InterviewArchive items={data.interview_archive} /> : null}

        {/* Panel tematyczny: waga spinu i najnowsze diagnozy obu stron. */}
        <div className="sc-clinic-group">

        <section className="sc-clinic-latest" aria-labelledby="clinic-latest-title">
          <SectionHeader titleId="clinic-latest-title" title="Najnowsze diagnozy" subtitle="Rządzący i opozycja — według tych samych zasad. Liczby opublikowanych diagnoz mogą się różnić." />
          <div className="sc-clinic-columns">
            {CAMPS.filter(camp => data.columns[camp].length > 0).map(camp => (
              <section key={camp} className="sc-clinic-column" aria-labelledby={`clinic-col-${camp}`}>
                <h3 id={`clinic-col-${camp}`}>{CAMP_LABELS[camp]}</h3>
                <div className="sc-clinic-column__list">
                  {[...data.columns[camp]].sort((a, b) => b.id - a.id).slice(0, 3).map(spin => <SpinRow key={spin.id} spin={spin} />)}
                </div>
                <Button href={`/klinika/diagnozy?camp=${camp}`} variant="quiet">Wszystkie diagnozy {camp === "government" ? "rządzących" : "opozycji"} →</Button>
              </section>
            ))}
          </div>
          {!CAMPS.some(camp => data.columns[camp].length) ? <p className="sc-clinic-empty">Nie ma jeszcze opublikowanych diagnoz.</p> : null}
          <Link className="sc-clinic-db__all" href="/klinika/diagnozy">Wszystkie diagnozy{data.stats?.diagnosed.total !== undefined ? ` (${data.stats.diagnosed.total.toLocaleString("pl-PL")})` : ""} →</Link>
        </section>
        </div>

        <DeletedPosts />
        <Politicians />

        <NewsletterSignup source="klinika" />
      </>}
    </section>
  );
}
