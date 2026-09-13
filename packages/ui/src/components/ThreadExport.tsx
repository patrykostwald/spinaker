"use client";
import { useState } from 'react';
import type { ThreadDetail } from '../types';
import { measurePost } from '../lib/xText';
export function ThreadExport({thread}: {thread: ThreadDetail}) {
 const [posts, setPosts] = useState<string[]>([]); const [notice, setNotice] = useState('');
 const sponsored = thread.is_sponsored || thread.thread_type === 'sponsored';
 const mandatoryPrefix = sponsored ? `[${thread.sponsorship_label || 'Nitka sponsorowana'}] ` : '';
 const prepare = () => {
   const ordered = [...thread.items].sort((a,b) => a.position - b.position);
   const main = thread.editorial_slot ? ordered[0] : [...ordered].reverse().find(i => i.article.published_date) ?? ordered[0];
   const items = main ? [main, ...ordered.filter(i => i.id !== main.id)] : [];
   setPosts(items.map((item,i) => `${i+1}/${items.length} ${item.editorial_note || item.article.title}\n${item.article.url}${i === 0 ? '\n' + window.location.origin + '/thread/' + thread.slug : ''}`));
   setNotice('Sprawdź teksty przed publikacją. Zmiany tutaj dotyczą wyłącznie eksportu.');
 };
 return <section className="space-y-4 rounded-xl border bg-white p-5"><button onClick={prepare} className="font-semibold text-primary">Przygotuj do publikacji na X</button>{notice && <p role="status" className="text-sm text-slate-600">{notice}</p>}{posts.map((post,i) => { const completePost = mandatoryPrefix + post; const stats=measurePost(completePost); return <div key={i} className="space-y-2">{sponsored && <p className="card-sponsorship">Stałe oznaczenie eksportu: {mandatoryPrefix}</p>}<label className="block text-sm font-semibold">Post {i+1} · {stats.weightedLength}/280<textarea value={post} onChange={e => setPosts(current => current.map((p,n) => n === i ? e.target.value : p))} rows={4} className="mt-2 block w-full rounded-lg border p-3 font-normal" /></label>{sponsored && <p className="text-xs text-slate-500">Oznaczenie sponsorowania zostaje dodane przy kopiowaniu i jest uwzględnione w limicie. Edycja tekstu go nie usuwa.</p>}{!stats.valid && <p className="text-sm text-red-700">Skróć tekst lub usuń niedozwolone znaki przed skopiowaniem.</p>}<button disabled={!stats.valid} className="rounded-lg border px-4 py-2 text-sm text-primary disabled:opacity-40" onClick={async () => { try {await navigator.clipboard.writeText(completePost); setNotice(`Skopiowano post ${i+1}.`);} catch {setNotice('Nie udało się skopiować. Użyj tekstu wraz z widocznym stałym oznaczeniem sponsorowania.');} }}>Kopiuj post {i+1}</button></div>; })}</section>;
}
