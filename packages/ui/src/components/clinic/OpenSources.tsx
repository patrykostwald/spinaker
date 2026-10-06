import type { FactCheck, SourceArchive } from "../../lib/clinic";
import { formatDateTimePl } from "../../lib/utils";

/** Raport źródeł 6.10: kopia cytowanego artykułu w Wayback Machine; po cichej edycji - etykieta i porównanie wersji.
 *  Etykieta stanu mała, po prawej od linku źródła (zasada 7); jedno wyróżnienie na wiersz (Von Restorff). */
export function ArchiveNote({ archive }: { archive?: SourceArchive }) {
  if (!archive?.archive_url) return null;
  return <span className="sc-archive-note">
    <a href={archive.archive_url} target="_blank" rel="noopener noreferrer">kopia z dnia cytowania ↗</a>
    {archive.changed_at ? <>
      <span className="sc-archive-note__changed" title={`Zmieniony ${formatDateTimePl(archive.changed_at)}`}>zmieniony po cytowaniu</span>
      {archive.compare_url ? <a href={archive.compare_url} target="_blank" rel="noopener noreferrer">porównaj wersje ↗</a> : null}
    </> : null}
  </span>;
}

/** „Tę tezę sprawdzili”: weryfikacje tej samej tezy przez redakcje fact-checkingowe (Google Fact Check API).
 *  Równe karty w rzędzie: wydawca i werdykt u góry, teza w środku, link na dole (grid auto 1fr auto). */
export function FactChecks({ id, items }: { id: number; items?: FactCheck[] }) {
  if (!items?.length) return null;
  return <section className="sc-spin-detail__section sc-factchecks" id={`spin-${id}-sprawdzili`} aria-labelledby={`spin-${id}-sprawdzili-title`}>
    <h2 id={`spin-${id}-sprawdzili-title`}>Tę tezę sprawdzili</h2>
    <p className="sc-spin-detail__intro">Weryfikacje podobnej tezy przez redakcje fact-checkingowe. Ich werdykt nie zmienia diagnozy Dr. Spina.</p>
    <ul className="sc-factchecks__list">{items.map(item => <li key={item.url} className="sc-factchecks__card">
      <p className="sc-factchecks__head"><b>{item.publisher || "Redakcja"}</b>{item.rating ? <span>{item.rating}</span> : null}</p>
      <p className="sc-factchecks__claim">{item.reviewed_claim || item.title}</p>
      <a href={item.url} target="_blank" rel="noopener noreferrer">Przeczytaj weryfikację ↗</a>
    </li>)}</ul>
    <p className="sc-spin-detail__intro sc-factchecks__src">Źródło: Google Fact Check Tools (ClaimReview).</p>
  </section>;
}
