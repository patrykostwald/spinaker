"use client";

import { ClinicOverview } from "./ClinicOverview";
import { useLongPress } from "../../lib/useLongPress";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Strip } from "../../kit/home/Strip";
import { CAMPS, CAMP_LABELS, getClinicDeleted, type SpinDetailData } from "../../lib/clinic";
import { IntensityMeter, SpinAuthorRow, VerdictTag } from "./SpinParts";
import { ShareSpinOnX } from "./ShareSpinOnX";
import { formatDateTimePl } from "../../lib/utils";

export { MessageBox } from "./ClinicExtras";


/** Spin dnia jako nitka: box główny (post + diagnoza), a za nim boxy kontekstu - źródła twierdzeń. */
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
            {/* Zdjęcia z wpisu - część przekazu (np. twarz, grafika z hasłem); klik otwiera wpis na X. */}
            {spin.post.media?.length ? (
              <a className="sc-clinic-sotd__media" data-count={Math.min(spin.post.media.length, 2)} href={spin.post.url} target="_blank" rel="noopener noreferrer"
                aria-label="Zdjęcia z wpisu - otwórz na X">
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
          <div className="sc-clinic-sotd__reading" data-expanded={expanded || undefined} tabIndex={0} aria-label="Diagnoza Dr. Spina - przewijaj">
            <p>{spin.summary}</p>
            {spin.analysis && spin.analysis.split(/\n{2,}/).map((part, index) => <p key={index}>{part}</p>)}
            {spin.techniques.length > 0 && <>
              <h4>Techniki</h4>
              <ul className="sc-clinic-sotd__list">{spin.techniques.map(item => (
                <li key={item.name + item.quote}><strong>{item.name}</strong> - „{item.quote}”. {item.explanation}</li>
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
              // Po zwinięciu wracamy do początku diagnozy - czytelnik nie zostaje na dole strony.
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

/** Strażnica niedostępnych wpisów: kto i kiedy usunął wpis, czy Dr. Spin ocenił go jako spin - bez treści (zasady X). */
function DeletedPosts() {
  const query = useQuery({ queryKey: ["clinic-deleted"], queryFn: getClinicDeleted, staleTime: 10 * 60_000 });
  const data = query.data;
  if (!data) return null;
  const week = CAMPS.map(camp => `${CAMP_LABELS[camp].toLowerCase()} ${data.week_by_camp[camp] ?? 0}`).join(" · ");
  return (
    <details className="sc-deleted sc-deleted--compact">
      <summary>Niedostępne wpisy <span>· ostatnie 7 dni: {Object.values(data.week_by_camp).reduce((sum, value) => sum + value, 0)}</span></summary>
      <header className="sc-deleted__head">
        <p>
          Wpisy niedostępne podczas sprawdzania. Nie przesądzamy, czy autor je usunął - przyczyną może być także ograniczenie dostępu. Nie pokazujemy ich treści,
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
            {/* archiwum przed datami, bez kolumny „bez diagnozy” (właściciel 4.10) */}
            <span className="sc-deleted__archive">{item.archive_url
              ? <a href={item.archive_url} target="_blank" rel="noopener noreferrer">kopia w archiwum ↗</a>
              : <a className="sc-deleted__search" href={item.archive_search_url} target="_blank" rel="noopener noreferrer">szukaj w archive.today ↗</a>}</span>
            <span className="sc-deleted__when">opublikowany {formatDateTimePl(item.published_at)}<br />zniknął {visibleFor(item.hours_visible)} od publikacji</span>
            {item.verdict ? <span><VerdictTag verdict={item.verdict} label={item.verdict_label} /></span> : null}
          </li>
        ))}</ul>
      ) : <p className="sc-clinic-empty">W ostatnich {data.days} dniach nie zauważyliśmy niedostępnych wpisów. Sprawdzamy co 3 godziny wpisy z ostatnich dwóch tygodni.</p>}
    </details>
  );
}

/** Przegląd: krótkie podglądy i wejścia do pełnych archiwów. */
export function ClinicPage({ embedded = false }: { embedded?: boolean }) {
  return <ClinicOverview home={embedded} extra={<DeletedPosts />} />;
}
