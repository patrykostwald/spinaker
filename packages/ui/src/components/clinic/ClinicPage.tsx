"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "../../kit";
import { Strip } from "../../kit/home/Strip";
import { CAMPS, CAMP_LABELS, getClinicAccounts, getClinicPage, type Camp, type DailyMessage, type SpinDetailData } from "../../lib/clinic";
import { formatDatePl } from "../../lib/utils";
import { AiTag, IntensityMeter, PartyBadge, SpinAuthorRow, SpinRow, SpinScale, VerdictTag } from "./SpinParts";
import { ShareSpinOnX } from "./ShareSpinOnX";

const CONTACT = "kontakt@spin.clinic";

export function MessageBox({ camp, message, emptyText }: { camp: Camp; message: DailyMessage | null; emptyText?: string }) {
  return (
    <article className="sc-clinic-message" data-camp={camp}>
      <p className="sc-clinic-kicker">{CAMP_LABELS[camp]} · przekaz dnia <AiTag /></p>
      {message ? <>
        <p className="sc-clinic-message__text">{message.message}</p>
        {message.themes.length > 0 && <ul className="sc-spin-techniques" aria-label="Główne hasła">{message.themes.map(theme => <li key={theme}>{theme}</li>)}</ul>}
        <p className="sc-clinic-message__meta">{formatDatePl(message.day)} · z {message.posts_count} postów</p>
      </> : <p className="sc-clinic-empty">{emptyText ?? "Przekaz dnia pojawi się, gdy posty opublikują co najmniej trzy konta tego obozu."}</p>}
    </article>
  );
}

