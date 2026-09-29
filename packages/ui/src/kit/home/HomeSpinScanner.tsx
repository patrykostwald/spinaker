"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { SpinDetailData } from "../../lib/clinic";
import { formatDatePl, formatDateTimePl } from "../../lib/utils";
import { SpinAvatar, VerdictTag } from "../../components/clinic/SpinParts";

const FAMILIES = [
  ["dane", "Dane i wnioskowanie"],
  ["przedstawienie", "Emocje i przedstawienie"],
  ["spor", "Spór i odpowiedzialność"],
] as const;
/** Rodzina każdej kategorii techniki (jak backend/news/techniques.py) — gdy odpowiedź API nie ma jeszcze pola scan. */
const FAMILY_OF: Record<string, string> = {
  "Liczba bez punktu odniesienia": "dane", "Wybiórcze dane": "dane", "Pominięcie kontekstu": "dane", "Przeinaczenie faktów": "dane",
  "Teza bez dowodu": "dane", "Fałszywa przyczynowość": "dane", "Nadmierne uogólnienie": "dane", "Fałszywa analogia i skojarzenie": "dane",
  "Fałszywa alternatywa": "dane", "Odwołanie do autorytetu": "dane",
  "Apel do emocji": "przedstawienie", "Straszenie": "przedstawienie", "Przesada": "przedstawienie", "Etykietowanie": "przedstawienie",
  "My kontra oni": "przedstawienie", "Sugestia i niedopowiedzenie": "przedstawienie",
  "Atak na osobę": "spor", "Przypisywanie intencji": "spor", "Słomiany człowiek": "spor", "Zmiana tematu": "spor", "Przypisywanie sobie zasług": "spor",
};
const modelLabel = (model = "") => /gpt/i.test(model) ? "GPT" : /qwen/i.test(model) ? "Qwen" : /gemini/i.test(model) ? "Gemini" : /claude/i.test(model) ? "Claude" : /nemotron/i.test(model) ? "Nemotron" : model;
const opinionsLabel = (n: number) => n === 1 ? "opinia" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? "opinie" : "opinii";
const firstSentence = (text = "") => text.match(/^.*?[.!?](?=\s|$)/s)?.[0] ?? text;
const characterCount = (text: string) => Array.from(text.replace(/https?:\/\/[^\s]+/g, "x".repeat(23))).length;
function domain(url: string) {
  try { const parsed = new URL(url); return /^https?:$/.test(parsed.protocol) ? parsed.hostname.replace(/^www\./, "") : ""; }
  catch { return ""; }
}

