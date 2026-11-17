"use client";

/**
 * „Dwie pętle” (właściciel 6.10.2026, wariant A): zewnętrzna pętla agentów pracujących nad wpisem i wewnętrzna pętla
 * modeli różnych firm z Dr. Spinem i medianą w środku. Kroki zgodne z kodem: clinic.screen_post → clinic_council.diagnose
 * (consult → combine → check_claims / escalate_claims (Gemini z głębokim myśleniem) → write → review → polish → edit_plain)
 * → auto_publish → SpinOpinion, ClinicAuthorReply, rejestr sprostowań. Minimum trzy odpowiedzi modeli (MIN_MEMBERS = 3).
 * Rysunek SVG liczony od szerokości pudełka; przy ograniczonym ruchu tylko stan kroku i ręczne przełączanie.
 */

import { useEffect, useId, useRef, useState } from "react";
import { glueShortWords } from "../../lib/typography";

type Lang = "pl" | "en";
type Step = { short: string; t: string; d: string };

const STEPS: Record<Lang, Step[]> = {
  pl: [
    { short: "Wpis", t: "Wpis polityka", d: "Nowy wpis z potwierdzonego konta polityka. Każdy wpis, każdej strony, przechodzi tę samą drogę." },
    { short: "Strażnik", t: "Strażnik wybiera", d: "Darmowe modele oceniają wpis od 0 do 100. Od 75 trafia do kolejki, od 40 jest oznaczony, poniżej 40 zostaje pominięty." },
    { short: "Konsylium", t: "Niezależne głosy", d: "Cztery modele z co najmniej trzech firm, najpierw polski Bielik. Każdy osobno: werdykt, siła 0-100, techniki z cytatem, twierdzenia. Gdy model milczy, dołącza kolejny; przy mniej niż trzech odpowiedziach wpis wraca do kolejki." },
    { short: "Mediana", t: "Łączenie głosów", d: "Stałe reguły, nie kolejny model: werdykt i siła to mediana, technika wchodzi przy co najmniej dwóch wskazaniach. Zgoda modeli jest jawna." },
    { short: "Fakty", t: "Sprawdzanie faktów", d: "Gemini szuka źródeł w Google. Gdy zgoda modeli jest poniżej 2/3 albo spin ma 70+, rusza docisk: Gemini z głębokim myśleniem sprawdza w kilku niezależnych źródłach." },
    { short: "Uzasadnienie", t: "Uzasadnienie i recenzja", d: "Przewodniczący pisze diagnozę tylko z ocen i źródeł, bez zmiany werdyktu. Recenzent sprawdza zgodność z Kartą; przy uwagach jedna poprawka." },
    { short: "Redakcja", t: "Język i prosta wersja", d: "Językoznawca poprawia wyłącznie polszczyznę. Redaktor prostoty pisze krótki pierwszy ekran, sprawdzany dwiema kontrolami bez AI." },
    { short: "Publikacja", t: "Publikacja automatyczna", d: "Diagnoza ukazuje się sama, z głosami modeli i ograniczeniami. Nikt nie poprawia treści; operator może ją tylko wycofać." },
    { short: "Czytelnicy", t: "Czytelnicy i sprostowania", d: "Ocena trafna albo nietrafna, zgłoszenie błędu, odpowiedź autora wpisu. Odpowiedzi i wycofania trafiają do publicznego rejestru." },
  ].map(s => ({ ...s, t: glueShortWords(s.t), d: glueShortWords(s.d) })),
  en: [
    { short: "Post", t: "A politician's post", d: "A new post from a verified politician's account. Every post, from every side, follows the same path." },
    { short: "Gatekeeper", t: "The Gatekeeper selects", d: "Free models score the post from 0 to 100. From 75 it joins the queue, from 40 it is flagged, below 40 it is skipped." },
    { short: "Council", t: "Independent votes", d: "Four models from at least three companies, the Polish Bielik first. Each one separately: verdict, strength 0-100, techniques with a quotation, claims. If a model is silent, another joins; with fewer than three responses the post returns to the queue." },
    { short: "Median", t: "Combining the votes", d: "Fixed rules, not another model: the verdict and strength are medians, a technique counts when at least two models identify it. Model agreement is shown openly." },
    { short: "Facts", t: "Fact-checking", d: "Gemini looks for sources with Google Search. When agreement is below 2/3 or the spin is 70+, escalation starts: Gemini with deep thinking checks several independent sources." },
    { short: "Reasoning", t: "Reasoning and review", d: "The Chair writes the diagnosis only from the assessments and sources, without changing the verdict. The Reviewer checks it against the Charter; if there are remarks, one revision follows." },
    { short: "Editing", t: "Language and plain version", d: "The Linguist corrects only the Polish. The plain-language editor writes a short first screen, checked by two non-AI tests." },
    { short: "Publication", t: "Automatic publication", d: "The diagnosis appears on its own, with the models' votes and limitations. Nobody edits the content; the operator can only withdraw it." },
    { short: "Readers", t: "Readers and corrections", d: "Accurate or inaccurate rating, error reports, the author's reply. Replies and withdrawals go to a public register." },
  ],
};

