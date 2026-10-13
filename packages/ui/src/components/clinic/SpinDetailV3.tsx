"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { agreementLabel, searchClinicSpins, type SpinDetailData } from "../../lib/clinic";
import { diagnosisPresentation } from "../../lib/diagnosisPresentation";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { initials } from "../../lib/spinScale";
import { clinicResultsUrl } from "../../lib/clinicNavigation";
import { SpinMeter } from "../../kit/SpinMeter";
import { SpinRow } from "../../kit/SpinRow";
import { ClinicNav } from "./ClinicNav";
import { ClinicDiscussion } from "./ClinicDiscussion";
import { HowToRead } from "./SpinParts";
import { ReportError, modelLabel } from "./SpinSummary";
import { ShareSpinOnX } from "./ShareSpinOnX";
import { AuthorReplies } from "./ClinicCorrections";
import { PositionChanges } from "./PositionChanges";
import { SpinReceptionBlock } from "./SpinReception";
import { ArchiveNote, FactChecks } from "./OpenSources";
import { ContextThreadStrip } from "../ContextThreadStrip";
import { useFeature } from "../../lib/features";

const FAMILY_SHORT: Record<string, string> = { spor: "Spór", przedstawienie: "Emocje", dane: "Dane", inne: "Inne" };
const VERDICT_SHORT: Record<string, string> = { spin: "spin", partial: "częściowy spin", no_spin: "bez spinu", unclear: "nie da się ocenić" };
const short = (model: string) => model.split("/").pop() ?? model;
const sourceDomain = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; } };
const InfoIcon = () => <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.5" /></svg>;
const ExtIcon = () => <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>;

/** Spis treści z podświetleniem bieżącej sekcji (od 1180 px; węziej ukryty). */
function Toc({ items }: { items: Array<[string, string]> }) {
  const [active, setActive] = useState(items[0]?.[0]);
  useEffect(() => {
    if (!("IntersectionObserver" in window)) return;
    const nodes = items.map(([id]) => document.getElementById(id)).filter(Boolean) as HTMLElement[];
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible[0]) setActive(visible[0].target.id);
    }, { rootMargin: "-20% 0px -65% 0px" });
    nodes.forEach(node => observer.observe(node));
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- klucz z identyfikatorów, nie z tożsamości tablicy
  }, [items.map(([id]) => id).join()]);
  return <nav className="sc-v3-toc" aria-label="Na tej stronie"><p>Na tej stronie</p>
    {items.map(([id, label]) => <a key={id} href={`#${id}`} data-active={active === id || undefined} aria-current={active === id ? "location" : undefined}>{label}</a>)}
  </nav>;
}

function NextSpinsV3({ current }: { current: number }) {
  const query = useQuery({ queryKey: ["clinic-next", current], queryFn: () => searchClinicSpins({}), staleTime: 60_000 });
  const rows = (query.data?.results ?? []).filter(row => row.id !== current).slice(0, 3);
  if (!rows.length) return null;
  return <section className="sc-v3-dg-next" aria-labelledby="dg-next-title">
    <div className="sc-v3-feed-h"><h2 id="dg-next-title">Kolejne diagnozy</h2><Link className="sc-v3-lnk" href="/klinika/diagnozy">Wszystkie diagnozy <span className="sc-v3-ar" aria-hidden="true">→</span></Link></div>
    {/* jeden schemat wiersza zamiast wąskich kart (tytuły w kartach łamały się na 6 linii) */}
    <ol className="sc-v3-rows">{rows.map((row, index) => <SpinRow key={row.id} index={index} href={`/klinika/${row.id}`} name={row.author?.name ?? ""} kind={<>Diagnoza AI · {row.verdict === "unclear" ? "Nie da się ocenić" : row.verdict_label}</>}
      title={row.headline} meta={[row.author?.name, row.post?.published_at ? <time key="t" dateTime={row.post.published_at}>{formatDateTimePl(row.post.published_at)}</time> : null, `#SPIN-${row.id}`]} value={row.intensity} />)}</ol>
  </section>;
}

/**
 * Diagnoza v3 (prototyp spin-v3/klinika/5884): siedem sekcji w kolejności fakt, opinia AI, liczba, twierdzenia,
 * uzasadnienie, ograniczenia, dyskusja; spis treści po prawej od 1180 px. Wszystkie dotychczasowe bloki zostają
 * (weryfikacje, zmiana zdania, odbiór, odpowiedź autora, redakcja językowa, udostępnianie, kolejne diagnozy).
 */
