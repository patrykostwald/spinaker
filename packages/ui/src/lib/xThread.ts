/**
 * Diagnoza jako wątek na X: 1/N — podsumowanie z linkiem do pełnej diagnozy (X pokaże jej kartę),
 * dalej techniki z cytatami i twierdzenia ze źródłami, na końcu link. Każdy wpis mieści się w limicie
 * 280 znaków ważonych (liczonych jak w X, linki = 23 znaki) — razem z numerem „k/N”.
 */
import { DOMAIN } from "./api";
import type { SpinDetailData } from "./clinic";
import { measurePost } from "./xText";

const LIMIT = 280;
const MAX_POSTS = 10;
const fits = (text: string) => measurePost(text).weightedLength <= LIMIT;

/** Tnie tekst na kawałki mieszczące się w limicie (z zapasem na numer), po słowach. */
function split(text: string, reserve: number): string[] {
  const words = text.replace(/\s+/g, " ").trim().split(" ");
  const parts: string[] = [];
  let current = "";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (measurePost(next).weightedLength + reserve <= LIMIT) current = next;
    else { if (current) parts.push(current); current = word; }
  }
  if (current) parts.push(current);
  return parts;
}

function shorten(text: string, budget: number): string {
  if (measurePost(text).weightedLength <= budget) return text;
  let result = text;
  while (result && measurePost(`${result}…`).weightedLength > budget) result = result.slice(0, -2).trimEnd();
  return `${result}…`;
}

export function diagnosisUrl(spin: { id: number }): string {
  return `https://${DOMAIN}/klinika/${spin.id}`;
}

export function buildXThread(spin: SpinDetailData): string[] {
  const url = diagnosisUrl(spin);
  const head = `Dr. Spin (AI) o wpisie @${spin.author.handle}: ${spin.verdict_label}, siła ${spin.intensity}/100.`;
  const reserve = 8; // „10/10 ” i spacja
  const firstBudget = LIMIT - reserve - measurePost(`${head}  ${url}`).weightedLength;
  const first = `${head} ${shorten(spin.headline, Math.max(40, firstBudget))} ${url}`;

  const body: string[] = [];
  for (const technique of spin.techniques) {
    body.push(...split(`Technika: ${technique.name}. „${technique.quote}” — ${technique.explanation}`, reserve));
  }
  for (const claim of spin.claims) {
    const source = claim.sources[0]?.url;
    body.push(...split(`${claim.assessment_label[0].toUpperCase()}${claim.assessment_label.slice(1)}: ${claim.claim}. ${claim.explanation}`, reserve));
    if (source) body.push(`Źródło: ${source}`);
  }
  const last = `Pełna diagnoza, źródła i ograniczenia: ${url} · Diagnozę przygotowało AI.`;
  const posts = [first, ...body.slice(0, MAX_POSTS - 2), last];
  const total = posts.length;
  return posts.map((post, index) => {
    const numbered = `${index + 1}/${total} ${post}`;
    return fits(numbered) ? numbered : shorten(numbered, LIMIT);
  });
}

/** Otwiera okno publikacji na X; z `replyTo` — jako odpowiedź pod wpisem polityka. */
export function xIntentUrl(text: string, replyTo?: string): string {
  const params = new URLSearchParams({ text });
  if (replyTo) params.set("in_reply_to", replyTo);
  return `https://x.com/intent/post?${params}`;
}