const UI: Record<Lang, Record<string, string>> = {
  pl: {
    region: "Jak działa Konsylium AI", steps: "Kroki", pause: "Pauza", play: "Odtwórz", entry: "01 wpis polityka", next: "kolejny wpis",
    escalate: "docisk", review: "recenzja", corrections: "sprostowania", median: "04 MEDIANA",
    img: "Schemat dwóch pętli: wpis polityka przechodzi przez Strażnika, Konsylium modeli różnych firm, łączenie głosów (mediana), sprawdzanie faktów z dociskiem, uzasadnienie z recenzją, redakcję, publikację i oceny czytelników, które wracają jako sprostowania.",
    list: "Kroki po kolei",
    note: "Skład pokazany przykładowo (domyślna lista). Dobór zmienia się z dostępnością modeli; aktualny skład i wykonawców widać przy każdej diagnozie.",
  },
  en: {
    region: "How the AI Council works", steps: "Steps", pause: "Pause", play: "Play", entry: "01 politician's post", next: "next post",
    escalate: "escalation", review: "review", corrections: "corrections", median: "04 MEDIAN",
    img: "Diagram of two loops: a politician's post passes the Gatekeeper, the Council of models from different companies, combining the votes (median), fact-checking with escalation, reasoning with review, editing, publication and readers' ratings, which return as corrections.",
    list: "The steps in order",
    note: "The line-up shown is an example (the default list). Selection changes with model availability; the actual line-up and performers are shown with every diagnosis.",
  },
};

/** Domyślny skład (DEFAULT_COUNCIL w backend/news/clinic_council.py); dobór zmienia się z dostępnością modeli. */
const MODELS = [
  { n: "Bielik", pl: true }, { n: "gpt-oss" }, { n: "Qwen" }, { n: "Nemotron" },
  { n: "Gemini" }, { n: "Mistral" }, { n: "Llama" }, { n: "Gemma" },
] as const;

/** Kroki na pętli agentów (indeksy STEPS) i odwrotnie. Krok 04 (mediana) jest w środku. */
const OUT = [1, 2, 4, 5, 6, 7, 8];
const STEP_NODE: Record<number, number> = { 1: 0, 2: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6 };

/** Tempo (właściciel 6.10: o ok. 40% szybciej niż prototyp): krótkie przejścia, tekst kroku widoczny 1,2-2,3 s. */
const T = { gap: 500, travel: 450, entry: 700, hop: 200, spoke: 50, models: 500, pulse: 800, orbitFacts: 700, orbitReview: 600, ret: 750, reset: 300 };

const NS = "http://www.w3.org/2000/svg";
const DS_BUBBLE = "M37.32 46.95L34.3 47.4L31.23 47.49L28.18 47.22L25.2 46.59L22.36 45.63L19.7 44.34L17.28 42.75L15.15 40.89L13.34 38.8L11.9 36.52L10.85 34.1L10.21 31.57L10 29L10.21 26.43L10.85 23.9L11.9 21.48L13.34 19.2L15.15 17.11L17.28 15.25L19.7 13.66L22.36 12.37L25.2 11.41L28.18 10.78L31.23 10.51L34.3 10.6L37.32 11.05L40.24 11.85L43 12.98L45.54 14.42L47.83 16.15L49.8 18.13L51.42 20.31L52.67 22.67L53.52 25.15L53.95 27.71L53.95 30.29L53.52 32.85L52.67 35.33L51.42 37.69L49.8 39.87L47.83 41.85L46.72 42.75L47 50Z";
const DS_SPIRAL = "M32 19L33.36 19.32L34.63 19.81L35.79 20.47L36.82 21.27L37.7 22.18L38.43 23.19L38.99 24.26L39.38 25.37L39.61 26.5L39.66 27.62L39.56 28.71L39.3 29.74L38.91 30.69L38.41 31.55L37.8 32.31L37.11 32.95L36.35 33.46L35.56 33.84L34.75 34.09L33.94 34.22L33.15 34.22L32.4 34.11L31.7 33.89L31.06 33.58L30.51 33.2L30.04 32.76L29.67 32.27L29.39 31.75L29.21 31.23L29.12 30.7L29.11 30.2L29.19 29.73L29.33 29.31L29.54 28.94L29.79 28.64L30.07 28.4L30.37 28.23L30.68 28.14L30.98 28.11L31.26 28.14L31.51 28.23L31.61 28.3";

