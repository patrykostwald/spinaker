"use client";

import { SpinSummary } from "./SpinSummary";
import { ClinicNav } from "./ClinicNav";
import { SourceDisclosure } from "./SourceDisclosure";
import Link from "next/link";
import { ApiError } from "../../lib/api";
import { useQuery } from "@tanstack/react-query";
import { agreementLabel, getSpin, searchClinicSpins, type SpinDetailData } from "../../lib/clinic";
import { Breadcrumbs } from "../../kit/Breadcrumbs";
import { formatDateTimePl } from "../../lib/utils";
import { OpinionsPanel } from "../OpinionsPanel";
import { AiTag, FitStickyAside, HowToRead, SpinAuthorRow } from "./SpinParts";
import { ShareSpinOnX, ThreadPosts } from "./ShareSpinOnX";
import { CiteShare } from "../CiteShare";
import { CorrectionForm } from "../CorrectionForm";
import { AiNotice, EditorialNote, PUBLICATION_MODEL } from "./AiNotice";
import { agreementWords, modelCompany, modelFullName } from "../../lib/models";
import { clinicResultsUrl } from "../../lib/clinicNavigation";
import { ContextThreadStrip } from '../ContextThreadStrip';
import { useEffect, useRef, useState } from "react";
import { rememberClinicVisit } from "../../lib/clinicHistory";

export function SpinDiagnosisBody({ spin, withSummary = true, share = true }: { spin: SpinDetailData; withSummary?: boolean; share?: boolean }) {
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
      {spin.council ? <details className="sc-spin-detail__models"><summary>Pokaż oceny modeli ({responded(spin.council)} z {spin.council.members.length} odpowiedziało)</summary><CouncilNote council={spin.council} /></details> : <p>Model: {spin.model || "brak danych o modelu"}. Szczegółowe głosy nie są dostępne.</p>}
    </section>
    <section className="sc-spin-detail__section" id={`spin-${spin.id}-ograniczenia`}><h2>Ograniczenia analizy</h2><p className="sc-spin-detail__limits">{spin.limitations || "Nie zapisano dodatkowych ograniczeń tej analizy."}</p></section>
    <p className="sc-spin-detail__meta"><AiTag /> Szczegóły techniczne: {spin.model === "konsylium" ? "Konsylium AI (modele wymienione wyżej)" : modelFullName(spin.model)} · wersja instrukcji {spin.prompt_version} · diagnoza {formatDateTimePl(spin.created_at)}</p>
    <p>Zasady publikacji i korekt: <Link href="/konsylium/karta">Karta Konsylium</Link>.</p>
    {share ? <p className="sc-spin-detail__share"><ShareSpinOnX id={spin.id} spin={spin} /></p> : null}
    <ContextThreadStrip url={spin.post.url} />
  </>;
}