export function SpinDetailV3({ spin, returnTo }: { spin: SpinDetailData; returnTo?: string }) {
  const { techniques, families, claims, council } = useMemo(() => diagnosisPresentation(spin), [spin]);
  const models = council.responses.map(vote => ({ label: modelLabel(vote.model), value: vote.intensity }));
  const discussion = useFeature("ACCOUNTS_ENABLED");
  const unverified = spin.claims.some(claim => claim.assessment === "unverified");
  const title = spin.headline;
  const toc: Array<[string, string]> = [["dg-cytat", "Cytat"], ["dg-technika", "Technika AI"], ["dg-sila", "Siła spinu"], ["dg-twierdzenia", "Twierdzenia"],
    ...(spin.factchecks?.length ? [[`spin-${spin.id}-sprawdzili`, "Tę tezę sprawdzili"]] as Array<[string, string]> : []),
    ...(spin.position_changes?.items.length ? [[`spin-${spin.id}-zmiana-zdania`, "Zmiana zdania"]] as Array<[string, string]> : []),
    ...(spin.reception ? [[`spin-${spin.id}-odbior`, "Jak zadziałało"]] as Array<[string, string]> : []),
    ["dg-uzasadnienie", "Uzasadnienie"], ["dg-ograniczenia", "Ograniczenia analizy"], ...(discussion ? [["dg-dyskusja", "Dyskusja"]] as Array<[string, string]> : [])];

  return <div className="sc-v3 sc-v3-page sc-v3-dg">
    <ClinicNav />
    <p className="sc-v3-ctx">
      <Link className="sc-v3-crumb" href={returnTo ? clinicResultsUrl(returnTo) : "/klinika/diagnozy"} scroll={false}>← {returnTo ? "Wróć do wyników" : "Wszystkie diagnozy"}</Link>
      <span className="sc-v3-tag" data-tone="accent" title="Diagnoza przygotowana przez system AI (Konsylium kilku modeli różnych firm). Nikt nie edytuje jej treści.">AI</span>
      <span className="sc-v3-tag" title="Wersja testowa">BETA</span>
      <span>Ocena AI, może zawierać błędy</span><span className="sc-v3-dot" aria-hidden="true">·</span><span>Te same kryteria dla wszystkich partii</span>
      <Link className="sc-v3-lnk" href="/metodologia">Metoda <span className="sc-v3-ar" aria-hidden="true">→</span></Link>
    </p>

    <div className="sc-v3-dg__grid">
      <div className="sc-v3-dg__main">
        <section id="dg-cytat" className="sc-v3-dg-sec" aria-labelledby="dg-cytat-h">
          <h2 id="dg-cytat-h">Cytat<small>Fakt: treść wpisu w chwili pobrania.</small></h2>
          <figure className="sc-v3-quote">
            <figcaption className="sc-v3-quote__who">
              <span className="sc-v3-av" aria-hidden="true">{initials(spin.author.name)}</span>
              <span><b>{spin.author.name}</b><span>@{spin.author.handle} · {formatDateTimePl(spin.post.published_at)} · {spin.camp_label}{spin.author.role_title ? ` · ${spin.author.role_title}` : ""}</span></span>
            </figcaption>
            <blockquote lang="pl">{spin.post.text}</blockquote>
            {spin.post.media.filter(item => item.url).slice(0, 2).map(item => (
              // eslint-disable-next-line @next/next/no-img-element -- miniatura z oficjalnego API X
              <figure key={item.url} className="sc-v3-quote__media"><img src={item.url} alt={item.alt || "Załącznik do wpisu"} loading="lazy" referrerPolicy="no-referrer" /><figcaption><a className="sc-v3-lnk" href={item.url} target="_blank" rel="noopener noreferrer">Pokaż cały załącznik <ExtIcon /></a></figcaption></figure>
            ))}
            <p className="sc-v3-quote__f"><span>Treść mogła zostać zmieniona lub usunięta po pobraniu.</span><a className="sc-v3-lnk" href={spin.post.url} target="_blank" rel="noopener noreferrer">Oryginalny wpis na X <ExtIcon /></a></p>
          </figure>
        </section>

        <section id="dg-technika" className="sc-v3-dg-sec" aria-labelledby="dg-title">
          <h2 className="sc-v3-dg-sec__h">Technika AI<small>Opinia modeli: jak zbudowano przekaz.</small></h2>
          <p className="sc-v3-dg-k"><span>#SPIN-{spin.id}</span><span>{spin.verdict === "unclear" ? "Nie da się ocenić" : spin.verdict_label}</span><time dateTime={spin.scan?.diagnosed_at || spin.created_at}>{formatDatePl(spin.scan?.diagnosed_at || spin.created_at)}</time><HowToRead /></p>
          <h1 id="dg-title" className="sc-v3-dg-title">{title}</h1>
          <p className="sc-v3-dg-short"><b>W skrócie.</b> {spin.summary}</p>
          {techniques.length ? <>
            <ul className="sc-v3-chips" aria-label="Techniki perswazji">{techniques.filter((item, index, all) => all.findIndex(other => other.label === item.label) === index).map(item => <li key={item.label} className="sc-v3-chip" data-fam={item.family}><i aria-hidden="true" />{item.label}</li>)}</ul>
            <p className="sc-v3-fam-leg">{families.filter(family => family.count).map(family => <span key={family.key} data-fam={family.key}><i aria-hidden="true" />{FAMILY_SHORT[family.key]} {family.count}</span>)}</p>
            <ol className="sc-v3-techs">{spin.techniques.map((item, index) => {
              const fam = techniques[index]?.family ?? "inne";
              return <li key={index} className="sc-v3-tech" data-fam={fam}>
                <h3><i aria-hidden="true" />{item.name}</h3>
                {item.quote ? <q>{item.quote}</q> : null}
                {item.explanation ? <p>{item.explanation}</p> : null}
              </li>;
            })}</ol>
          </> : <p className="sc-v3-empty">Nie wskazano technik w tej analizie.</p>}
        </section>

        <section id="dg-sila" className="sc-v3-dg-sec" aria-labelledby="dg-sila-h">
          <h2 id="dg-sila-h">Siła spinu</h2>
          <div className="sc-v3-power">
            <SpinMeter value={spin.intensity} size="lg" label="Siła spinu tego wpisu" models={models}
              legend={models.length ? models.map(model => `${model.label} ${model.value ?? "-"}`).join(" · ") : undefined} />
            <p className="sc-v3-power__txt"><b>Ocena AI jednego wpisu.</b> Nie mówi o prawdziwości wypowiedzi ani o osobie. {models.length ? "Krótkie szare kreski to oceny poszczególnych modeli na tej samej linii; kreska w kolorze to wynik diagnozy. " : ""}Konsylium AI: {agreementLabel(council.agreement)}{council.agreement ? ` (${council.agreement})` : ""}.</p>
            {spin.council ? <details className="sc-v3-details"><summary>Skład Konsylium i role modeli</summary>
              <ul className="sc-v3-plain-list">{spin.council.members.map(member => <li key={member.model}><b>{short(member.model)}</b> - {member.intensity == null || !member.verdict ? "brak odpowiedzi" : <>{VERDICT_SHORT[member.verdict] ?? member.verdict}, siła spinu {member.intensity}/100</>}</li>)}</ul>
              <p>Lekarz prowadzący: {short(spin.council.chair)}{spin.council.linguist ? ` · redaktor: ${short(spin.council.linguist)}` : ""}{spin.council.review.model ? ` · ordynator: ${short(spin.council.review.model)} - ${spin.council.review.ok ? "bez zastrzeżeń" : spin.council.review.ok === false ? `uwagi${spin.council.review.revised ? " (diagnoza poprawiona)" : ""}` : "brak odpowiedzi"}` : ""}{spin.council.escalated ? " · konsultacja specjalisty: fakty sprawdził dodatkowo mocniejszy model z wyszukiwaniem" : ""}</p>
            </details> : <p className="sc-v3-meta">Model: {spin.model || "brak danych o modelu"}. Szczegółowe głosy nie są dostępne.</p>}
          </div>
        </section>

        <section id="dg-twierdzenia" className="sc-v3-dg-sec" aria-labelledby="dg-tw-h">
          <h2 id="dg-tw-h">Twierdzenia<small>Status z wyszukiwania źródeł{claims.some(claim => claim.count) ? `: ${claims.filter(claim => claim.count).map(claim => `${claim.label} ${claim.count}`).join(", ")}` : ""}.</small></h2>
          {spin.claims.length ? <ul className="sc-v3-claims">{spin.claims.map((claim, index) => <li key={index} data-assessment={claim.assessment}>
            <details>
              <summary><span className="sc-v3-st" data-assessment={claim.assessment}>{claim.assessment_label}</span><span className="sc-v3-claim__t">{claim.claim}</span>{claim.sources.length ? <span className="sc-v3-claim__n">{claim.sources.length} {claim.sources.length === 1 ? "źródło" : claim.sources.length < 5 ? "źródła" : "źródeł"}</span> : null}</summary>
              <div className="sc-v3-claim__body">
                {claim.explanation ? <p>{claim.explanation}</p> : null}
                {claim.sources.length ? <ul>{claim.sources.map(source => <li key={source.url}><a className="sc-v3-lnk" href={source.url} target="_blank" rel="noopener noreferrer">{source.title || "Źródło"} · {sourceDomain(source.url)} <ExtIcon /></a> <ArchiveNote archive={spin.source_archives?.[source.url]} /></li>)}</ul> : null}
              </div>
            </details>
          </li>)}</ul> : <p className="sc-v3-empty">Brak osobno sprawdzonych twierdzeń.</p>}
          {unverified ? <p className="sc-v3-meta">Niezweryfikowane: nie sprawdzono lub brak źródła. To nie znaczy, że twierdzenie jest fałszywe.</p> : null}
        </section>

        <FactChecks id={spin.id} items={spin.factchecks} />
        <PositionChanges id={spin.id} block={spin.position_changes} />
        <SpinReceptionBlock id={spin.id} block={spin.reception} />

        <section id="dg-uzasadnienie" className="sc-v3-dg-sec sc-v3-prose" aria-labelledby="dg-uz-h">
          <h2 id="dg-uz-h">Uzasadnienie</h2>
          {spin.analysis.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
          {spin.notice ? <p className="sc-v3-prose__quiet">{spin.notice}</p> : null}
          {spin.readability_edit ? <details className="sc-v3-details"><summary>Redakcja językowa: tekst wygładzony, sens bez zmian · pokaż tekst pierwotny</summary>
            {Object.entries(spin.readability_edit.original).map(([key, text]) => <p key={key}><b>{key === "headline" ? "Nagłówek" : key === "summary" ? "W skrócie" : "Uzasadnienie"}:</b> {text}</p>)}
          </details> : null}
          <p className="sc-v3-meta">Model {spin.model} · instrukcja {spin.prompt_version} · diagnoza {formatDateTimePl(spin.created_at)}{spin.auto_published ? " · opublikowana automatycznie" : spin.reviewed_at ? ` · zatwierdzona bez zmian ${formatDateTimePl(spin.reviewed_at)}` : ""} · zasady publikacji i korekt: <Link className="sc-v3-inl" href="/konsylium/karta">Karta Konsylium</Link></p>
        </section>

        <section id="dg-ograniczenia" className="sc-v3-dg-sec" aria-labelledby="dg-og-h">
          <h2 id="dg-og-h">Ograniczenia analizy</h2>
          <p className="sc-v3-note"><InfoIcon /><span>{spin.limitations || "Nie zapisano dodatkowych ograniczeń tej analizy."}</span></p>
          <p className="sc-v3-acts"><ReportError spin={spin} /><ShareSpinOnX id={spin.id} spin={spin} /></p>
        </section>

        {spin.author_replies?.length ? <div className="sc-v3-dg-sec"><AuthorReplies replies={spin.author_replies} /></div> : null}

        {/* dyskusja tylko przy włączonych kontach (ClinicDiscussion bez kont zwraca null) */}
        {discussion ? <section id="dg-dyskusja" className="sc-v3-dg-sec" aria-label="Dyskusja"><ClinicDiscussion kind="spins" id={spin.id} /></section> : null}

        <NextSpinsV3 current={spin.id} />
        <ContextThreadStrip url={spin.post.url} />
        <p className="sc-v3-meta">Analizujemy codziennie, bez reklam i bez pieniędzy od partii. <Link className="sc-v3-inl" href="/wsparcie">Wesprzyj Klinikę</Link></p>
      </div>
      <Toc items={toc} />
    </div>
  </div>;
}

