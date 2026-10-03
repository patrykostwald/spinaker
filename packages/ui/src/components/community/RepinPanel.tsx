"use client";

import { useState } from 'react';
import Link from 'next/link';
import { useQueryClient } from '@tanstack/react-query';
import type { CommunityThreadSummary, ThreadElement } from '../../lib/community';
import { savePersonalThread } from '../../lib/personal';
import { emailVerified, useAccount } from '../../lib/account';
import { SpinkaClip } from './ThreadSteps';

/**
 * Przepięcie (właściciel 3.10): zamiast komentarzy pojawia się lustrzane odbicie spinki. Te same boksy w tej samej
 * kolejności, a czytelnik pisze własne wyjaśnienia boksów i własne spinki (dlaczego dwa materiały się łączą).
 */
export function RepinPanel({ thread, items, onClose }: { thread: CommunityThreadSummary; items: ThreadElement[]; onClose: () => void }) {
  const account = useAccount();
  const cache = useQueryClient();
  const [title, setTitle] = useState(`Przepięcie: ${thread.title}`.slice(0, 80));
  const [notes, setNotes] = useState(() => items.map(() => ''));
  const [links, setLinks] = useState(() => items.map(() => ''));
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState('');
  const [doneId, setDoneId] = useState<number | null>(null);
  const signedIn = account.data?.authenticated;
  const canPublish = signedIn && emailVerified(account.data);

  async function save(publish: boolean) {
    setPending(true); setStatus('');
    try {
      const saved = await savePersonalThread({
        title: title.trim(), description: '', query: '', categories: [], source_ids: [], repin_of: thread.id, is_public: publish,
        items: items.map((item, index) => ({
          ...(item.box ? { box_item_id: item.id } : item.kind === 'article' ? { article_id: item.id } : { link_id: item.id }),
          note: notes[index].trim(), link_note: index ? links[index].trim() : '',
        })),
      });
      setDoneId(saved.id);
      setStatus(publish ? 'Przepięcie opublikowane. Najpierw trafia do izby przyjęć.' : 'Szkic zapisany na Twoim koncie.');
      void cache.invalidateQueries({ queryKey: ['community-thread', String(thread.id)] });
    } catch (error) { setStatus(error instanceof Error ? error.message : 'Nie udało się zapisać przepięcia.'); }
    finally { setPending(false); }
  }

  if (!signedIn) return <section className="sc-repin" aria-label="Przepnij spinkę">
    <p className="sc-repin__lead"><Link href="/konto">Zaloguj się</Link>, aby przepiąć tę spinkę po swojemu.</p>
    <button type="button" className="sc-repin__ghost" onClick={onClose}>Wróć do komentarzy</button>
  </section>;

  return <section className="sc-repin" aria-label="Przepnij spinkę">
    <header className="sc-repin__head">
      <p className="sc-repin__lead">Te same boksy, Twoje spięcie. Napisz, co według Ciebie znaczy każdy materiał i jak naprawdę się łączą.</p>
      <label className="sc-repin__title"><span>Tytuł przepięcia</span>
        <input value={title} maxLength={80} onChange={event => setTitle(event.target.value)} /></label>
    </header>
    <ol className="sc-repin__track">
      {items.map((item, index) => <li key={`${item.kind}:${item.id}`} className="sc-repin__step">
        {index > 0 && <div className="sc-repin__joint">
          <SpinkaClip />
          <label><span>Twoja spinka {index}</span>
            <textarea rows={3} maxLength={200} value={links[index]} placeholder={item.link_note ? `Autor: ${item.link_note}` : 'Dlaczego te dwa materiały się łączą?'}
              onChange={event => setLinks(links.map((value, at) => at === index ? event.target.value : value))} /></label>
        </div>}
        <div className="sc-repin__box">
          <p className="sc-repin__src">{item.source_name || (item.kind === 'link' ? item.domain : '')}</p>
          <p className="sc-repin__mat">{item.title}</p>
          <label><span>Twój tytuł boksu</span>
            <textarea rows={4} maxLength={4000} value={notes[index]} placeholder="Co ten materiał pokazuje?"
              onChange={event => setNotes(notes.map((value, at) => at === index ? event.target.value : value))} /></label>
        </div>
      </li>)}
    </ol>
    <footer className="sc-repin__foot">
      {status && <p role="status">{status} {doneId && <Link href={`/spinki/${doneId}`}>Zobacz →</Link>}</p>}
      <button type="button" className="sc-repin__ghost" onClick={onClose}>Anuluj</button>
      <button type="button" className="sc-repin__ghost" disabled={pending || !title.trim()} onClick={() => void save(false)}>Zapisz szkic</button>
      <button type="button" className="sc-repin__go" disabled={pending || !title.trim() || !canPublish} title={canPublish ? undefined : 'Potwierdź e-mail, aby publikować'} onClick={() => void save(true)}>Opublikuj przepięcie</button>
    </footer>
  </section>;
}
