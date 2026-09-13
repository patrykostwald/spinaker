import type { Article, TimelineResponse } from '../types';
const warsawDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Warsaw', year: 'numeric', month: '2-digit', day: '2-digit' });
export function publicationDay(article: Article): string {
  if (!article.published_date) return 'undated';
  const date = new Date(article.published_date);
  if (Number.isNaN(date.getTime())) return 'undated';
  const parts = warsawDay.formatToParts(date);
  const part = (type: string) => parts.find(value => value.type === type)?.value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}
export function mergeSearchTimeline(pages: TimelineResponse[], discovered: Article[], categories: string[], from: string, to: string) {
  const articles = new Map<number, Article>();
  for (const page of pages) for (const rows of Object.values(page.timeline)) for (const article of rows) articles.set(article.id, article);
  for (const article of discovered) {
    const day = publicationDay(article);
    if (categories.length && !categories.includes(article.category)) continue;
    if ((from || to) && day === 'undated') continue;
    if ((from && day < from) || (to && day > to)) continue;
    articles.set(article.id, article);
  }
  const sorted = [...articles.values()].sort((a, b) => {
    const left = a.published_date ? Date.parse(a.published_date) : -Infinity;
    const right = b.published_date ? Date.parse(b.published_date) : -Infinity;
    return left === right ? b.id - a.id : left > right ? -1 : 1;
  });
  const timeline: TimelineResponse['timeline'] = {};
  for (const article of sorted) (timeline[publicationDay(article)] ??= []).push(article);
  return timeline;
}
