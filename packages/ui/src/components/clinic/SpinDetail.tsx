"use client";

import { SpinSummary, ReportError } from "./SpinSummary";
import { ClinicNav } from "./ClinicNav";
import { SourceDisclosure } from "./SourceDisclosure";
import Link from "next/link";
import { ApiError } from "../../lib/api";
import { useQuery } from "@tanstack/react-query";
import { agreementLabel, getSpin, spinVar, type SpinDetailData } from "../../lib/clinic";
import { formatDateTimePl } from "../../lib/utils";
import { ClinicDiscussion } from "./ClinicDiscussion";
import { AiTag, FitStickyAside, HowToRead, SpinAuthorRow } from "./SpinParts";
import { ShareSpinOnX } from "./ShareSpinOnX";
import { clinicResultsUrl } from "../../lib/clinicNavigation";
import { setSpinMood } from "../../lib/mood";
import { ContextThreadStrip } from '../ContextThreadStrip';
import { useEffect, useRef, useState } from "react";
import { rememberClinicVisit } from "../../lib/clinicHistory";
import { AuthorReplies, WithdrawnSpin } from "./ClinicCorrections";

// Jedno ustawienie pierwszego ekranu: "word" pokazuje samą ocenę słowną.
export const SCORE_STYLE: "number" | "word" = "number";

function hasPlain(plain: SpinDetailData["plain"]): plain is NonNullable<SpinDetailData["plain"]> {
  return !!plain && typeof plain.title === "string" && !!plain.title.trim()
    && typeof plain.gist === "string" && !!plain.gist.trim() && Array.isArray(plain.top)
    && plain.top.length === 2 && plain.top.every(t => t && typeof t.name === "string"
      && !!t.name.trim() && typeof t.quote === "string" && !!t.quote.trim());
}

export function PlainDiagnosis({ spin }: { spin: SpinDetailData }) {
  const plain = spin.plain;
  if (!hasPlain(plain)) return null;
  const score = Math.max(0, Math.min(100, spin.intensity));
  const level = score >= 70 ? "wysoki" : score >= 30 ? "średni" : "niski";
  return <section className="sc-plain" aria-label="Diagnoza w skrócie">
    <p className="sc-clinic-kicker">Siła spinu</p>
    <p className="sc-plain__score" data-level={level}>
      {SCORE_STYLE === "number" && <span className="sc-spin-num" style={spinVar(score)}>{score}<small>/100</small></span>}
      <strong>{level}</strong>
    </p>
    <div className="sc-plain__bar" data-level={level} aria-hidden="true"><i className="sc-spin-fill" style={{ ...spinVar(score), width: `${score}%` }} /></div>
    <h1>{plain.title}</h1>
    <p className="sc-plain__gist">{plain.gist}</p>
    <ul className="sc-plain__techniques">{plain.top.map((technique, index) => <li key={index}>
      <h2>{technique.name}</h2><blockquote>„{technique.quote}”</blockquote>
    </li>)}</ul>
  </section>;
}

