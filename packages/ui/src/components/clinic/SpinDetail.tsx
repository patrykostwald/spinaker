"use client";

import { SpinSummary, ReportError } from "./SpinSummary";
import { ClinicNav } from "./ClinicNav";
import { SourceDisclosure } from "./SourceDisclosure";
import Link from "next/link";
import { ApiError } from "../../lib/api";
import { useQuery } from "@tanstack/react-query";
import { agreementLabel, getSpin, type SpinDetailData } from "../../lib/clinic";
import { formatDateTimePl } from "../../lib/utils";
import { OpinionsPanel } from "../OpinionsPanel";
import { AiTag, SpinAuthorRow } from "./SpinParts";
import { ShareSpinOnX } from "./ShareSpinOnX";

export function SpinDiagnosisBody({ spin, withSummary = true }: { spin: SpinDetailData; withSummary?: boolean }) {
  return <>
    {withSummary ? <SpinSummary spin={spin} heading="h2" /> : null}
    <p className="sc-spin-detail__summary">{spin.summary}</p>
    <div className="sc-spin-detail__analysis">{spin.analysis.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>

    {spin.techniques.length > 0 && <section className="sc-spin-detail__section">
      <h2>Techniki perswazji</h2>
      <p className="sc-spin-detail__intro">Jak zbudowano przekaz: techniki, cytaty i wyjaśnienia.</p>
      <ol className="sc-spin-detail__techniques">{spin.techniques.map((item, index) => (
        <li key={index}><strong>{item.name}</strong><blockquote>„{item.quote}”</blockquote><p>{item.explanation}</p></li>
      ))}</ol>
    </section>}

    {spin.claims.length > 0 && <section className="sc-spin-detail__section">
      <h2>Twierdzenia i źródła</h2>
      <p className="sc-spin-detail__intro">Co można sprawdzić i jakie źródła wykorzystano w analizie.</p>
      <ul className="sc-spin-detail__claims">{spin.claims.map((claim, index) => (
        <li key={index} data-assessment={claim.assessment}>
          <p className="sc-spin-detail__claim"><span className="sc-verdict" data-assessment={claim.assessment}>{claim.assessment_label}</span> {claim.claim}</p>
          {claim.explanation && <p>{claim.explanation}</p>}
          {claim.sources.length > 0 && <ul className="sc-spin-detail__sources">{claim.sources.map(source => (
            <li key={source.url}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title || "Źródło"} · {sourceDomain(source.url)} ↗</a></li>
          ))}</ul>}
        </li>
      ))}</ul>
    </section>}

    {spin.limitations && <section className="sc-spin-detail__section"><h2>Ograniczenia analizy</h2><p className="sc-spin-detail__limits">{spin.limitations}</p></section>}
    {spin.council ? <CouncilNote council={spin.council} /> : null}
    <p className="sc-spin-detail__meta"><AiTag /> Model {spin.model} · instrukcja {spin.prompt_version} · diagnoza {formatDateTimePl(spin.created_at)}{spin.auto_published ? " · opublikowana automatycznie" : spin.reviewed_at ? ` · zatwierdzona bez zmian ${formatDateTimePl(spin.reviewed_at)}` : ""}</p>
    <p>Zasady publikacji i korekt: <Link href="/konsylium/karta">Karta Konsylium</Link>.</p>
    <p><ReportError spin={spin} /></p>
    <p className="sc-spin-detail__share"><ShareSpinOnX id={spin.id} spin={spin} /></p>
  </>;
}

export function SpinDetail({ id }: { id: string }) {
  const query = useQuery({ queryKey: ["clinic-spin", id], queryFn: () => getSpin(id) });
  if (query.isLoading) return <div className="sc-clinic"><p className="sc-clinic-empty">Wczytujemy diagnozy…</p></div>;
  if (query.isError && !(query.error instanceof ApiError && query.error.status === 404) && !query.data) return <div className="sc-clinic" role="alert"><p>Nie udało się pobrać danych.</p><button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></div>;
  if (!query.data) return <div className="sc-clinic"><p className="sc-clinic-empty">Nie znaleziono diagnozy. <Link href="/klinika">Wróć do Kliniki</Link></p></div>;
  const spin = query.data;
  return (
    <div className="sc-clinic sc-spin-detail">
      {query.isError ? <p role="status">Pokazujemy dane z {new Date(query.dataUpdatedAt).toLocaleString("pl-PL")}. Aktualizacja jest chwilowo niedostępna. <button type="button" onClick={() => void query.refetch()}>Spróbuj ponownie</button></p> : null}
      <ClinicNav />
      <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} />
      <SpinSummary spin={spin} heading="h1" />
      <div className="sc-spin-detail__grid">
        <article className="sc-spin-detail__diagnosis">
          <SpinDiagnosisBody spin={spin} withSummary={false} />
          <p className="sc-clinic-roadmap">{spin.notice}</p>
        </article>
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

/** Konsylium Dr. Spina: kto oceniał, jak zagłosował, lekarz prowadzący, redaktor i ordynator. */
function CouncilNote({ council }: { council: NonNullable<SpinDetailData["council"]> }) {
  return (
    <section className="sc-council sc-spin-detail__section" aria-label="Konsylium Dr. Spina">
      <h2>Oceny modeli</h2>
      <p className="sc-council__title">Konsylium Dr. Spina · {agreementLabel(council.agreement)}{council.escalated ? " · konsultacja specjalisty: fakty sprawdził dodatkowo mocniejszy model z wyszukiwaniem" : ""}</p>
      <ul>{council.members.map(member => (
        <li key={member.model}><strong>{short(member.model)}</strong> — {member.intensity == null || !member.verdict ? "Brak odpowiedzi" : <>{VERDICT_SHORT[member.verdict] ?? member.verdict}, siła spinu {member.intensity}/100</>}</li>
      ))}</ul>
      <p className="sc-council__roles">Lekarz prowadzący: {short(council.chair)}{council.linguist ? ` · redaktor: ${short(council.linguist)}` : ""}
        {council.review.model ? ` · ordynator: ${short(council.review.model)} — ${council.review.ok ? "bez zastrzeżeń" : council.review.ok === false ? `uwagi${council.review.revised ? " (diagnoza poprawiona)" : ""}` : "brak odpowiedzi"}` : ""}</p>
    </section>
  );
}

function sourceDomain(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; }
}