export function SpinDetail({ id, returnTo }: { id: string; returnTo?: string }) {
  const query = useQuery({ queryKey: ["clinic-spin", id], queryFn: () => getSpin(id) });
  const recorded = useRef<number | null>(null);
  // „Wróć do wyników” tylko gdy czytelnik przyszedł z tej samej witryny (wyniki Kliniki) albo ma returnTo.
  const [cameFromSite, setCameFromSite] = useState(false);
  useEffect(() => {
    try { setCameFromSite(Boolean(document.referrer) && new URL(document.referrer).origin === window.location.origin); } catch { setCameFromSite(false); }
  }, []);
  useEffect(() => {
    const spin = query.data;
    if (!spin || recorded.current === spin.id) return;
    recorded.current = spin.id;
    rememberClinicVisit({ type: "diagnosis", id: spin.id, title: spin.headline, camp: spin.camp,
      verdict: spin.verdict, intensity: spin.intensity, author: spin.author.name });
  }, [query.data]);
  if (query.isLoading) return <div className="sc-clinic"><p className="sc-clinic-empty">Wczytujemy diagnozy…</p></div>;
  if (query.isError && !(query.error instanceof ApiError && query.error.status === 404) && !query.data) return <div className="sc-clinic" role="alert"><p>Nie udało się pobrać danych.</p><button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></div>;
  if (!query.data) return <div className="sc-clinic"><p className="sc-clinic-empty">Nie znaleziono diagnozy. <Link href="/klinika">Wróć do Kliniki</Link></p></div>;
  const spin = query.data;
  return (
    <div className="sc-clinic sc-spin-detail">
      {query.isError ? <p role="status">Pokazujemy dane z {new Date(query.dataUpdatedAt).toLocaleString("pl-PL")}. Aktualizacja jest chwilowo niedostępna. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p> : null}
      <ClinicNav />
      <Breadcrumbs items={[{ label: "Klinika", href: "/klinika" }, { label: "Diagnozy", href: clinicResultsUrl(returnTo ?? null) }, { label: spin.headline }]} />
      {returnTo || cameFromSite ? <Link className="sc-spin-detail__back" href={clinicResultsUrl(returnTo ?? null)} scroll={false}>← Wróć do wyników</Link> : null}
      <AiNotice models={aiModels(spin)} version={spin.prompt_version} publication={spin.auto_published ? { mode: "auto", at: spin.created_at } : spin.reviewed_at ? { mode: "manual", at: spin.reviewed_at } : null} explain={PUBLICATION_MODEL} detailsHref={spin.council ? `#spin-${spin.id}-modele` : undefined} />
      {/* Lewa kolumna: źródło i szybkie podsumowanie; prawa: ocena i pełna analiza (uwagi recenzenta UX, 30.09).
          Na telefonie kolejność: ocena → podsumowanie → wpis → analiza. */}
      <div className="sc-dg-layout">
        <FitStickyAside className="sc-dg-side">
        <SourceDisclosure className="sc-spin-detail__post">
          <p className="sc-origin-label" data-kind="original">Oryginał · wpis źródłowy, nie nasza ocena</p>
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
        <SeeAlso spin={spin} />
        </FitStickyAside>
        <div className="sc-dg-main">
        <div className="sc-dg-score"><p className="sc-origin-label" data-kind="assessment">Ocena Konsylium AI · analiza automatyczna, nie nasze rozstrzygnięcie</p><SpinSummary spin={spin} heading="h1" withPoint={false} withTable={false} actions={<div className="sc-dg-actionbar"><CiteShare title={`${spin.verdict_label}: ${spin.headline}`} path={`/klinika/${spin.id}`} author="Dr. Spin, Klinika spinu" kind={`diagnoza AI wpisu @${spin.author.handle}`} publishedAt={spin.created_at} extra={<ThreadPosts spin={spin} />} /><CorrectionForm kind="diagnosis" targetId={spin.id} type="correction" label="Sprostowanie / odpowiedź" /><CorrectionForm kind="diagnosis" targetId={spin.id} type="error" label="Zgłoś błąd" /></div>} /><HowToRead /></div>
        <nav className="sc-spin-detail__anchors" aria-label="W tej diagnozie">{[["techniki", "Techniki"], ["twierdzenia", "Twierdzenia i źródła"], ["modele", "Modele"], ["ograniczenia", "Ograniczenia"]].map(([anchor, label]) => <a key={anchor} href={`#spin-${spin.id}-${anchor}`}>{label}</a>)}</nav>
        <article className="sc-spin-detail__diagnosis">
          <SpinDiagnosisBody spin={spin} withSummary={false} share={false} />
          <p className="sc-clinic-roadmap">{spin.notice}</p>
          <EditorialNote />
        </article>
        </div>
      </div>
      <OpinionsPanel endpoint={`/api/clinic/spins/${spin.id}/opinions/`} labels={{
        kicker: "REAKCJE CZYTELNIKÓW",
        question: "Czy ta diagnoza jest trafna?",
        positive: "Trafna",
        negative: "Nietrafna",
        signedOut: "Zaloguj się, aby ocenić diagnozę i dodać komentarz. Komentarz zawsze idzie z reakcją.",
      }} />
    </div>
  );
}