export function SpinDiagnosisBody({ spin, withSummary = true }: { spin: SpinDetailData; withSummary?: boolean }) {
  return <>
    {withSummary ? <><SpinSummary spin={spin} heading="h2" compact withPoint={false} /><p className="sc-spin-detail__summary">{spin.summary}</p></> : null}
    <h2>Uzasadnienie</h2>
    <div className="sc-spin-detail__analysis">{spin.analysis.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>

    <section className="sc-spin-detail__section" id={`spin-${spin.id}-techniki`}>
      <h2>Techniki perswazji</h2>
      <p className="sc-spin-detail__intro">Jak zbudowano przekaz: techniki, cytaty i wyjaśnienia.</p>
      {!spin.techniques.length ? <p>Nie wskazano technik w tej analizie.</p> : null}
      <ol className="sc-spin-detail__techniques">{spin.techniques.map((item, index) => (
        <li key={index}><strong>{item.name}</strong><blockquote>„{item.quote}”</blockquote><p>{item.explanation}</p></li>
      ))}</ol>
    </section>

    <section className="sc-spin-detail__section" id={`spin-${spin.id}-twierdzenia`}>
      <h2>Twierdzenia i źródła</h2>
      <p className="sc-spin-detail__intro">Co można sprawdzić i jakie źródła wykorzystano w analizie.</p>
      {!spin.claims.length ? <p>Brak osobno sprawdzonych twierdzeń.</p> : null}
      {/* Akordeony: czytelnik sam rozwija fakt, który chce zgłębić (uwagi recenzenta UX, 30.09) */}
      <ul className="sc-spin-detail__claims">{spin.claims.map((claim, index) => (
        <li key={index} data-assessment={claim.assessment}>
          <details className="sc-spin-detail__claim-item">
            <summary><span className="sc-verdict" data-assessment={claim.assessment}>{claim.assessment_label}</span><span className="sc-spin-detail__claim">{claim.claim}</span>{claim.sources.length ? <span className="sc-spin-detail__claim-count">{claim.sources.length} {claim.sources.length === 1 ? "źródło" : claim.sources.length < 5 ? "źródła" : "źródeł"}</span> : null}</summary>
            <div className="sc-spin-detail__claim-body">
              {claim.explanation && <p>{claim.explanation}</p>}
              {claim.sources.length > 0 && <ul className="sc-spin-detail__sources">{claim.sources.map(source => (
                <li key={source.url}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title || "Źródło"} · {sourceDomain(source.url)} ↗</a></li>
              ))}</ul>}
            </div>
          </details>
        </li>
      ))}</ul>
    </section>

    <section className="sc-spin-detail__section" id={`spin-${spin.id}-modele`}><h2>Modele</h2>
      {spin.council ? <details className="sc-spin-detail__models"><summary>Pokaż oceny modeli</summary><CouncilNote council={spin.council} /></details> : <p>Model: {spin.model || "brak danych o modelu"}. Szczegółowe głosy nie są dostępne.</p>}
    </section>
    <section className="sc-spin-detail__section" id={`spin-${spin.id}-ograniczenia`}><h2>Ograniczenia analizy</h2><p className="sc-spin-detail__limits">{spin.limitations || "Nie zapisano dodatkowych ograniczeń tej analizy."}</p></section>
    <p className="sc-spin-detail__meta"><AiTag /> Model {spin.model} · instrukcja {spin.prompt_version} · diagnoza {formatDateTimePl(spin.created_at)}{spin.auto_published ? " · opublikowana automatycznie" : spin.reviewed_at ? ` · zatwierdzona bez zmian ${formatDateTimePl(spin.reviewed_at)}` : ""}</p>
    <p>Zasady publikacji i korekt: <Link href="/konsylium/karta">Karta Konsylium</Link>.</p>
    <p><ReportError spin={spin} /></p>
    <p className="sc-spin-detail__share"><ShareSpinOnX id={spin.id} spin={spin} /></p>
    <ContextThreadStrip url={spin.post.url} />
  </>;
}