type Attrs = Record<string, string | number>;
const el = <K extends keyof SVGElementTagNameMap>(tag: K, attrs: Attrs, parent?: Element): SVGElementTagNameMap[K] => {
  const node = document.createElementNS(NS, tag);
  for (const k in attrs) node.setAttribute(k, String(attrs[k]));
  if (parent) parent.appendChild(node);
  return node;
};
const txt = (parent: Element, x: number, y: number, s: string, attrs: Attrs) => { const t = el("text", { x, y, ...attrs }, parent); t.textContent = s; return t; };
const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));
type Stop = () => boolean;
/** Płynne przejście (rAF, ease-in-out); przerywane, gdy użytkownik wybierze krok. */
const tween = (ms: number, fn: (e: number, p: number) => void, stop?: Stop) => new Promise<boolean>(resolve => {
  const t0 = performance.now();
  const frame = (now: number) => {
    if (stop?.()) return resolve(false);
    const p = Math.min(1, (now - t0) / ms), e = p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    fn(e, p);
    if (p < 1) requestAnimationFrame(frame); else resolve(true);
  };
  requestAnimationFrame(frame);
});

type Pill = { g: SVGGElement; x: number; y: number };
type Loop = { x: number; y: number; r: number; ring: SVGCircleElement; cap: SVGTextElement };

