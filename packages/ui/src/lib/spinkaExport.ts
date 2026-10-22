import type { ThreadElement } from './community';

/** Eksport spinki (właściciel 3.10): tekst z linkami do wklejenia w artykuł i CSV do analizy. */
type Meta = { id: number; title: string; author: string };

const absolute = (url: string, origin: string) => url.startsWith('/') ? origin + url : url;
const sourceOf = (item: ThreadElement) => item.source_name || (item.kind === 'link' ? item.domain : '');

export function spinkaMarkdown(meta: Meta, items: ThreadElement[], origin: string) {
  const lines = [`${meta.author}: ${meta.title}`, `${origin}/spinki/${meta.id}`, ''];
  items.forEach((item, index) => {
    if (index && item.link_note) lines.push(`   ↳ spinka ${index}: ${item.link_note}`);
    lines.push(`${index + 1}. ${item.title}${sourceOf(item) ? ` (${sourceOf(item)})` : ''}`, `   ${absolute(item.url, origin)}`);
    if (item.note) lines.push(`   Wyjaśnienie autora: ${item.note}`);
  });
  lines.push('', 'Źródło: spin.clinic');
  return lines.join('\n');
}

const cell = (value: unknown) => {
  const text = String(value ?? '');
  return /[";\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

export function spinkaCsv(meta: Meta, items: ThreadElement[], origin: string) {
  const head = ['spinka_id', 'spinka_tytul', 'autor', 'boks', 'tytul', 'zrodlo', 'data', 'adres', 'wyjasnienie_autora', 'spinka_do_poprzedniego'];
  const rows = items.map((item, index) => [meta.id, meta.title, meta.author, index + 1, item.title, sourceOf(item), item.published_date ?? '',
    absolute(item.url, origin), item.note ?? '', index ? item.link_note ?? '' : '']);
  return [head, ...rows].map(row => row.map(cell).join(';')).join('\r\n');
}