export function SpinDetail({ id, returnTo }: { id: string; returnTo?: string }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const query = useQuery({ queryKey: ["clinic-spin", id], queryFn: () => getSpin(id), staleTime: 0, refetchOnMount: "always" });
  const recorded = useRef<number | null>(null);
  useEffect(() => {
    const spin = query.data;
    if (!spin || spin.status === "withdrawn" || recorded.current === spin.id) return;
    recorded.current = spin.id;
    rememberClinicVisit({ type: "diagnosis", id: spin.id, title: spin.headline, camp: spin.camp,
      verdict: spin.verdict, intensity: spin.intensity, author: spin.author.name });
  }, [query.data]);
  // tło przyjmuje siłę spinu tej diagnozy (właściciel 3.10)
  const moodIntensity = query.data && 'intensity' in query.data ? query.data.intensity : null;
  useEffect(() => { setSpinMood(moodIntensity); return () => setSpinMood(null); }, [moodIntensity]);
  if (query.isFetching || query.isLoading) return <div className="sc-clinic"><p className="sc-clinic-empty">Wczytujemy diagnozę…</p></div>;
  if (query.isError && !(query.error instanceof ApiError && query.error.status === 404)) return <div className="sc-clinic" role="alert"><p>Nie udało się pobrać danych.</p><button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></div>;
  if (query.isError || !query.data) return <div className="sc-clinic"><p className="sc-clinic-empty">Nie znaleziono diagnozy. <Link href="/klinika">Wróć do Kliniki</Link></p></div>;
  const spin = query.data;
  if (spin.status === "withdrawn") return <WithdrawnSpin spin={spin} />;
  const simple = hasPlain(spin.plain);
  const expanded = expandedId === id;
  return (
    <div className="sc-clinic sc-spin-detail">
      <ClinicNav />
      <Link className="sc-spin-detail__back" href={clinicResultsUrl(returnTo ?? null)} scroll={false}>← Wróć do wyników</Link>
      <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} />
      {simple && <>
        <PlainDiagnosis spin={spin} />
        <button type="button" className="sc-plain__toggle" aria-expanded={expanded}
          aria-controls={`spin-${spin.id}-details`} onClick={() => setExpandedId(expanded ? null : id)}>
          {expanded ? "Ukryj szczegóły" : "Pokaż szczegóły"}
        </button>
      </>}
      <div id={`spin-${spin.id}-details`} hidden={simple && !expanded}>
      {/* Lewa kolumna: źródło i szybkie podsumowanie; prawa: ocena i pełna analiza (uwagi recenzenta UX, 30.09).
          Na telefonie kolejność: wpis → ocena → podsumowanie → analiza. */}
      <div className="sc-dg-layout">
        <FitStickyAside className="sc-dg-side">
        <SourceDisclosure className="sc-spin-detail__post">
          <p className="sc-clinic-kicker">{spin.camp_label}</p>
          <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} size="lg" />
          {spin.author.role_title && <p className="sc-spin-detail__role">{spin.author.role_title}</p>}
          <p className="sc-spin-card__text sc-spin-card__text--full">{spin.post.text}</p>
          {spin.post.media.filter(item => item.url).slice(0, 2).map(item => (
            // eslint-disable-next-line @next/next/no-img-element -- miniatura z oficjalnego API X
            <figure key={item.url}><img className="sc-spin-card__media" src={item.url} alt={item.alt || "Załącznik do wpisu"} loading="lazy" referrerPolicy="no-referrer" /><figcaption><a href={item.url} target="_blank" rel="noopener noreferrer">Pokaż cały załącznik ↗</a></figcaption></figure>
          ))}
          <a className="sc-spin-card__source" href={spin.post.url} target="_blank" rel="noopener noreferrer">Oryginalny wpis na X ↗</a>
        </SourceDisclosure>
        <section className="sc-dg-quick" aria-label="Podsumowanie"><h2>W skrócie</h2><p className="sc-spin-detail__summary">{spin.summary}</p></section>
        </FitStickyAside>
        <div className="sc-dg-main">
        <div className="sc-dg-score"><SpinSummary spin={spin} heading="h1" withPoint={false} withReport withTable={false} /><HowToRead /></div>
        <nav className="sc-spin-detail__anchors" aria-label="W tej diagnozie">{[["techniki", "Techniki"], ["twierdzenia", "Twierdzenia i źródła"], ["modele", "Modele"], ["ograniczenia", "Ograniczenia"]].map(([anchor, label]) => <a key={anchor} href={`#spin-${spin.id}-${anchor}`}>{label}</a>)}</nav>
        <article className="sc-spin-detail__diagnosis">
          <SpinDiagnosisBody spin={spin} withSummary={false} />
          <p className="sc-clinic-roadmap">{spin.notice}</p>
        </article>
        </div>
      </div>
      <AuthorReplies replies={spin.author_replies} />
      <ClinicDiscussion kind="spins" id={spin.id} />
      </div>
    </div>
  );
}


const VERDICT_SHORT: Record<string, string> = { spin: "spin", partial: "częściowy spin", no_spin: "bez spinu", unclear: "nie da się ocenić" };
const short = (model: string) => model.split("/").pop() ?? model;

/** Konsylium Dr. Spina: kto oceniał, jak zagłosował, lekarz prowadzący, redaktor i ordynator. */
function CouncilNote({ council }: { council: NonNullable<SpinDetailData["council"]> }) {
  return (
    <section className="sc-council sc-spin-detail__section" aria-label="Konsylium Dr. Spina">
      <h2>Oceny modeli</h2>
      <p className="sc-council__title">Konsylium Dr. Spina · {agreementLabel(council.agreement)}{council.escalated ? " · konsultacja specjalisty: fakty sprawdził dodatkowo mocniejszy model z wyszukiwaniem" : ""}</p>
      <ul>{council.members.map(member => (
        <li key={member.model}><strong>{short(member.model)}</strong> - {member.intensity == null || !member.verdict ? "Brak odpowiedzi" : <>{VERDICT_SHORT[member.verdict] ?? member.verdict}, siła spinu {member.intensity}/100</>}</li>
      ))}</ul>
      <p className="sc-council__roles">Lekarz prowadzący: {short(council.chair)}{council.linguist ? ` · redaktor: ${short(council.linguist)}` : ""}
        {council.review.model ? ` · ordynator: ${short(council.review.model)} - ${council.review.ok ? "bez zastrzeżeń" : council.review.ok === false ? `uwagi${council.review.revised ? " (diagnoza poprawiona)" : ""}` : "brak odpowiedzi"}` : ""}</p>
    </section>
  );
}

function sourceDomain(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; }
}