/** Rysunek i ruch: imperatywnie na SVG (jak w zatwierdzonym prototypie), React prowadzi tylko panel. */
function createDiagram(host: HTMLDivElement, uid: string, lang: Lang) {
  const steps = STEPS[lang], ui = UI[lang], n = MODELS.length;
  const ang = (k: number) => (-90 + k * 360 / 7) * Math.PI / 180;
  // modele co 360/n od góry: podpisy po bokach (0° i 180°) stoją między węzłami Fakty i Publikacja, nie pod nimi
  const mang = (k: number) => (-90 + k * 360 / n) * Math.PI / 180;
  let c = 0, R = 0, Rin = 0, ms = 11;
  let svg: SVGSVGElement, prog: SVGPathElement, entry: SVGTextElement, pulse: SVGCircleElement, token: SVGGElement;
  let ret: SVGPathElement, retCap: SVGTextElement;
  let spokes: SVGLineElement[] = [], mdots: SVGCircleElement[] = [], mlabs: SVGTextElement[] = [], pills: Pill[] = [];
  let loops: Record<number, Loop> = {};
  const at = (r: number, a: number): [number, number] => [c + r * Math.cos(a), c + r * Math.sin(a)];
  const arcPath = (r: number, a1: number, a2: number) => {
    if (a2 < a1) a2 += Math.PI * 2;
    const [x1, y1] = at(r, a1), [x2, y2] = at(r, a2);
    return `M${x1} ${y1}A${r} ${r} 0 ${a2 - a1 > Math.PI ? 1 : 0} 1 ${x2} ${y2}`;
  };
  const onPath = (defs: Element, id: string, d: string, label: string, dy: number) => {
    el("path", { id, d, fill: "none" }, defs);
    const t = el("text", { class: "sc-kloops__cap", "font-size": ms, dy }, svg);
    const tp = el("textPath", { href: `#${id}`, startOffset: "50%", "text-anchor": "middle" }, t); tp.textContent = label;
    return t;
  };

  function render() {
    host.innerHTML = "";
    const S = host.clientWidth, small = S < 380;
    if (!S) return;
    c = S / 2; R = S * (small ? .37 : .375); Rin = S * (small ? .15 : .17);
    const fs = small ? 11 : 12; ms = small ? 9.5 : 11;
    svg = el("svg", { viewBox: `0 0 ${S} ${S}`, "aria-hidden": "true", focusable: "false" }, host);
    const defs = el("defs", {}, svg);
    const pat = el("pattern", { id: `${uid}dots`, width: 18, height: 18, patternUnits: "userSpaceOnUse", x: c % 18, y: c % 18 }, defs);
    el("circle", { cx: 9, cy: 9, r: 1, class: "sc-kloops__dot" }, pat);
    const fade = el("radialGradient", { id: `${uid}fade` }, defs);
    el("stop", { offset: 0, "stop-color": "#fff", "stop-opacity": .9 }, fade); el("stop", { offset: 1, "stop-color": "#fff", "stop-opacity": 0 }, fade);
    const mask = el("mask", { id: `${uid}m` }, defs); el("circle", { cx: c, cy: c, r: R * .95, fill: `url(#${uid}fade)` }, mask);
    const glow = el("radialGradient", { id: `${uid}glow` }, defs);
    el("stop", { offset: 0, class: "sc-kloops__stop", "stop-opacity": .16 }, glow); el("stop", { offset: 1, class: "sc-kloops__stop", "stop-opacity": 0 }, glow);
    const glow2 = el("radialGradient", { id: `${uid}glow2` }, defs);
    el("stop", { offset: 0, class: "sc-kloops__stop", "stop-opacity": .45 }, glow2); el("stop", { offset: 1, class: "sc-kloops__stop", "stop-opacity": 0 }, glow2);
    const mk = el("marker", { id: `${uid}ar`, viewBox: "0 0 10 10", refX: 8, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
    el("path", { d: "M1 1L9 5L1 9", fill: "none", stroke: "context-stroke", "stroke-width": 1.6, "stroke-linecap": "round" }, mk);
    // prześwietlenie: poświata i kropki 18 px tylko w środku
    el("circle", { cx: c, cy: c, r: R * 1.05, fill: `url(#${uid}glow)` }, svg);
    el("rect", { width: S, height: S, fill: `url(#${uid}dots)`, mask: `url(#${uid}m)`, opacity: .55 }, svg);
    // pętla agentów od Strażnika do Czytelników; odcinek „kolejny wpis” przerywany
    el("path", { d: arcPath(R, ang(0), ang(6)), class: "sc-kloops__ring sc-kloops__flow" }, svg);
    el("path", { d: arcPath(R, ang(6), ang(0)), class: "sc-kloops__ring sc-kloops__ring--next", "stroke-dasharray": "1 6" }, svg);
    if (!small) onPath(defs, `${uid}nextp`, arcPath(R, ang(6), ang(7)), ui.next, ms + 6);
    prog = el("path", { class: "sc-kloops__prog", d: "" }, svg);
    // wejście wpisu
    const [sx, sy] = at(R, ang(0));
    el("line", { x1: sx, y1: 0, x2: sx, y2: sy - 16, class: "sc-kloops__ring sc-kloops__flow", "marker-end": `url(#${uid}ar)` }, svg);
    entry = txt(svg, sx + 8, 10, ui.entry, { class: "sc-kloops__cap", "font-size": ms, "dominant-baseline": "middle" });
    // pętla modeli
    el("circle", { cx: c, cy: c, r: Rin, class: "sc-kloops__ring sc-kloops__ring--in sc-kloops__flow" }, svg);
    spokes = MODELS.map((_, k) => { const [x, y] = at(Rin, mang(k)); return el("line", { x1: c, y1: c, x2: x, y2: y, class: "sc-kloops__spoke sc-kloops__flow" }, svg); });
    mdots = []; mlabs = [];
    MODELS.forEach((m, k) => {
      const a = mang(k), [x, y] = at(Rin, a), cos = Math.cos(a), sin = Math.sin(a);
      mdots.push(el("circle", { cx: x, cy: y, r: small ? 4 : 5, class: "sc-kloops__mdot" }, svg));
      const [lx, ly] = at(Rin + (small ? 9 : 12), a);
      const t = txt(svg, lx, ly + sin * 5, m.n, { class: "sc-kloops__mlab", "font-size": ms, "dominant-baseline": "middle",
        "text-anchor": cos > .35 ? "start" : cos < -.35 ? "end" : "middle" });
      if ("pl" in m) { const s = el("tspan", { class: "sc-kloops__pl", dx: 3 }, t); s.textContent = "PL"; }
      mlabs.push(t);
    });
    // środek: Dr. Spin i mediana
    pulse = el("circle", { cx: c, cy: c, r: 10, class: "sc-kloops__pulse" }, svg);
    const D = small ? 34 : 44;
    const doc = el("g", { transform: `translate(${c - D / 2} ${c - 6 - D / 2}) scale(${D / 64})` }, svg);
    el("circle", { cx: 32, cy: 32, r: 32, fill: "#3b82f6" }, doc);
    const spiral = el("g", { fill: "none", stroke: "#fff", "stroke-width": 4.5, "stroke-linecap": "round", "stroke-linejoin": "round" }, doc);
    el("path", { d: DS_BUBBLE }, spiral); el("path", { d: DS_SPIRAL }, spiral);
    txt(svg, c, c - 6 + D / 2 + (small ? 10 : 13), ui.median, { class: "sc-kloops__center", "font-size": small ? 8.5 : 9.5, "text-anchor": "middle", "dominant-baseline": "middle" });
    // pętle powtórzeń: docisk przy faktach, recenzja przy uzasadnieniu (do środka od węzła)
    loops = {};
    ([[2, ui.escalate], [3, ui.review]] as const).forEach(([k, name]) => {
      const a = ang(k), r = small ? 8 : 10, [x, y] = at(R - (small ? 13 : 15) - r - 3, a);
      const ring = el("circle", { cx: x, cy: y, r, class: "sc-kloops__loop sc-kloops__flow" }, svg);
      const cap = txt(svg, x - r - 5, y, name, { class: "sc-kloops__cap", "font-size": ms, "text-anchor": "end", "dominant-baseline": "middle" });
      loops[k] = { x, y, r, ring, cap };
    });
    // powrót od czytelników do publikacji: sprostowania
    const Ro = R + (small ? 22 : 28);
    ret = el("path", { d: `M${at(Ro, ang(5.82)).join(" ")}A${Ro} ${Ro} 0 0 0 ${at(Ro, ang(5.18)).join(" ")}`, class: "sc-kloops__ret sc-kloops__flow", "marker-end": `url(#${uid}ar)` }, svg);
    retCap = onPath(defs, `${uid}retp`, `M${at(Ro, ang(5.22)).join(" ")}A${Ro} ${Ro} 0 0 1 ${at(Ro, ang(5.78)).join(" ")}`, ui.corrections, -7);
    // węzły agentów
    const padX = small ? 18 : 24, h = small ? 26 : 30;
    pills = OUT.map((step, k) => {
      const [x, y] = at(R, ang(k)), g = el("g", { class: "sc-kloops__pill" }, svg);
      el("circle", { cx: x, cy: y, r: small ? 40 : 50, class: "sc-kloops__halo", fill: `url(#${uid}glow2)` }, g);
      const t = txt(g, 0, 0, "", { "font-size": fs, "dominant-baseline": "central" });
      const num = el("tspan", { class: "sc-kloops__num", "font-size": fs - 2 }, t); num.textContent = `${String(step + 1).padStart(2, "0")} `;
      const lab = el("tspan", {}, t); lab.textContent = steps[step].short;
      const w = t.getComputedTextLength() + padX;
      t.setAttribute("x", String(x - (w - padX) / 2)); t.setAttribute("y", String(y));
      g.insertBefore(el("rect", { x: x - w / 2, y: y - h / 2, width: w, height: h, rx: h / 2, class: "sc-kloops__face" }), t);
      return { g, x, y };
    });
    token = el("g", { opacity: 0 }, svg);
    el("circle", { r: small ? 6 : 7, class: "sc-kloops__token" }, token); el("circle", { r: 2.2, class: "sc-kloops__token-core" }, token);
    // wszystko w pudełku: gdy podpis wystaje, kwadratowy viewBox rośnie równo z każdej strony
    let over = 0;
    svg.querySelectorAll<SVGGraphicsElement>("text, .sc-kloops__face").forEach(node => {
      const b = node.getBBox();
      over = Math.max(over, -b.x, -b.y, b.x + b.width - S, b.y + b.height - S);
    });
    if (over > 0) { const o = Math.ceil(over) + 2; svg.setAttribute("viewBox", `${-o} ${-o} ${S + 2 * o} ${S + 2 * o}`); }
  }

  const put = (x: number, y: number, o = 1) => { token.setAttribute("transform", `translate(${x} ${y})`); token.setAttribute("opacity", String(o)); };
  const progress = (k: number) => prog.setAttribute("d", k > 0 ? arcPath(R, ang(0), ang(k)) : "");
  const setModels = (on: boolean) => {
    spokes.forEach(s => s.classList.toggle("is-on", on)); mdots.forEach(d => d.classList.toggle("is-on", on)); mlabs.forEach(d => d.classList.toggle("is-on", on));
  };
  function focus(i: number) {
    if (!svg) return;
    const node = STEP_NODE[i];
    pills.forEach((p, k) => { p.g.classList.toggle("is-on", k === node); p.g.classList.toggle("is-done", node !== undefined ? k < node : i === 3 && k < 2); });
    entry.classList.toggle("is-on", i === 0);
    Object.entries(loops).forEach(([k, l]) => { const on = (k === "2" && i === 4) || (k === "3" && i === 5); l.ring.classList.toggle("is-on", on); l.cap.classList.toggle("is-on", on); });
    ret.classList.toggle("is-on", i === 8); retCap.classList.toggle("is-on", i === 8);
    setModels(i === 2 || i === 3);
    progress(i === 3 ? 1 : node || 0);
  }
  function still(i: number) {
    if (!svg) return;
    focus(i);
    if (i === 0) { const [x, y] = at(R, ang(0)); return put(x, y * .45); }
    if (i === 3) return put(c, c, 0);
    const p = pills[STEP_NODE[i]]; put(p.x, p.y, 0);
  }
  const land = (k: number) => { pills.forEach((p, j) => p.g.classList.toggle("is-on", j === k)); token.setAttribute("opacity", "0"); };
  async function travel(k1: number, k2: number, stop: Stop) {
    pills[k2].g.classList.remove("is-on");
    const ok = await tween(T.travel, e => { const a = ang(k1) + (ang(k2) - ang(k1)) * e; const [x, y] = at(R, a); put(x, y); prog.setAttribute("d", arcPath(R, ang(0), a)); }, stop);
    land(k2); return ok;
  }
  const line = (x1: number, y1: number, x2: number, y2: number, dur: number, stop: Stop) => tween(dur, e => put(x1 + (x2 - x1) * e, y1 + (y2 - y1) * e), stop);
  async function orbit(k: 2 | 3, dur: number, stop: Stop) {
    const l = loops[k], p = pills[k];
    if (!await line(p.x, p.y, l.x, l.y - l.r, T.hop, stop)) return false;
    if (!await tween(dur, e => { const a = -Math.PI / 2 + e * Math.PI * 2; put(l.x + l.r * Math.cos(a), l.y + l.r * Math.sin(a)); }, stop)) return false;
    const ok = await line(l.x, l.y - l.r, p.x, p.y, T.hop, stop); token.setAttribute("opacity", "0"); return ok;
  }
  async function ring(x: number, y: number, r0: number, r1: number, dur: number, stop: Stop) {
    pulse.setAttribute("cx", String(x)); pulse.setAttribute("cy", String(y)); pulse.style.opacity = "1";
    await tween(dur, (_, p) => { pulse.setAttribute("r", String(r0 + p * (r1 - r0))); pulse.style.opacity = String(1 - p); }, stop);
    pulse.style.opacity = "0";
  }
  async function anim(i: number, stop: Stop) {
    if (!svg) return sleep(1000);
    const [sx, sy] = at(R, ang(0));
    if (i === 0) { progress(0); pills[0].g.classList.remove("is-on"); await line(sx, 2, sx, sy - 14, T.entry, stop); return; }
    if (i === 1) { land(0); return sleep(900); }
    if (i === 2) {
      if (!await travel(0, 1, stop)) return;
      const p = pills[1]; await sleep(100);
      if (!await line(p.x, p.y, c, c, 300, stop)) return;
      put(c, c, 0); setModels(false);
      const order = MODELS.map((_, k) => k).sort(() => Math.random() - .5);
      for (const k of order) {
        if (stop()) return;
        spokes[k].classList.add("is-on"); await sleep(T.spoke);
        setTimeout(() => { mdots[k]?.classList.add("is-on"); mlabs[k]?.classList.add("is-on"); }, 120 + Math.random() * 280);
      }
      return sleep(T.models);
    }
    if (i === 3) { await ring(c, c, 10, Rin * .8, T.pulse, stop); return sleep(200); }
    if (i === 4) { const p = pills[2]; put(c, c); if (!await line(c, c, p.x, p.y, 400, stop)) return; progress(2); land(2); await orbit(2, T.orbitFacts, stop); return sleep(200); }
    if (i === 5) { if (!await travel(2, 3, stop)) return; await orbit(3, T.orbitReview, stop); return sleep(200); }
    if (i === 6) { await travel(3, 4, stop); return sleep(450); }
    if (i === 7) { if (!await travel(4, 5, stop)) return; const p = pills[5]; return ring(p.x, p.y, 14, 50, 700, stop); }
    if (i === 8) {
      if (!await travel(5, 6, stop)) return; await sleep(200);
      const len = ret.getTotalLength();
      if (await tween(T.ret, e => { const pt = ret.getPointAtLength(len * e); put(pt.x, pt.y); }, stop)) land(5);
    }
  }
  const reset = () => { if (!svg) return; progress(0); put(0, 0, 0); setModels(false); };
  return { render, focus, still, anim, reset };
}

export function CouncilLoops({ lang = "pl" }: { lang?: Lang }) {
  const steps = STEPS[lang], ui = UI[lang];
  const uid = `k${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const host = useRef<HTMLDivElement>(null);
  const ctl = useRef<{ pick(j: number): void; toggle(): void } | null>(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const node = host.current;
    if (!node) return;
    const view = createDiagram(node, uid, lang);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      || !!document.documentElement.closest('[data-sc-force~="reduced-motion"]');
    let i = 0, gen = 0, on = !reduced, width = 0, alive = true;
    const show = (j: number) => { i = j; setStep(j); };
    const wait = (ms: number, g: number) => sleep(ms).then(() => g !== gen);
    async function loop() {
      const g = ++gen;
      while (alive && on && g === gen) {
        show(i); view.focus(i);
        await view.anim(i, () => g !== gen || !alive);
        if (g !== gen || await wait(T.gap, g)) return;
        i = (i + 1) % steps.length;
        if (i === 0) { view.reset(); if (await wait(T.reset, g)) return; }
      }
    }
    ctl.current = {
      pick(j) { gen++; on = false; setPlaying(false); show(j); view.still(j); },
      toggle() { on = !on; setPlaying(on); if (on) loop(); else { gen++; view.still(i); } },
    };
    const redraw = () => {
      if (!alive || node.clientWidth === width) return;
      width = node.clientWidth; gen++; view.render(); view.still(i); if (on) loop();
    };
    setPlaying(on);
    const ro = new ResizeObserver(redraw);
    (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => { if (!alive) return; redraw(); ro.observe(node); });
    return () => { alive = false; gen++; ro.disconnect(); ctl.current = null; };
  }, [lang, steps.length, uid]);

  return (
    <div className="sc-kloops" role="group" aria-label={ui.region}>
      <div className="sc-kloops__stage">
        <div className="sc-kloops__dia" ref={host} role="img" aria-label={ui.img} />
        <div className="sc-kloops__panel">
          <div className="sc-kloops__head">
            <span className="sc-kloops__n">{String(step + 1).padStart(2, "0")} / {String(steps.length).padStart(2, "0")}</span>
            <button type="button" className="sc-kloops__play" aria-pressed={!playing} onClick={() => ctl.current?.toggle()}>{playing ? ui.pause : ui.play}</button>
          </div>
          <div className="sc-kloops__body" aria-live={playing ? "off" : "polite"}>
            {steps.map((s, j) => <div key={s.short} className="sc-kloops__text" data-on={j === step} aria-hidden={j !== step}>
              <h3 className="sc-kloops__t">{s.t}</h3><p className="sc-kloops__d">{s.d}</p></div>)}
          </div>
          <div className="sc-kloops__dots" role="tablist" aria-label={ui.steps}>
            {steps.map((s, j) => <button key={s.short} type="button" role="tab" aria-selected={j === step} data-done={j < step}
              aria-label={`${j + 1}. ${s.t.replace(/ /g, " ")}`} onClick={() => ctl.current?.pick(j)}><i /></button>)}
          </div>
        </div>
      </div>
      <p className="sc-kloops__note">{lang === "pl" ? glueShortWords(ui.note) : ui.note}</p>
      <ol className="sc-sr-only" aria-label={ui.list}>{steps.map(s => <li key={s.short}>{s.t}: {s.d}</li>)}</ol>
    </div>
  );
}
