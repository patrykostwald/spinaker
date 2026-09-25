"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getSpin, type SpinDetailData } from "../../lib/clinic";
import { formatDateTimePl } from "../../lib/utils";
import { OpinionsPanel } from "../OpinionsPanel";
import { AiTag, IntensityMeter, SpinAuthorRow, VerdictTag } from "./SpinParts";

export function SpinDiagnosisBody({ spin }: { spin: SpinDetailData }) {
  return <>
    <p className="sc-spin-card__verdict"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><IntensityMeter value={spin.intensity} /></p>
    <h1 className="sc-spin-detail__headline">{spin.headline}</h1>
    <p className="sc-spin-detail__summary">{spin.summary}</p>
    <div className="sc-spin-detail__analysis">{spin.analysis.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>

    {spin.techniques.length > 0 && <section className="sc-spin-detail__section">
      <h2>Techniki</h2>
      <ol className="sc-spin-detail__techniques">{spin.techniques.map((item, index) => (
        <li key={index}><strong>{item.name}</strong><blockquote>„{item.quote}”</blockquote><p>{item.explanation}</p></li>
      ))}</ol>
    </section>}

    {spin.claims.length > 0 && <section className="sc-spin-detail__section">
      <h2>Twierdzenia i źródła</h2>
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
    <p className="sc-spin-detail__meta"><AiTag /> Model {spin.model} · instrukcja {spin.prompt_version} · diagnoza {formatDateTimePl(spin.created_at)}{spin.reviewed_at ? ` · zatwierdzona bez zmian ${formatDateTimePl(spin.reviewed_at)}` : ""}</p>
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
