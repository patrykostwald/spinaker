"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import {
  nb, pairAriaLabel, pairDate, pairDateShort, quoteNeedsToggle, sourceDomain, safeSourceHref,
  POSITION_CONNECTOR_LABEL, POSITION_PAIRS_ANCHOR, POSITION_PAIRS_COMPLETENESS, POSITION_PAIRS_NOTICE, POSITION_PAIRS_PAUSED, POSITION_PAIRS_TITLE,
  type PositionPairData, type PositionPairsBlock, type PositionSide,
} from "../lib/positionPairs";
import { PositionPairReport } from "./PositionPairReport";
import "./position-pair.css";

/**
 * „Wcześniej i teraz” - spinka dwóch wypowiedzi tej samej osoby o tym samym temacie (zlecenie właściciela 13.10.2026).
 *
 * Neutralna: pokazuje dane i nie ocenia, wnioski należą do czytelnika. TA SAMA MIARA DLA KAŻDEJ STRONY, ZAWSZE: żadnej
 * gałęzi zależnej od osoby, partii ani treści; bez kolorów ostrzegawczych, słów oceniających, licznika i rankingu.
 *  - A (starsza) po lewej, na wąskim kontenerze u góry; B (nowsza) po prawej; kolejność czytania A, potem B.
 *  - Oba boksy mają jedną wysokość (subgrid): nagłówek | cytat | przełącznik | nazwa źródła | odnośnik na wspólnych liniach.
 *  - Cytat dosłowny w budżecie 5 linii i "Pokaż całość" (bez pasków przewijania); treść zawsze w DOM.
 *  - Źródło: nazwa i odnośnik (domena + ↗, cel 44 px); pod parą kontekst jednym zdaniem i "Zgłoś błąd lub sprostowanie".
 * Dane: kontrakt API-v3.md sekcja 5 (lib/positionPairs.ts). Na produkcji tylko pary zatwierdzone przez człowieka, za flagą.
 */
export type PositionPairProps = {
  pair: PositionPairData;
  /** poziom nagłówka z tematem pary */
  as?: "h2" | "h3" | "h4";
  /** etykiety ról; w spince "Boks 3" / "Boks 4" zamiast "Wcześniej" / "Teraz" (kolejność autora nie jest chronologią) */
  labels?: [string, string];
  /** słowo na łączniku (domyślnie "inaczej niż") */
  connector?: string;
  /** zdanie nad parą; false = bez (lista pokazuje je raz) */
  notice?: string | false;
  /** przycisk "Zgłoś błąd lub sprostowanie" (domyślnie tak) */
  reportable?: boolean;
  /** dodatkowa linia meta: kto zatwierdził */
  showApproval?: boolean;
  /** nagłówek z tematem (domyślnie tak; w spince temat jest opisem połączenia w karcie obok) */
  showTopic?: boolean;
  /** tekst w cudzysłowie typograficznym (cytat dosłowny); false dla zestawień z boksów spinki (tytuły i opisy, nie cytaty) */
  quotes?: boolean;
  id?: string;
};