function SharePanel({ spin, lead, point }: { spin: SpinDetailData; lead: string; point: string }) {
  const [tab, setTab] = useState("image");
  const [status, setStatus] = useState<Record<string, string>>({});
  const imageUrl = `/api/clinic/spins/${spin.id}/card.png`;
  const url = `https://spin.clinic/klinika/${spin.id}`;
  const author = `${spin.author.name}${spin.author.party?.short ? `, ${spin.author.party.short}` : ""}`;
  const single = spin.scan?.share?.single || `Dr. Spin (AI) · ${author} · ${spin.verdict_label} ${spin.intensity}/100\n${lead}\n${url}`;
  const thread = spin.x_share?.length ? spin.x_share.slice(0, 2) : [];
  const posts = [thread[0] || `Dr. Spin (AI) · ${author} · ${spin.verdict_label} ${spin.intensity}/100\n${lead}`,
    thread[1] || `${point}\nPełna diagnoza ze źródłami: ${url}`];
  async function copy(key: string, text?: string) {
    try {
      if (text !== undefined) await navigator.clipboard.writeText(text);
      else {
        if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined") throw new Error("clipboard");
        // Obietnica zachowuje aktywację użytkownika także w przeglądarkach wymagających jej przy write().
        const blob = fetch(imageUrl).then(async response => {
          if (!response.ok) throw new Error("image");
          const result = await response.blob();
          if (result.type !== "image/png") throw new Error("format");
          return result;
        });
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      }
      setStatus(previous => ({ ...previous, [key]: "Skopiowano" }));
    } catch {
      setStatus(previous => ({ ...previous, [key]: text === undefined ? "Nie udało się skopiować obrazu. Użyj „Pobierz PNG”." : "Nie udało się skopiować. Zaznacz tekst i skopiuj ręcznie." }));
    }
  }
  return <section className="sc-scan-sh" aria-label="Udostępnij diagnozę">
    <div className="sc-scan-sh-tabs" role="tablist" aria-label="Format udostępniania">
      {[["image", "Obraz"], ["text", "Tekst z linkiem"], ["thread", "Wątek (2 wpisy)"]].map(([key, label]) =>
        <button type="button" key={key} role="tab" id={`share-tab-${spin.id}-${key}`} aria-controls={`share-panel-${spin.id}`} aria-selected={tab === key} tabIndex={tab === key ? 0 : -1} onClick={() => setTab(key)} onKeyDown={event => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          const tabs = ["image", "text", "thread"];
          const index = tabs.indexOf(tab);
          const next = tabs[event.key === "Home" ? 0 : event.key === "End" ? 2 : (index + (event.key === "ArrowRight" ? 1 : 2)) % 3];
          setTab(next);
          document.getElementById(`share-tab-${spin.id}-${next}`)?.focus();
        }}>{label}</button>)}
    </div>
    <div role="tabpanel" id={`share-panel-${spin.id}`} aria-labelledby={`share-tab-${spin.id}-${tab}`}>
      {tab === "image" ? <>
        {/* Podgląd obrazu przygotowanego przez backend. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="sc-scan-sh-image" src={imageUrl} alt={`Karta diagnozy #SPIN-${spin.id}`} />
        <div className="sc-scan-dg-actions"><button type="button" onClick={() => void copy("image")}>Kopiuj obraz</button><a className="sc-scan-button" href={imageUrl} download={`spin-${spin.id}.png`}>Pobierz PNG</a><span role="status">{status.image}</span></div>
      </> : (tab === "text" ? [single] : posts).map((text, index) => {
        const key = `${tab}-${index}`;
        return <div className="sc-scan-sh-text" key={key}>
          <label htmlFor={`share-${spin.id}-${key}`}>{tab === "thread" ? `Wpis ${index + 1}` : "Tekst z linkiem"} · {characterCount(text)} znaków</label>
          <textarea id={`share-${spin.id}-${key}`} value={text} readOnly rows={5} />
          <button type="button" onClick={() => void copy(key, text)}>Kopiuj</button> <span role="status">{status[key]}</span>
        </div>;
      })}
    </div>
  </section>;
}

export function HomeSpinScanner({ spin }: { spin: SpinDetailData }) {
  const [expanded, setExpanded] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [fullText, setFullText] = useState(false);
  const [clipped, setClipped] = useState(false);
  const textRef = useRef<HTMLParagraphElement>(null);
  const expandRef = useRef<HTMLButtonElement>(null);
  const wasExpanded = useRef(false);
  const scan = spin.scan;
  const lead = scan?.synthesis?.lead || spin.headline;
  const point = scan?.synthesis?.points?.[0] || firstSentence(spin.summary);
  const media = spin.post.media?.find(item => item.url);
  const videoFile = media && /\.(mp4|webm|mov)(?:[?#]|$)/i.test(media.url);
  const votes = scan?.council?.votes ?? spin.council?.members ?? [];
  const scores = votes.flatMap(vote => typeof vote.intensity === "number" ? [vote.intensity] : []);
  const range = scan?.council?.range ?? (scores.length ? [Math.min(...scores), Math.max(...scores)] : null);
  const agreement = scan?.council?.verdict_agreement ?? (votes.length ? `${votes.filter(vote => vote.verdict === spin.verdict).length}/${votes.length}` : "—");
  const claims = spin.claims ?? [];
  const checked = scan?.claims?.checked ?? claims.filter(claim => claim.assessment !== "unverified").length;
  const opinions = scan?.claims?.opinions ?? claims.filter(claim => claim.assessment === "unverified" && !claim.sources?.length).length;
  // Techniki z rodziną: z pola scan, a dla starszych odpowiedzi — kategoria z diagnozy i słownik rodzin.
  const techniques = (scan?.techniques ?? (spin.techniques ?? []).map(item => ({ ...item, name: item.category || item.name, family: FAMILY_OF[item.category || item.name] ?? "inne" })))
    .filter((item, index, list) => list.findIndex(other => other.name === item.name) === index);
  const familyCount = (key: string) => scan?.families?.[key]?.technique_types ?? techniques.filter(item => item.family === key).length;
  const typeCount = techniques.length;
  const familyMax = Math.max(1, ...FAMILIES.map(([key]) => familyCount(key)));
  const claimCount = (key: "supported" | "misleading" | "contradicted") => scan?.claims?.[key] ?? claims.filter(claim => claim.assessment === key).length;
  const [supported, misleading, contradicted] = [claimCount("supported"), claimCount("misleading"), claimCount("contradicted")];
  const activeFamilies = FAMILIES.filter(([key]) => familyCount(key) > 0).length;
  const claimSquares = [...Array(supported).fill("ok"), ...Array(misleading).fill("mid"), ...Array(contradicted).fill("bad"), ...Array(opinions).fill("op")] as string[];
  const analyzed = scan?.scope?.analyzed ?? (scan?.scope ? [scan.scope.text && "tekst", scan.scope.image && "obraz", scan.scope.video && "film"].filter(Boolean) : ["tekst", ...(media?.type === "photo" || media?.type === "image" ? ["obraz"] : [])]);
  const notAnalyzed = scan?.scope?.not_analyzed ?? (!scan?.scope?.video && spin.post.media?.some(item => ["video", "animated_gif", "amplify_video_thumb"].includes(item.type)) ? ["film"] : []);
  useEffect(() => {
    const element = textRef.current;
    if (!element) return;
    const measure = () => setClipped(element.scrollHeight > element.clientHeight + 1);
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    measure();
    return () => observer.disconnect();
  }, [fullText, spin.post.text]);
  useEffect(() => {
    const shouldScroll = wasExpanded.current && !expanded;
    wasExpanded.current = expanded;
    if (!shouldScroll) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const timer = window.setTimeout(() => {
      const section = document.getElementById("dr-spin");
      if (section && section.getBoundingClientRect().top < 0) section.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
    }, reducedMotion ? 0 : 410);
    return () => window.clearTimeout(timer);
  }, [expanded]);
  function collapse() {
    setExpanded(false);
    expandRef.current?.focus({ preventScroll: true });
  }
  return <article className="sc-scan-card" data-expanded={expanded || undefined} aria-labelledby={`scan-lead-${spin.id}`} onClick={event => {
    if (!(event.target as HTMLElement).closest("a,button,textarea,input,select,label,video") && !window.getSelection()?.toString()) setExpanded(true);
  }}>
    <div className="sc-scan-p" data-full={fullText || undefined}>
      <div className="sc-scan-p-inner">
        <header className="sc-scan-p-author"><SpinAvatar author={spin.author} /><div>
          <p className="sc-scan-p-name">{spin.author.name}{spin.author.party?.short ? `, ${spin.author.party.short}` : ""}</p>
          <p className="sc-scan-p-meta"><time dateTime={spin.post.published_at}>{formatDateTimePl(spin.post.published_at)}</time>{" · "}<a href={spin.post.url} target="_blank" rel="noopener noreferrer">Otwórz wpis na X ↗</a></p>
        </div></header>
        <p className="sc-scan-p-scope">Analiza: {analyzed.join(" i ")}{notAnalyzed.length ? ` · ${notAnalyzed.join(", ")} nieanalizowany` : ""}</p>
        {media ? <figure className="sc-scan-p-media">
          {videoFile ? <video src={media.url} controls preload="none" aria-label={media.alt || "Film dołączony do wpisu"} /> :
            // eslint-disable-next-line @next/next/no-img-element
            <img src={media.url} alt={media.alt || "Załącznik wpisu"} loading="lazy" referrerPolicy="no-referrer" />}
          <figcaption>Załącznik wpisu</figcaption>
        </figure> : null}
        <p ref={textRef} className="sc-scan-p-text" data-clipped={!fullText && clipped || undefined}>{spin.post.text}</p>
        {clipped || fullText ? <button type="button" className="sc-scan-p-more" onClick={() => setFullText(!fullText)}>{fullText ? "Zwiń wpis" : "Pokaż cały wpis"}</button> : null}
      </div>
    </div>
    <div className="sc-scan-dg">
      <header className="sc-scan-dg-head"><VerdictTag verdict={spin.verdict} label={spin.verdict_label} /><span className="sc-scan-dg-ai">Ocena Konsylium AI</span><span className="sc-scan-dg-id">#SPIN-{spin.id} · diagnoza {formatDatePl(scan?.diagnosed_at || spin.created_at)}</span></header>
      {expanded ? <p className="sc-scan-dg-who">Wpis: <strong>{spin.author.name}{spin.author.party?.short ? `, ${spin.author.party.short}` : ""}</strong> · {formatDateTimePl(spin.post.published_at)} · <a href={spin.post.url} target="_blank" rel="noopener noreferrer">Otwórz wpis na X ↗</a></p> : null}
      <h3 className="sc-scan-dg-lead" id={`scan-lead-${spin.id}`}>{lead}</h3>
      <p className="sc-scan-dg-point">{point}</p>
      <div className="sc-scan-m">
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Nasilenie spinu</p><p className="sc-scan-m-num sc-scan-strength">{spin.intensity}<small>/100</small></p>
          <div className="sc-scan-g" title="Ocena AI w skali 0–100"><span className="sc-scan-g-track"><i style={{ width: `${Math.max(0, Math.min(100, spin.intensity))}%` }} /></span><span className="sc-scan-g-scale"><b>0</b><b>50</b><b>100</b></span></div></div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Konsylium AI</p><p className="sc-scan-m-num">{agreement}<small> zgodne</small></p>
          <div className="sc-scan-g" title={scan?.council?.method || "Oceny modeli w skali 0–100; kropka — werdykt modelu"}>{votes.map((vote, index) => (
            <span key={index} className="sc-scan-g-row"><em>{modelLabel(vote.model)}</em><span className="sc-scan-g-track sc-scan-g-thin"><i style={{ width: `${Math.max(0, Math.min(100, vote.intensity ?? 0))}%` }} /></span><b>{vote.intensity ?? "—"}</b><u data-verdict={vote.verdict} title={`werdykt: ${vote.verdict ?? "brak"}`} /></span>))}</div></div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Twierdzenia</p><p className="sc-scan-m-num">{checked}<small> sprawdzone</small></p>
          <div className="sc-scan-g"><span className="sc-scan-g-squares">{claimSquares.map((kind, index) => <i key={index} data-k={kind} data-gap={index === claimSquares.indexOf("op") || undefined} />)}</span>
            <span className="sc-scan-g-legend">{supported ? <span data-k="ok">{supported} potw.</span> : null}{misleading ? <span data-k="mid">{misleading} mylące</span> : null}{contradicted ? <span data-k="bad">{contradicted} sprzeczne</span> : null}{opinions ? <span data-k="op">{opinions} {opinionsLabel(opinions)}</span> : null}</span></div></div>
        <div className="sc-scan-m-col"><p className="sc-scan-m-lbl">Techniki</p><p className="sc-scan-m-num">{typeCount}<small> {typeCount === 1 ? "typ" : typeCount >= 2 && typeCount <= 4 ? "typy" : "typów"}</small></p>
          <div className="sc-scan-g">{FAMILIES.map(([key, label]) => (
            <span key={key} className="sc-scan-g-row sc-scan-g-fam" data-family={key}><em>{label.split(" ")[0]}</em><span className="sc-scan-g-track sc-scan-g-thin"><i style={{ width: `${(familyCount(key) / familyMax) * 100}%` }} /></span><b>{familyCount(key)}</b></span>))}</div></div>
      </div>
      <table className="sc-scan-t"><thead><tr><th>Rodzina technik</th><th>Techniki w analizowanym materiale</th><th className="sc-scan-t-n">Typy</th></tr></thead><tbody>
        {FAMILIES.map(([key, label]) => <tr key={key} data-family={key}><th scope="row"><i />{label}</th><td>{techniques.filter(item => item.family === key).map(item => item.name).join(" · ") || <span className="sc-scan-t-none">Nie wskazano</span>}</td><td className="sc-scan-t-n">{familyCount(key)}</td></tr>)}
      </tbody></table>
      <footer className="sc-scan-dg-foot"><a className="sc-scan-dg-report" href={`mailto:kontakt@spin.clinic?subject=${encodeURIComponent(`Zgłoszenie błędu w diagnozie ${spin.id}`)}`}>Zgłoś błąd</a><div className="sc-scan-dg-actions">
        <button ref={expandRef} type="button" aria-expanded={expanded} aria-controls={`scan-details-${spin.id}`} onClick={() => expanded ? collapse() : setExpanded(true)}>{expanded ? "Zwiń uzasadnienie" : "Rozwiń uzasadnienie"}</button>
        <button type="button" aria-expanded={sharing} aria-controls={`scan-share-${spin.id}`} onClick={() => setSharing(!sharing)}>Udostępnij</button>
        <Link className="sc-scan-button sc-scan-primary" href={`/klinika/${spin.id}`}>Pełna diagnoza →</Link>
      </div></footer>
      <div className="sc-scan-expand" data-open={expanded}><div><section id={`scan-details-${spin.id}`} className="sc-scan-details" aria-label="Uzasadnienie" aria-hidden={!expanded}>
        <div className="sc-scan-details-grid">
          <div className="sc-scan-details-col">
            <h4>Techniki według rodzin</h4>
            {FAMILIES.map(([key, label]) => {
              const items = techniques.filter(item => item.family === key);
              return <div className="sc-scan-fam" data-family={key} key={key}><p className="sc-scan-fam-head"><i />{label}<b>{items.length}</b></p>
                {items.length ? items.map((item, index) => {
                  const original = spin.techniques?.find(old => ("category" in item && item.category && old.category === item.category) || old.name === item.name || (item.quote && old.quote === item.quote));
                  return <div className="sc-scan-t-item" key={index}><strong>{item.name}</strong>{item.quote ? <q>{item.quote}</q> : null}<span>{item.explanation || original?.explanation}</span></div>;
                }) : <p className="sc-scan-t-none">Nie wskazano</p>}</div>;
            })}
          </div>
          <div className="sc-scan-details-col">
            <h4>Twierdzenia i dowody</h4>
            {claims.length ? <ul className="sc-scan-cl">{claims.map((claim, index) => <li key={index}><span className="sc-scan-assessment" data-assessment={claim.assessment}>{claim.assessment_label}</span><q>{claim.claim}</q><p>{firstSentence(claim.explanation)}</p><div className="sc-scan-cl-src">{claim.sources?.filter(source => domain(source.url)).map((source, sourceIndex) => <a tabIndex={expanded ? 0 : -1} key={sourceIndex} href={source.url} target="_blank" rel="noopener noreferrer">{domain(source.url)}</a>)}</div></li>)}</ul> : <p>Brak osobno sprawdzonych twierdzeń.</p>}
            {scan?.synthesis?.points?.slice(1).map((text, index) => <p key={index}>{text}</p>)}
          </div>
        </div>
        <button type="button" tabIndex={expanded ? 0 : -1} onClick={collapse}>Zwiń uzasadnienie</button>
      </section></div></div>
    </div>
    {sharing ? <div id={`scan-share-${spin.id}`} className="sc-scan-share"><SharePanel spin={spin} lead={lead} point={point} /></div> : null}
  </article>;
}