/** Spin dnia jako nitka: box główny (post + diagnoza), a za nim boxy kontekstu — źródła twierdzeń. */
function SpinOfDay({ spin }: { spin: SpinDetailData }) {
  // Pełna odpowiedź Dr. Spina obok posta: tej samej wysokości co post, przewijana po najechaniu; „Rozwiń” pokazuje całość.
  const [expanded, setExpanded] = useState(false);
  const sources = spin.claims.flatMap(claim => claim.sources.map(source => ({ ...source, label: claim.assessment_label, claim: claim.claim })));
  return (
    <div className="sc-clinic-sotd__body">
      <div className="sc-clinic-sotd__main">
        <div className="sc-clinic-sotd__post">
          <SpinAuthorRow author={spin.author} publishedAt={spin.post.published_at} size="lg" />
          <p className="sc-clinic-sotd__camp">{spin.camp_label}</p>
          <blockquote>{spin.post.text}</blockquote>
          <a href={spin.post.url} target="_blank" rel="noopener noreferrer">Post na X ↗</a>
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
            <button type="button" className="sc-clinic-sotd__toggle" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? "Zwiń diagnozę ↑" : "Rozwiń całą diagnozę ↓"}</button><ShareSpinOnX id={spin.id} spin={spin} /><Link href={`/klinika/${spin.id}`}>Pełna diagnoza →</Link></p>
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

function AccountsList({ collapsed }: { collapsed: boolean }) {
  const query = useQuery({ queryKey: ["clinic-accounts"], queryFn: getClinicAccounts, staleTime: 10 * 60_000 });
  const count = query.data?.results.length;
  const list = query.data && (
    <div className="sc-clinic-accounts__grid">{CAMPS.map(camp => (
      <section key={camp}>
        <h3>{CAMP_LABELS[camp]}</h3>
        <ul>{query.data.results.filter(item => item.camp === camp).map(item => (
          <li key={item.handle}>
            <PartyBadge party={item.party} />
            <span className="sc-clinic-accounts__who">
              {item.figure_id ? <Link href={`/osoby-publiczne/${item.figure_id}`}>{item.figure_name}</Link> : item.display_name}
              <a href={item.url} target="_blank" rel="noopener noreferrer">@{item.handle}</a>
            </span>
          </li>
        ))}</ul>
      </section>
    ))}</div>
  );
  const intro = <p>Tylko oficjalne konta polityków i partii: potwierdzone oficjalnym profilem albo otwartymi danymi i sprawdzone w X (nazwa zgodna z osobą, bez kont fanowskich i parodii). Obóz wynika z klubu lub frakcji.</p>;
  return collapsed ? (
    <details className="sc-clinic-accounts" id="konta">
      <summary>Z jakich kont czytamy{count ? ` — ${count} oficjalnych kont` : ""}</summary>
      {intro}{list}
    </details>
  ) : (
    <section className="sc-clinic-accounts" id="konta" aria-labelledby="clinic-accounts-title">
      <h2 id="clinic-accounts-title">Z jakich kont czytamy {count ? <span>{count}</span> : null}</h2>
      {intro}{list}
    </section>
  );
}

/** Klinika spinu. `embedded` — sekcja strony głównej (nagłówek h2, lista kont zwinięta). */
export function ClinicPage({ embedded = false }: { embedded?: boolean }) {
  const query = useQuery({ queryKey: ["clinic-page"], queryFn: getClinicPage, refetchInterval: 5 * 60_000 });
  const data = query.data;
  const Title = embedded ? "h2" : "h1";
  return (
    <section className="sc-clinic" id="spin" aria-labelledby="clinic-title" data-embedded={embedded || undefined}>
      <header className="sc-clinic-head">
        <p className="sc-clinic-kicker">Klinika spinu</p>
        <Title id="clinic-title">Diagnozy przekazów polityków</Title>
        <p className="sc-clinic-subtitle"><AiTag /> Treści w tej sekcji generuje AI. {data?.notice ?? ""} <Link href="/o-nas#klinika">Jak to działa</Link></p>
      </header>

      {query.isError && <p role="alert" className="sc-clinic-empty">Nie udało się pobrać Kliniki. <Button size="sm" variant="quiet" onClick={() => query.refetch()}>Ponów</Button></p>}
      {query.isLoading && <p className="sc-clinic-empty">Ładowanie diagnoz…</p>}

      {data && <>
        <div className="sc-clinic-top">
          <SpinScale scale={data.scale} />
          <div className="sc-clinic-split" aria-label="Przekazy dnia">
            {CAMPS.map(camp => <MessageBox key={camp} camp={camp} message={data.messages[camp]} />)}
          </div>
        </div>

        <section className="sc-clinic-sotd" aria-labelledby="sotd-title">
          <p className="sc-clinic-kicker">Spin dnia</p>
          {data.spin_of_day ? <SpinOfDay spin={data.spin_of_day} />
            : <p className="sc-clinic-empty" id="sotd-title">Spin dnia to diagnoza z najwyższą siłą spinu z ostatniej doby. Pojawi się po pierwszych diagnozach.</p>}
        </section>

        <section className="sc-clinic-latest" aria-labelledby="clinic-latest-title">
          <header className="sc-clinic-latest__head">
            <h3 id="clinic-latest-title">Najnowsze diagnozy</h3>
            <p>Rządzący i opozycja obok siebie — według tych samych zasad. Każdą diagnozę udostępnisz jako wątek na X.</p>
          </header>
          <div className="sc-clinic-columns">
            {CAMPS.map(camp => (
              <section key={camp} className="sc-clinic-column" aria-labelledby={`clinic-col-${camp}`}>
                <h4 id={`clinic-col-${camp}`} className="sc-clinic-column__title">{CAMP_LABELS[camp]}</h4>
                {data.columns[camp].length ? (
                  <div className="sc-clinic-column__list" tabIndex={0} aria-label={`Diagnozy: ${CAMP_LABELS[camp]} — przewijaj`}>
                    {data.columns[camp].map(spin => <SpinRow key={spin.id} spin={spin} />)}
                  </div>
                ) : <p className="sc-clinic-empty">Pierwsze diagnozy pojawią się, gdy strażnik znajdzie posty warte sprawdzenia.</p>}
              </section>
            ))}
          </div>
        </section>

        <aside className="sc-clinic-journalists" aria-labelledby="journalists-title">
          <div>
            <p className="sc-clinic-kicker">Dla dziennikarzy</p>
            <h3 id="journalists-title">Prowadzisz temat? Poprowadź tu autoryzowaną nitkę.</h3>
            <p>
              Dr. Spin pokazuje, jak zbudowany jest przekaz. Ty wiesz, co wydarzyło się naprawdę. Zapraszamy dziennikarzy do prowadzenia nitek
              kontekstowych pod własnym nazwiskiem: materiał otwierający, a za nim dokumenty, wypowiedzi i źródła — z Twoim podpisem i linkiem do redakcji.
            </p>
          </div>
          <a className="sc-onas-mail sc-clinic-journalists__cta" href={`mailto:${CONTACT}?subject=${encodeURIComponent("Autoryzowana nitka w spin.clinic")}`}>Napisz: {CONTACT}</a>
        </aside>

        <p className="sc-clinic-roadmap">
          Dziś diagnoza to tekst ze źródłami z wyszukiwania. W miarę rozbudowy naszej bazy dowodami będą boxy z materiałami źródłowymi.
        </p>
        <AccountsList collapsed={embedded} />
      </>}
    </section>
  );
}
