/**
 * Diagnoza jako wątek na X. Treść to synteza diagnozy przygotowana raz przez darmowy model (`x_thread`):
 * 1/N — werdykt i siła (dosłownie z diagnozy), główna teza i link do pełnej diagnozy (X pokaże jej kartę),
 * dalej 2–3 wpisy o technikach i twierdzeniach, na końcu link. Bez syntezy — zwięzły zapas: po jednym
 * wpisie na technikę, skrócone całymi słowami (nigdy urwane w pół zdania). Limit 280 znaków ważonych.
 */
import { DOMAIN } from "./api";
import type { SpinDetailData } from "./clinic";
import { measurePost } from "./xText";

const LIMIT = 280;
const RESERVE = 6; // „5/5 ” z zapasem
const fits = (text: string) => measurePost(text).weightedLength <= LIMIT;

/** Skraca do limitu całymi słowami (a jeśli się da — całymi zdaniami). */
function shorten(text: string, budget: number): string {
  if (measurePost(text).weightedLength <= budget) return text;
  const sentences = text.match(/[^.!?]+[.!?]+/g) ?? [];
  let bySentence = "";
  for (const sentence of sentences) {
    const next = (bySentence + sentence).trim();
    if (measurePost(next).weightedLength > budget) break;
    bySentence = next;
  }
  if (bySentence.length > text.length / 3) return bySentence;
  const words = text.split(/\s+/);
  let result = "";
  for (const word of words) {
    const next = result ? `${result} ${word}` : word;
    if (measurePost(`${next}…`).weightedLength > budget) break;
    result = next;
  }
  return `${result.replace(/[,;:—–-]+$/, "")}…`;
}

export function diagnosisUrl(spin: { id: number }): string {
  return `https://${DOMAIN}/klinika/${spin.id}`;
}

export function buildXThread(spin: SpinDetailData): string[] {
  const url = diagnosisUrl(spin);
  const head = `Dr. Spin (AI) o wpisie @${spin.author.handle}: ${spin.verdict_label.toLowerCase()}, siła ${spin.intensity}/100.`;
  const leadBudget = LIMIT - RESERVE - measurePost(`${head}  ${url}`).weightedLength;
  const synthesis = spin.x_thread ?? [];
  let lead: string;
  let body: string[];
  if (synthesis.length >= 2) {
    [lead, ...body] = synthesis;
  } else {
    lead = spin.headline;
    body = spin.techniques.slice(0, 3).map(t => `${t.name}: „${t.quote}”. ${t.explanation}`);
    const counts = spin.claims.reduce<Record<string, number>>((acc, c) => ({ ...acc, [c.assessment_label]: (acc[c.assessment_label] ?? 0) + 1 }), {});
    const summary = Object.entries(counts).map(([label, n]) => `${label}: ${n}`).join(", ");
    if (summary) body.push(`Twierdzenia we wpisie — ${summary}. Każde ze źródłami w pełnej diagnozie.`);
  }
  const first = `${head} ${shorten(lead, Math.max(60, leadBudget))} ${url}`;
  const last = `Pełna diagnoza: techniki z cytatami, twierdzenia ze źródłami i ograniczenia analizy — ${url} · Diagnozę przygotowało AI.`;
  const posts = [first, ...body.map(post => shorten(post, LIMIT - RESERVE)), last];
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
