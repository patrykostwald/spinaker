import { PositionPairReply } from "../../kit/PositionPairReply";
import Link from "next/link";
import { ClinicNav } from "./ClinicNav";
import { PositionPair } from "../../kit/PositionPair";
import {
  nb, personPairsHref, POSITION_PAIRS_COMPLETENESS, POSITION_PAIRS_NOTICE, POSITION_PAIRS_PAUSED, POSITION_PAIRS_TITLE,
  type PositionPairData, type PositionPairPerson,
} from "../../lib/positionPairs";

/**
 * Strona jednej pary /klinika/stanowiska/<id> (spin.clinic): nagłówek, para obok siebie, kontekst, zgłoszenie błędu i powrót
 * do profilu. Komponent serwerowy (bez haków); PositionPair sam jest kliencki. Neutralna: bez ocen, liczników i rankingów.
 */
export function PositionPairPage({ pair, person, paused = false }: { pair: PositionPairData | null; person: PositionPairPerson | null; paused?: boolean }) {
  const back = person?.slug || person?.id ? personPairsHref(person.slug || person.id, pair?.id) : null;
  return <div className="sc-v3 sc-v3-page sc-v3-pp-page">
    <ClinicNav />
    <p className="sc-v3-ctx">
      {back && <Link className="sc-v3-crumb" href={back}>← Profil osoby: {person?.name}</Link>}
    </p>
    <h1 className="sc-v3-dg-title">{POSITION_PAIRS_TITLE}{person ? <small style={{ display: "block", marginTop: 8, font: "500 17px/1.4 var(--sc-font-sans)", color: "var(--sc-text-2)" }}>{person.name}</small> : null}</h1>
    {paused || !pair
      ? <p className="sc-pp-list__lead">{nb(paused ? POSITION_PAIRS_PAUSED : "Nie znaleziono tego zestawienia. Mogło zostać wycofane do ponownej oceny.")}</p>
      : <><PositionPair pair={pair} as="h2" notice={pair.notice || POSITION_PAIRS_NOTICE} /><p className="sc-pp__replyrow"><PositionPairReply pair={pair} /></p></>}
    <p className="sc-pp-list__note">{nb(POSITION_PAIRS_COMPLETENESS)}</p>
  </div>;
}
