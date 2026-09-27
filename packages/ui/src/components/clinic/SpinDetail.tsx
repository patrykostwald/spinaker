"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getSpin, type SpinDetailData } from "../../lib/clinic";
import { formatDateTimePl } from "../../lib/utils";
import { OpinionsPanel } from "../OpinionsPanel";
import { AiTag, IntensityMeter, SpinAuthorRow, VerdictTag } from "./SpinParts";
import { ShareSpinOnX } from "./ShareSpinOnX";

export function SpinDiagnosisBody({ spin }: { spin: SpinDetailData }) {
  return <>
    <p className="sc-spin-card__verdict"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><IntensityMeter value={spin.intensity} /></p>
    <h1 className="sc-spin-detail__headline">{spin.headline}</h1>
    <p className="sc-spin-detail__summary">{spin.summary}</p>
    <div className="sc-spin-detail__analysis">{spin.analysis.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>

    {spin.techniques.length > 0 && <section className="sc-spin-detail__section">
      <h2>Diagnoza — techniki perswazji</h2>
      <p className="sc-spin-detail__intro">Jak zbudowano przekaz: każda technika z dosłownym cytatem z wpisu.</p>
      <ol className="sc-spin-detail__techniques">{spin.techniques.map((item, index) => (
        <li key={index}><strong>{item.name}</strong><blockquote>„{item.quote}”</blockquote><p>{item.explanation}</p></li>
      ))}</ol>
    </section>}

    {spin.claims.length > 0 && <section className="sc-spin-detail__section">
      <h2>Terapia — co mówią źródła</h2>
      <p className="sc-spin-detail__intro">Dr. Spin zaleca sprawdzić twierdzenia we wpisie u źródła: ocena każdego i linki, które ją uzasadniają.</p>
      <ul className="sc-spin-detail__claims">{spin.claims.map((claim, index) => (
        <li key={index} data-assessment={claim.assessment}>
          <p className="sc-spin-detail__claim"><span className="sc-verdict" data-assessment={claim.assessment}>{claim.assessment_label}</span> {claim.claim}</p>
          {claim.explanation && <p>{claim.explanation}</p>}
          {claim.sources.length > 0 && <ul className="sc-spin-detail__sources">{claim.sources.map(source => (
            <li key={source.url}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title || source.url} ↗</a></li>
          ))}</ul>}
        </li>
      ))}</ul>
    </section>}

    {spin.limitations && <p className="sc-spin-detail__limits"><strong>Ograniczenia diagnozy:</strong> {spin.limitations}</p>}
    {spin.council ? <CouncilNote council={spin.council} /> : null}
    <p className="sc-spin-detail__meta"><AiTag /> Model {spin.model} · instrukcja {spin.prompt_version} · diagnoza {formatDateTimePl(spin.created_at)}{spin.auto_published ? " · opublikowana automatycznie, bez redakcji człowieka" : spin.reviewed_at ? ` · zatwierdzona bez zmian ${formatDateTimePl(spin.reviewed_at)}` : ""}</p>
    <p className="sc-spin-detail__share"><ShareSpinOnX id={spin.id} spin={spin} /></p>
  </>;
}

export function SpinDetail({ id }: { id: string }) {
  const query = useQuery({ queryKey: ["clinic-spin", id], queryFn: () => getSpin(id) });
  if (query.isLoading) return <div className="sc-clinic"><p className="sc-clinic-empty">Ładowanie diagnozy…</p></div>;
  if (!query.data) return <div className="sc-clinic"><p className="sc-clinic-empty">Nie znaleziono diagnozy. <Link href="/klinika">Wróć do Kliniki</Link></p></div>;
  const spin = query.data;
  return (
    <div className="sc-clinic sc-spin-detail">
      <p><Link href="/klinika" className="sc-spin-detail__back">← Klinika spinu</Link></p>
      <div className="sc-spin-detail__grid">
        <aside className="sc-spin-detail__post">
          <p className="sc-clinic-kicker">{spin.camp_label}</p>
          <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} size="lg" />
          {spin.author.role_title && <p className="sc-spin-detail__role">{spin.author.role_title}</p>}
          <p className="sc-spin-card__text sc-spin-card__text--full">{spin.post.text}</p>
          {spin.post.media.filter(item => item.url).slice(0, 2).map(item => (
            // eslint-disable-next-line @next/next/no-img-element -- miniatura z oficjalnego API X
            <img key={item.url} className="sc-spin-card__media" src={item.url} alt={item.alt || "Załącznik do posta"} loading="lazy" referrerPolicy="no-referrer" />
          ))}
          <a className="sc-spin-card__source" href={spin.post.url} target="_blank" rel="noopener noreferrer">Oryginalny post na X ↗</a>
        </aside>
        <article className="sc-spin-detail__diagnosis">
          <SpinDiagnosisBody spin={spin} />
          <p className="sc-clinic-roadmap">{spin.notice}</p>
        </article>
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


const VERDICT_SHORT: Record<string, string> = { spin: "spin", partial: "częściowy spin", no_spin: "bez spinu", unclear: "nie da się ocenić" };
const short = (model: string) => model.split("/").pop() ?? model;

/** Konsylium Dr. Spina: kto oceniał, jak zagłosował, kto napisał, poprawił język i zrecenzował diagnozę. */
function CouncilNote({ council }: { council: NonNullable<SpinDetailData["council"]> }) {
  return (
    <section className="sc-council" aria-label="Konsylium Dr. Spina">
      <p className="sc-council__title">Konsylium Dr. Spina · zgodność {council.agreement}{council.escalated ? " · konsultacja specjalisty: fakty sprawdził dodatkowo mocniejszy model z wyszukiwaniem" : ""}</p>
      <ul>{council.members.map(member => (
        <li key={member.model}><strong>{short(member.model)}</strong> — {VERDICT_SHORT[member.verdict] ?? member.verdict}, siła {member.intensity}/100</li>
      ))}</ul>
      <p className="sc-council__roles">Przewodniczący: {short(council.chair)}{council.linguist ? ` · językoznawca: ${short(council.linguist)}` : ""}
        {council.review.model ? ` · recenzent: ${short(council.review.model)} — ${council.review.ok ? "bez zastrzeżeń" : council.review.ok === false ? `uwagi${council.review.revised ? " (diagnoza poprawiona)" : ""}` : "brak odpowiedzi"}` : ""}</p>
    </section>
  );
}
