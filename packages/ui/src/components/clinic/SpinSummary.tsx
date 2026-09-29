"use client";

import { agreementLabel, techniqueLabel, type SpinDetailData } from "../../lib/clinic";
import { FAMILY_OF } from "../../lib/techniqueFamilies";
import { formatDatePl } from "../../lib/utils";
import { VerdictTag } from "./SpinParts";

const FAMILIES = [
  ["dane", "Dane i wnioskowanie"],
  ["przedstawienie", "Emocje i przedstawienie"],
  ["spor", "Spór i odpowiedzialność"],
] as const;
const modelLabel = (model = "") => /gpt/i.test(model) ? "GPT" : /qwen/i.test(model) ? "Qwen" : /gemini/i.test(model) ? "Gemini" : /claude/i.test(model) ? "Claude" : /nemotron/i.test(model) ? "Nemotron" : model;
const opinionsLabel = (n: number) => n === 1 ? "opinia" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? "opinie" : "opinii";
const firstSentence = (text = "") => text.match(/^.*?[.!?](?=\s|$)/s)?.[0] ?? text;

export function ReportError({ spin }: { spin: SpinDetailData }) {
  return <a className="sc-scan-dg-report" href={`mailto:kontakt@spin.clinic?subject=${encodeURIComponent(`Zgłoszenie błędu w diagnozie ${spin.id}`)}`}>Zgłoś błąd</a>;
}

/** Wspólny wynik i panel liczb; źródło i akcje pozostają w komponencie osadzającym. */
export function SpinSummary({ spin, heading: Heading = "h3" }: { spin: SpinDetailData; heading?: "h1" | "h2" | "h3" }) {
  const scan = spin.scan;
  const lead = scan?.synthesis?.lead || spin.headline;
  const point = scan?.synthesis?.points?.[0] || firstSentence(spin.summary);
  const votes = scan?.council?.votes ?? spin.council?.members ?? [];
  const agreement = scan?.council?.verdict_agreement ?? (votes.length ? `${votes.filter(vote => vote.verdict === spin.verdict).length}/${votes.length}` : "—");
  const claims = spin.claims ?? [];
  // Older scan aggregates infer opinions from missing sources. Count explicit assessments instead.
  const opinions = claims.filter(claim => claim.assessment === "opinion").length;
  const unverified = claims.filter(claim => claim.assessment === "unverified").length;
  // Techniki z rodziną: z pola scan, a dla starszych odpowiedzi — kategoria z diagnozy i słownik rodzin.
  const techniques = (scan?.techniques ?? (spin.techniques ?? []).map(item => ({ ...item, name: item.category || item.name, family: FAMILY_OF[item.category || item.name] ?? "inne" })))
    .filter((item, index, list) => list.findIndex(other => other.name === item.name) === index);
  const familyCount = (key: string) => scan?.families?.[key]?.technique_types ?? techniques.filter(item => item.family === key).length;
  const typeCount = techniques.length;
  const familyMax = Math.max(1, ...FAMILIES.map(([key]) => familyCount(key)));
  const claimCount = (key: "supported" | "misleading" | "contradicted") => claims.filter(claim => claim.assessment === key).length;
  const [supported, misleading, contradicted] = [claimCount("supported"), claimCount("misleading"), claimCount("contradicted")];
  const checked = supported + misleading + contradicted;
  const claimSquares = [...Array(supported).fill("ok"), ...Array(misleading).fill("mid"), ...Array(contradicted).fill("bad"), ...Array(unverified).fill("unverified"), ...Array(opinions).fill("op")] as string[];
  return <div className="sc-spin-summary">
      <header className="sc-scan-dg-head"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><span className="sc-scan-dg-ai">Ocena Konsylium AI</span><span className="sc-scan-dg-id">#SPIN-{spin.id} · diagnoza {formatDatePl(scan?.diagnosed_at || spin.created_at)}</span></header>
      <Heading className="sc-scan-dg-lead" id={`scan-lead-${spin.id}`}>{lead}</Heading>
      <p className="sc-scan-dg-point">{point}</p>
      <div className="sc-scan-m">
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Siła spinu</p><p className="sc-scan-m-num sc-scan-strength">{spin.intensity}<small>/100</small></p>
          <div className="sc-scan-g" title="Ocena AI w skali 0–100"><span className="sc-scan-g-track"><i style={{ width: `${Math.max(0, Math.min(100, spin.intensity))}%` }} /></span><span className="sc-scan-g-scale"><b>0</b><b>50</b><b>100</b></span></div></div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Konsylium AI</p><p className="sc-scan-m-num" title={agreementLabel(agreement)}>{agreement && /\d/.test(agreement) ? agreement : "—"}<small> zgodne</small></p>
          <div className="sc-scan-g sc-scan-council" title={scan?.council?.method || "Oceny modeli w skali 0–100; kropka — werdykt modelu"}>{!votes.length ? <span>Brak danych o składzie</span> : null}{votes.map((vote, index) => (
            <span key={index} className="sc-scan-g-row">{vote.intensity == null || !vote.verdict ? <span className="sc-scan-vote-missing">{modelLabel(vote.model)} — Brak odpowiedzi</span> : <><em title={vote.model}>{modelLabel(vote.model)}</em><span className="sc-scan-g-track sc-scan-g-thin"><i style={{ width: `${Math.max(0, Math.min(100, vote.intensity))}%` }} /></span><b>{vote.intensity}</b><u data-verdict={vote.verdict} title={`werdykt: ${vote.verdict ?? "brak"}`} /></>}</span>))}</div></div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Twierdzenia</p><p className="sc-scan-m-num">{checked}<small> sprawdzone</small></p>
          <div className="sc-scan-g"><span className="sc-scan-g-squares" aria-hidden="true">{claimSquares.map((kind, index) => <i key={index} data-k={kind} data-gap={index === claimSquares.indexOf("op") || undefined} />)}</span>
            <span className="sc-scan-g-legend">{supported ? <span data-k="ok">{supported} potw.</span> : null}{misleading ? <span data-k="mid">{misleading} mylące</span> : null}{contradicted ? <span data-k="bad">{contradicted} sprzeczne</span> : null}{unverified ? <span data-k="unverified">{unverified} niesprawdzone</span> : null}{opinions ? <span data-k="op">{opinions} {opinionsLabel(opinions)}</span> : null}</span></div></div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Techniki</p><p className="sc-scan-m-num">{typeCount}<small> {techniqueLabel(typeCount)}</small></p>
          <div className="sc-scan-g">{FAMILIES.map(([key, label]) => (
            <span key={key} className="sc-scan-g-row sc-scan-g-fam" data-family={key}><em>{label.split(" ")[0]}</em><span className="sc-scan-g-track sc-scan-g-thin"><i style={{ width: `${(familyCount(key) / familyMax) * 100}%` }} /></span><b>{familyCount(key)}</b></span>))}</div></div>
      </div>
      <table className="sc-scan-t"><thead><tr><th>Rodzina technik</th><th>Techniki w analizowanym materiale</th><th className="sc-scan-t-n">Typy</th></tr></thead><tbody>
        {FAMILIES.map(([key, label]) => <tr key={key} data-family={key}><th scope="row"><i />{label}</th><td>{techniques.filter(item => item.family === key).map(item => item.name).join(" · ") || <span className="sc-scan-t-none">Nie wskazano</span>}</td><td className="sc-scan-t-n">{familyCount(key)}</td></tr>)}
      </tbody></table>
  </div>;
}