function Side({ side, which, role, domId, quotes }: { side: PositionSide; which: "a" | "b"; role: string; domId: string; quotes: boolean }) {
  const text = side.quote ?? side.vote_subject;
  const isQuote = side.quote != null && quotes;
  const ref = useRef<HTMLParagraphElement>(null);
  const [open, setOpen] = useState(false);
  // przed pomiarem (serwer, pierwszy render) szacunek po długości; po montażu dokładny pomiar zawartości względem budżetu linii
  const [needs, setNeeds] = useState(() => quoteNeedsToggle(side));
  useEffect(() => {
    const el = ref.current;
    if (!el || open) return;
    const measure = () => setNeeds(el.scrollHeight > el.clientHeight + 1);
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [open, text]);
  const domain = sourceDomain(side.source.url);
  const href = safeSourceHref(side.source.url);
  return <article className="sc-pp__box" data-side={which} data-kind={side.kind} aria-labelledby={`${domId}-h`}>
    <header className="sc-pp__h" id={`${domId}-h`}>
      <span className="sc-pp__role">{role}</span>
      <time className="sc-pp__date" dateTime={side.date}>{pairDate(side.date)}</time>
      <span className="sc-pp__kind">{side.kind_label}</span>
    </header>
    <div className="sc-pp__q">
      {side.vote && <p className="sc-pp__vote">Głos: <b>{side.vote}</b></p>}
      {text && <blockquote className="sc-pp__bq" cite={href ?? undefined} lang="pl">
        <p ref={ref} id={`${domId}-q`} className="sc-pp__txt" data-quote={isQuote || undefined} data-subject={side.quote == null || undefined} data-open={open || undefined}>{text}</p>
      </blockquote>}
    </div>
    <div className="sc-pp__t">
      {(needs || open) && text && <button type="button" className="sc-pp__tg" aria-expanded={open} aria-controls={`${domId}-q`} onClick={() => setOpen(value => !value)}>
        {open ? "Zwiń" : "Pokaż całość"}<span className="sc-pp-sr"> {isQuote ? "cytatu" : "treści"}: {role}</span></button>}
    </div>
    <p className="sc-pp__sn" title={side.source.name}>Źródło: {side.source.name}</p>
    <p className="sc-pp__sl">
      {href && <a href={href} target={href.startsWith("/") ? undefined : "_blank"} rel="noopener noreferrer">{domain}<i aria-hidden="true">↗</i>
        <span className="sc-pp-sr"> (źródło: {role.toLowerCase()}{href.startsWith("/") ? "" : ", otwiera się w nowym oknie"})</span></a>}
      {side.source.fetched_at && <span>pobrano {pairDateShort(side.source.fetched_at)}</span>}
    </p>
  </article>;
}

export function PositionPair({ pair, as: Heading = "h3", labels = ["Wcześniej", "Teraz"], connector = POSITION_CONNECTOR_LABEL, notice = POSITION_PAIRS_NOTICE, reportable = true, showApproval = true, quotes = true, showTopic = true, id }: PositionPairProps) {
  const uid = useId().replace(/:/g, "");
  const base = `pp-${pair.id}-${uid}`;
  return <section className="sc-pp" id={id} role="group" aria-label={pairAriaLabel(pair, labels)} data-pair={pair.id}>
    {showTopic && <Heading className="sc-pp__topic"><small>Temat</small>{nb(pair.topic)}</Heading>}
    {notice !== false && <p className="sc-pp__lead">{nb(notice)}</p>}
    <div className="sc-pp__grid">
      <Side side={pair.a} which="a" role={labels[0]} domId={`${base}-a`} quotes={quotes} />
      <div className="sc-pp__link">
        <span className="sc-pp__lw">{nb(connector)}</span>
        <i className="sc-pp__ln" aria-hidden="true" />
      </div>
      <Side side={pair.b} which="b" role={labels[1]} domId={`${base}-b`} quotes={quotes} />
    </div>
    {pair.context && <p className="sc-pp__ctx"><b>Kontekst:</b> {nb(pair.context)}</p>}
    <div className="sc-pp__foot">
      {showApproval && pair.approved_at
        ? <p className="sc-pp__meta">{pair.ai_suggested ? "Zestawienie zaproponowała AI, zatwierdził człowiek" : "Zestawienie zatwierdził człowiek"}, {pairDateShort(pair.approved_at)}.</p>
        : <span />}
      {reportable && <PositionPairReport pair={pair} />}
    </div>
  </section>;
}

/**
 * Sekcja z listą par: nagłówek "Wcześniej i teraz", jedno zdanie nad listą, pary jedna pod drugą (kolejność z API: najnowsza
 * druga wypowiedź pierwsza; bez rankingu), zdanie o kompletności pod listą. `paused` (cisza wyborcza) = tylko informacja.
 */
export function PositionPairs({ block, as: Heading = "h2", headingId, id = POSITION_PAIRS_ANCHOR }: {
  block: Pick<PositionPairsBlock, "items" | "notice" | "paused">;
  as?: "h2" | "h3";
  headingId?: string;
  id?: string;
}) {
  const uid = useId().replace(/:/g, "");
  const hid = headingId ?? `pp-list-${uid}`;
  if (block.paused) {
    return <section className="sc-pp-list" id={id} aria-labelledby={hid}>
      <Heading id={hid} className="sc-pp-list__h">{POSITION_PAIRS_TITLE}</Heading>
      <p className="sc-pp-list__lead">{nb(POSITION_PAIRS_PAUSED)}</p>
    </section>;
  }
  if (!block.items.length) return null;
  return <section className="sc-pp-list" id={id} aria-labelledby={hid}>
    <Heading id={hid} className="sc-pp-list__h">{POSITION_PAIRS_TITLE}</Heading>
    <p className="sc-pp-list__lead">{nb(block.notice || POSITION_PAIRS_NOTICE)}</p>
    <ol className="sc-pp-list__items">
      {block.items.map(pair => <li key={pair.id} id={`stanowiska-${pair.id}`}>
        <PositionPair pair={pair} as={Heading === "h2" ? "h3" : "h4"} notice={false} />
      </li>)}
    </ol>
    <p className="sc-pp-list__note">{nb(POSITION_PAIRS_COMPLETENESS)}</p>
  </section>;
}

/** Jedna linia w karcie diagnozy: tylko gdy para istnieje (ta sama reguła dla każdej diagnozy). */
export function PositionPairsNote({ pairs, person, detailHref }: {
  pairs: Array<Pick<PositionPairData, "id" | "topic">>;
  person?: string | number | null;
  detailHref: (id: number, person?: string | number | null) => string;
}) {
  if (!pairs.length) return null;
  return <div className="sc-pp-notes">
    {pairs.slice(0, 3).map(pair => <p key={pair.id} className="sc-pp-note">
      <span>{nb("Ta osoba wypowiadała się wcześniej na ten temat:")}</span>{" "}
      <Link href={detailHref(pair.id, person)}>zobacz obok siebie<span className="sc-pp-sr"> (temat: {pair.topic})</span></Link>
    </p>)}
  </div>;
}