/** „Zobacz też”: nowsza i starsza diagnoza tej samej osoby oraz kilka innych jej diagnoz (bez algorytmu „podobne”). */
function SeeAlso({ spin }: { spin: SpinDetailData }) {
  const accountId = spin.author.account_id;
  const enabled = Number.isSafeInteger(accountId) && accountId! > 0;
  const query = useQuery({
    queryKey: ["clinic-see-also", accountId],
    queryFn: () => searchClinicSpins({ account: String(accountId), sort: "new", page_size: 12 }),
    enabled,
  });
  const list = query.data?.results ?? [];
  const index = list.findIndex(item => item.id === spin.id);
  const newer = index > 0 ? list[index - 1] : null;
  const older = index >= 0 && index < list.length - 1 ? list[index + 1] : null;
  const others = list.filter(item => item.id !== spin.id && item.id !== newer?.id && item.id !== older?.id).slice(0, 3);
  const profile = spin.author.figure_id ? `/osoby-publiczne/${spin.author.figure_id}` : null;
  if (!newer && !older && !others.length && !profile) return null;
  const entry = (item: (typeof list)[number], prefix?: string) => (
    <li key={item.id}>
      <Link href={`/klinika/${item.id}`}>{prefix ? <span className="sc-see-also__prefix">{prefix}</span> : null}{item.headline}</Link>
      <span className="sc-see-also__meta">{item.verdict_label} · {formatDateTimePl(item.post.published_at)}</span>
    </li>
  );
  return (
    <nav className="sc-see-also" aria-labelledby="sc-see-also-title">
      <h2 id="sc-see-also-title" className="sc-t-title-m">Zobacz też</h2>
      <p className="sc-see-also__lead">Diagnozy wpisów: {spin.author.name}</p>
      <ul className="sc-see-also__list" role="list">
        {older ? entry(older, "Poprzednia") : null}
        {newer ? entry(newer, "Następna") : null}
        {others.map(item => entry(item))}
      </ul>
      <p className="sc-see-also__more">
        {profile ? <Link href={profile}>Profil: {spin.author.name} →</Link> : null}
        {enabled ? <Link href={`/klinika/diagnozy?account=${accountId}`}>Wszystkie diagnozy tej osoby →</Link> : null}
      </p>
    </nav>
  );
}

const VERDICT_SHORT: Record<string, string> = { spin: "spin", partial: "częściowy spin", no_spin: "bez spinu", unclear: "nie da się ocenić" };
const short = (model: string) => model.split("/").pop() ?? model;

const responded = (council: NonNullable<SpinDetailData["council"]>) => council.members.filter(member => member.intensity != null && member.verdict).length;
const aiModels = (spin: SpinDetailData) => {
  const companies = Array.from(new Set((spin.council?.members ?? []).filter(member => member.intensity != null && member.verdict)
    .map(member => member.company || modelCompany(member.model)).filter(Boolean)));
  return companies.length ? companies.join(", ") : spin.model === "konsylium" ? "Konsylium AI (kilka modeli różnych firm)" : modelFullName(spin.model);
};
const memberName = (member: { model: string; company?: string }) => modelFullName(member.model, member.company);

/** Konsylium Dr. Spina: pełne nazwy i firmy modeli, kto odpowiedział, jak zagłosował, lekarz prowadzący, redaktor i ordynator. */
function CouncilNote({ council }: { council: NonNullable<SpinDetailData["council"]> }) {
  const answered = responded(council);
  const silent = council.members.filter(member => member.intensity == null || !member.verdict);
  return (
    <section className="sc-council sc-spin-detail__section" aria-label="Konsylium Dr. Spina">
      <h2>Oceny modeli</h2>
      <p className="sc-council__title">Konsylium Dr. Spina: odpowiedziało {answered} z {council.members.length} modeli{agreementWords(council.agreement) ? `; ${agreementWords(council.agreement)}` : ""}{council.escalated ? " · konsultacja specjalisty: fakty sprawdził dodatkowo mocniejszy model z wyszukiwaniem" : ""}</p>
      <p className="sc-council__caveat">Zgodność modeli nie jest niezależnym potwierdzeniem: modele mogą się mylić tak samo, bo uczono je na podobnych danych.</p>
      <ul>{council.members.map(member => (
        <li key={member.model}><strong>{memberName(member)}</strong> — {member.intensity == null || !member.verdict
          ? `brak odpowiedzi${member.note === "timeout" ? " (model nie odpowiedział w limicie czasu)" : member.note ? ` (${member.note})` : ""}; nie wlicza się do wyniku`
          : <>{VERDICT_SHORT[member.verdict] ?? member.verdict}, siła spinu {member.intensity}/100</>}</li>
      ))}</ul>
      {silent.length ? <p className="sc-council__caveat">Liczymy tylko modele, które odpowiedziały ({answered}); {silent.length === 1 ? "jeden model" : `${silent.length} modele`} bez odpowiedzi nie głosuje.</p> : null}
      <p className="sc-council__roles">Lekarz prowadzący: {modelFullName(council.chair)}{council.linguist ? ` · redaktor: ${modelFullName(council.linguist)}` : ""}
        {council.review.model ? ` · ordynator: ${modelFullName(council.review.model)} — ${council.review.ok ? "bez zastrzeżeń" : council.review.ok === false ? `uwagi${council.review.revised ? " (diagnoza poprawiona)" : ""}` : "brak odpowiedzi"}` : ""}</p>
    </section>
  );
}

function sourceDomain(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; }
}
