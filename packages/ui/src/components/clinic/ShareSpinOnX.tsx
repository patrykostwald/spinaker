"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "../../kit";
import { getSpin, type SpinDetailData } from "../../lib/clinic";
import { buildXThread, xIntentUrl } from "../../lib/xThread";
import { Dialog } from "../Dialog";

function ThreadPosts({ spin }: { spin: SpinDetailData }) {
  const posts = buildXThread(spin);
  const [copied, setCopied] = useState<number | null>(null);
  async function copy(text: string, index: number) {
    try { await navigator.clipboard.writeText(text); setCopied(index); } catch { setCopied(null); }
  }
  return (
    <div className="sc-xshare">
      <p className="sc-xshare__hint">{posts.length === 1 ? "Jeden wpis: ocena w skali spinu, techniki i terapia — źródła z linkami. Na końcu cytowany wpis polityka i link do pełnej diagnozy." : `Wątek z ${posts.length} wpisów. Opublikuj pierwszy, kolejne wklej jako odpowiedzi.`}</p>
      <div className="sc-xshare__actions">
        <a className="sc-xshare__link is-primary" href={xIntentUrl(posts[0])} target="_blank" rel="noopener noreferrer">{posts.length === 1 ? "Opublikuj na X" : `Opublikuj 1/${posts.length} na X`}</a>
        <a className="sc-xshare__link" href={xIntentUrl(posts[0], spin.post.id)} target="_blank" rel="noopener noreferrer">Odpowiedz pod wpisem @{spin.author.handle}</a>
        <Button variant="quiet" size="sm" onClick={() => copy(posts.join("\n\n"), -1)}>{copied === -1 ? "Skopiowano cały wątek" : "Kopiuj cały wątek"}</Button>
      </div>
      <ol className="sc-xshare__posts">
        {posts.map((post, index) => (
          <li key={index}>
            <p>{post}</p>
            <button type="button" onClick={() => copy(post, index)}>{copied === index ? "Skopiowano" : "Kopiuj"}</button>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function ShareXCardContent({ interview = false }: { interview?: boolean }) {
  return <><svg className="sc-share-cta__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path fill="currentColor" d="M18.9 2H22l-6.8 7.8L23.2 22h-6.3L12 14.6 5.5 22H2.3l7.9-9L.8 2h6.5l4.5 6.8L18.9 2Zm-1.1 18h1.7L6.4 3.9H4.6L17.8 20Z" /></svg><span><strong>Udostępnij na X</strong><span>{interview ? "Pokaż, jak zbudowana jest ta rozmowa — z analizą wywiadu" : "Pokaż, jak zbudowany jest ten przekaz — z kartą diagnozy"}</span></span></>;
}

/** „Udostępnij na X” — dla czytelników i dla zespołu (ten sam przycisk w kolejce). */
export function ShareSpinOnX({ id, spin }: { id: number; spin?: SpinDetailData }) {
  const [open, setOpen] = useState(false);
  const query = useQuery({ queryKey: ["clinic-spin", String(id)], queryFn: () => getSpin(id), enabled: open, staleTime: 0 });
  const data = query.data;
  return <>
    <button type="button" className="sc-share-cta" aria-haspopup="dialog" onClick={() => setOpen(true)}><ShareXCardContent /></button>
    <Dialog open={open} onClose={() => setOpen(false)} title="Diagnoza jako wątek na X">
      {query.isFetching ? <p>Sprawdzanie dostępności diagnozy…</p> : query.isError ? <p>Diagnoza jest niedostępna. Nie można przygotować publikacji.</p>
        : data?.status === "withdrawn" ? <p>Diagnoza została wycofana. Nie można jej udostępnić.</p>
        : data ? <ThreadPosts spin={data} /> : <p>Ładowanie diagnozy…</p>}
    </Dialog>
  </>;
}
