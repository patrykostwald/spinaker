"use client";

import type { ReactNode } from "react";
import { agreementLabel, techniqueLabel, type SpinDetailData } from "../../lib/clinic";
import { STRENGTH_BANDS, diagnosisPresentation, plainClaimsSentence, strengthWord } from "../../lib/diagnosisPresentation";
import { Term } from "../../kit/Term";
import { FORMS, plural } from "../../lib/plural";
import { formatDatePl } from "../../lib/utils";
import { VerdictTag } from "./SpinParts";

// Krótkie nazwy członków Konsylium — pełna nazwa modelu (np. „speakleash/Bielik-11B-v3.0-Instruct:publicai”) rozpychała kartę.
const MODEL_LABELS: [RegExp, string][] = [[/gpt/i, "GPT"], [/qwen/i, "Qwen"], [/gemini/i, "Gemini"], [/gemma/i, "Gemma"], [/claude/i, "Claude"],
  [/nemotron/i, "Nemotron"], [/bielik/i, "Bielik"], [/pllum/i, "PLLuM"], [/llama/i, "Llama"], [/mistral|mixtral/i, "Mistral"], [/deepseek/i, "DeepSeek"],
  [/kimi/i, "Kimi"], [/glm/i, "GLM"], [/granite/i, "Granite"], [/jamba/i, "Jamba"], [/phi/i, "Phi"]];
const modelLabel = (model = "") => MODEL_LABELS.find(([pattern]) => pattern.test(model))?.[1]
  ?? (model.split("/").pop() || model).split(":")[0].slice(0, 14);
const VOTE_STATE: Record<string, string> = { spin: "spin", partial: "częściowy spin", no_spin: "bez spinu", unclear: "nie da się ocenić" };
const firstSentence = (text = "") => text.match(/^.*?[.!?](?=\s|$)/s)?.[0] ?? text;

export function ReportError({ spin }: { spin: SpinDetailData }) {
  return <a className="sc-scan-dg-report" href={`mailto:kontakt@spin.clinic?subject=${encodeURIComponent(`Zgłoszenie błędu w diagnozie ${spin.id}`)}`}>Zgłoś błąd</a>;
}

/** Wspólny wynik i panel liczb; źródło i akcje pozostają w komponencie osadzającym. */
export function SpinSummary({ spin, heading: Heading = "h3", compact = false, withPoint = true, withReport = false, withTable = !compact, actions }: { spin: SpinDetailData; heading?: "h1" | "h2" | "h3"; compact?: boolean; withPoint?: boolean; withReport?: boolean; withTable?: boolean; actions?: ReactNode }) {
  const scan = spin.scan;
  const lead = Heading === "h1" ? spin.headline : scan?.synthesis?.lead || spin.headline;
  const point = scan?.synthesis?.points?.[0] || firstSentence(spin.summary);
  const { families, typeCount, familyMax, claims, checked, claimSquares, council } = diagnosisPresentation(spin);
  const { votes, agreement } = council;
  return <div className="sc-spin-summary" data-compact={compact || undefined}>
      <header className="sc-scan-dg-head"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><span className="sc-scan-dg-ai">{votes.length ? "Ocena Konsylium AI" : "Analiza AI"}</span><span className="sc-scan-dg-id">#SPIN-{spin.id} · diagnoza {formatDatePl(scan?.diagnosed_at || spin.created_at)}</span>{withReport ? <ReportError spin={spin} /> : null}</header>
      <Heading className="sc-scan-dg-lead" id={`scan-lead-${spin.id}`}>{lead}</Heading>
      {actions ? <div className="sc-scan-dg-actions">{actions}</div> : null}
      {withPoint ? <p className="sc-scan-dg-point">{point}</p> : null}
      {!compact ? <p className="sc-scan-plain">{spin.verdict === "unclear"
        ? <>Konsylium nie rozstrzygnęło oceny, więc liczba poniżej jest tylko orientacyjna. {plainClaimsSentence(claims)}</>
        : <><strong><Term id="sila-spinu">Siła spinu</Term>: {strengthWord(spin.intensity)}.</strong> {plainClaimsSentence(claims)}</>}
        <small className="sc-scan-plain__note">Werdykt (np. „{spin.verdict_label}”) opisuje rodzaj przekazu, a siła spinu mówi, jak mocny jest spin: {STRENGTH_BANDS}. Obie oceny pochodzą z tej samej analizy AI.</small></p> : null}
      <div className="sc-scan-m">
        <div className="sc-scan-m-col sc-scan-m-col--strength"><p className="sc-scan-m-lbl">Siła spinu</p><p className="sc-scan-m-num sc-scan-strength">{spin.intensity}<small>/100</small></p>
          <div className="sc-scan-g" title="Ocena AI w skali 0–100"><span className="sc-scan-g-track"><i style={{ width: `${Math.max(0, Math.min(100, spin.intensity))}%` }} /></span><span className="sc-scan-g-scale"><b>0</b><b>50</b><b>100</b></span></div></div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Konsylium AI</p><p className="sc-scan-m-num" title={agreementLabel(agreement)}>{agreement && /\d/.test(agreement) ? agreement : "—"}<small className="sc-scan-agreement-caption">z odpowiadających modeli zgodnych z wynikiem</small></p>
          {!compact ? <div className="sc-scan-g sc-scan-council" title={scan?.council?.method || "Oceny modeli w skali 0–100; kropka — werdykt modelu"}>{!votes.length ? <span>Brak zapisanych głosów modeli</span> : null}{votes.length ? <small className="sc-scan-council__tally"><span>Skład: {votes.length} {plural(votes.length, FORMS.model)}</span><span>odpowiedziało {council.responses.length}</span><span>zgodnych z wynikiem {council.sameVerdict}</span>{council.missing.length ? <span>bez odpowiedzi {council.missing.length}</span> : null}</small> : null}{votes.map((vote, index) => (
            <span key={index} className="sc-scan-g-row">{vote.missing ? <span className="sc-scan-vote-missing">{modelLabel(vote.model)} — Brak odpowiedzi</span> : <><em title={vote.model}>{modelLabel(vote.model)}</em><span className="sc-scan-g-track sc-scan-g-thin" data-missing={vote.intensity == null || undefined} title={vote.intensity == null ? "Brak oceny siły" : undefined}><i style={{ width: `${Math.max(0, Math.min(100, vote.intensity ?? 0))}%` }} /></span><b>{vote.intensity ?? "—"}</b><u role="img" data-verdict={vote.verdict} aria-label={`${modelLabel(vote.model)}: ${VOTE_STATE[vote.verdict ?? ""] ?? "brak oceny"}${vote.intensity == null ? "" : `, ${vote.intensity}`}`} title={`werdykt modelu: ${VOTE_STATE[vote.verdict ?? ""] ?? "brak"}`} /></>}</span>))}</div> : null}{!compact && votes.some(vote => !vote.missing) ? <p className="sc-scan-vote-legend"><span>Znaczek = werdykt modelu:</span> <span><u aria-hidden="true" data-verdict="spin" /> spin</span> <span><u aria-hidden="true" data-verdict="partial" /> częściowy spin</span> <span><u aria-hidden="true" data-verdict="no_spin" /> bez spinu</span> <span><u aria-hidden="true" /> nie da się ocenić</span></p> : null}{compact && council.missing.length ? <p className="sc-scan-vote-note">Brak odpowiedzi: {council.missing.length}</p> : null}</div>
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
