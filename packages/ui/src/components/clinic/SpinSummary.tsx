"use client";

import { agreementLabel, techniqueLabel, type SpinDetailData } from "../../lib/clinic";
import { diagnosisPresentation } from "../../lib/diagnosisPresentation";
import { formatDatePl } from "../../lib/utils";
import { VerdictTag } from "./SpinParts";

const modelLabel = (model = "") => /gpt/i.test(model) ? "GPT" : /qwen/i.test(model) ? "Qwen" : /gemini/i.test(model) ? "Gemini" : /claude/i.test(model) ? "Claude" : /nemotron/i.test(model) ? "Nemotron" : model;
const firstSentence = (text = "") => text.match(/^.*?[.!?](?=\s|$)/s)?.[0] ?? text;

export function ReportError({ spin }: { spin: SpinDetailData }) {
  return <a className="sc-scan-dg-report" href={`mailto:kontakt@spin.clinic?subject=${encodeURIComponent(`Zgłoszenie błędu w diagnozie ${spin.id}`)}`}>Zgłoś błąd</a>;
}

/** Wspólny wynik i panel liczb; źródło i akcje pozostają w komponencie osadzającym. */
export function SpinSummary({ spin, heading: Heading = "h3", compact = false, withPoint = true, withReport = false, withTable = !compact }: { spin: SpinDetailData; heading?: "h1" | "h2" | "h3"; compact?: boolean; withPoint?: boolean; withReport?: boolean; withTable?: boolean }) {
  const scan = spin.scan;
  const lead = Heading === "h1" ? spin.headline : scan?.synthesis?.lead || spin.headline;
  const point = scan?.synthesis?.points?.[0] || firstSentence(spin.summary);
  const { families, typeCount, familyMax, claims, checked, claimSquares, council } = diagnosisPresentation(spin);
  const { votes, agreement } = council;
  return <div className="sc-spin-summary" data-compact={compact || undefined}>
      <header className="sc-scan-dg-head"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><span className="sc-scan-dg-ai">Ocena Konsylium AI</span><span className="sc-scan-dg-id">#SPIN-{spin.id} · diagnoza {formatDatePl(scan?.diagnosed_at || spin.created_at)}</span>{withReport ? <ReportError spin={spin} /> : null}</header>
      <Heading className="sc-scan-dg-lead" id={`scan-lead-${spin.id}`}>{lead}</Heading>
      {withPoint ? <p className="sc-scan-dg-point">{point}</p> : null}
      <div className="sc-scan-m">
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Siła spinu</p><p className="sc-scan-m-num sc-scan-strength">{spin.intensity}<small>/100</small></p>
          <div className="sc-scan-g" title="Ocena AI w skali 0–100"><span className="sc-scan-g-track"><i style={{ width: `${Math.max(0, Math.min(100, spin.intensity))}%` }} /></span><span className="sc-scan-g-scale"><b>0</b><b>50</b><b>100</b></span></div></div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Konsylium AI</p><p className="sc-scan-m-num" title={agreementLabel(agreement)}>{agreement && /\d/.test(agreement) ? agreement : "—"}<small className="sc-scan-agreement-caption">ten sam werdykt</small></p>
          {!compact ? <div className="sc-scan-g sc-scan-council" title={scan?.council?.method || "Oceny modeli w skali 0–100; kropka — werdykt modelu"}>{!votes.length ? <span>Brak danych o składzie</span> : null}{votes.map((vote, index) => (
            <span key={index} className="sc-scan-g-row">{vote.missing ? <span className="sc-scan-vote-missing">{modelLabel(vote.model)} — Brak odpowiedzi</span> : <><em title={vote.model}>{modelLabel(vote.model)}</em><span className="sc-scan-g-track sc-scan-g-thin" data-missing={vote.intensity == null || undefined} title={vote.intensity == null ? "Brak oceny siły" : undefined}><i style={{ width: `${Math.max(0, Math.min(100, vote.intensity ?? 0))}%` }} /></span><b>{vote.intensity ?? "—"}</b><u data-verdict={vote.verdict} title={`werdykt: ${vote.verdict ?? "brak"}`} /></>}</span>))}</div> : null}{council.missing.length ? <p className="sc-scan-vote-note">Brak odpowiedzi: {council.missing.length}</p> : null}</div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl" title="Liczymy zapisane pozycje analizy, bez scalania podobnych twierdzeń">Twierdzenia</p><p className="sc-scan-m-num">{checked}<small> sprawdzone</small></p>
          <div className="sc-scan-g"><span className="sc-scan-g-squares" aria-hidden="true">{claimSquares.map((kind, index) => <i key={index} data-k={kind} data-gap={index === claimSquares.indexOf("op") || undefined} />)}</span>
            <span className="sc-scan-g-legend">{claims.map(claim => claim.count ? <span key={claim.key} data-k={claim.kind}>{claim.count} {claim.label}</span> : null)}</span></div></div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Techniki</p><p className="sc-scan-m-num">{typeCount}<small> {techniqueLabel(typeCount)}</small></p>
          <div className="sc-scan-g">{families.map(({ key, label, count }) => (
            <span key={key} className="sc-scan-g-row sc-scan-g-fam" data-family={key}><em>{label.split(" ")[0]}</em><span className="sc-scan-g-track sc-scan-g-thin"><i style={{ width: `${(count / familyMax) * 100}%` }} /></span><b>{count}</b></span>))}</div></div>
      </div>
      {withTable ? <table className="sc-scan-t"><thead><tr><th>Rodzina technik</th><th>Techniki w analizowanym materiale</th><th className="sc-scan-t-n">Typy</th></tr></thead><tbody>
        {families.map(({ key, label, count, types }) => <tr key={key} data-family={key}><th scope="row"><i />{label}</th><td>{types.map(item => item.label).join(" · ") || <span className="sc-scan-t-none">Nie wskazano</span>}</td><td className="sc-scan-t-n">{count}</td></tr>)}
      </tbody></table> : null}
  </div>;
}
