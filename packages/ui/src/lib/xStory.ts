/**
 * Nitka kontekstowa jako wątek na X.
 * 1/N - tytuł, krótki opis całej nitki i link do nitki na spin.clinic (X pokaże jej kartę).
 * 2/N…N/N - kolejne boxy: rodzaj, źródło, tytuł, komentarz autora i link do ORYGINAŁU
 * (X pokaże kartę ze zdjęciem strony redakcji - ruch idzie do autora materiału).
 * Każdy wpis mieści się w 280 znakach ważonych; dłuższe fragmenty skracamy całymi słowami.
 */
import { DOMAIN } from "./api";
import { categoryLabel } from "./utils";
import { measurePost } from "./xText";
import { shorten } from "./xThread";
import type { Article } from "../types";

const LIMIT = 280;
const URL_WEIGHT = 23; // X liczy każdy link jako 23 znaki

export type StoryThread = { title: string; description: string; slug: string; items: Array<{ article: Article; editorial_note: string }> };

export function threadUrl(slug: string): string {
  return `https://${DOMAIN}/thread/${slug}`;
}

/** Pierwszy wpis: tytuł, opis, link. Zwraca też, czy mieści się bez skracania (do licznika w edytorze). */
export function openingPost(title: string, description: string, slug: string, total: number) {
  const url = slug ? threadUrl(slug) : `https://${DOMAIN}/thread/…`;
  const head = `1/${total} ${title.trim()}`;
  const full = [head, description.trim(), url].filter(Boolean).join("\n\n");
  const length = measurePost(full).weightedLength - measurePost(url).weightedLength + URL_WEIGHT;
  return { text: full, length, fits: length <= LIMIT };
}

function boxPost(index: number, total: number, article: Article, note: string): string {
  const url = article.url;
  const kind = article.reference_only ? "Wpis na X" : categoryLabel(article.category);
  const source = article.reference_only ? "" : ` · ${article.source?.name ?? ""}`;
  const head = `${index}/${total} ${kind}${source}`;
  const budget = LIMIT - URL_WEIGHT - measurePost(head).weightedLength - 6;
  const title = article.reference_only ? "" : article.title.trim();
  const body = [title, note.trim()].filter(Boolean).join(" - ");
  return [head, shorten(body, Math.max(40, budget)), url].filter(Boolean).join("\n");
}

export function buildStoryThread(thread: StoryThread): string[] {
  const total = thread.items.length + 1;
  const first = openingPost(thread.title, thread.description, thread.slug, total);
  const opening = first.fits ? first.text : [`1/${total} ${thread.title.trim()}`, shorten(thread.description, 180), threadUrl(thread.slug)].join("\n\n");
  return [opening, ...thread.items.map((item, index) => boxPost(index + 2, total, item.article, item.editorial_note))];
}
