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
      <p className="sc-xshare__hint">Wątek z {posts.length} wpisów. Pierwszy mieści się w limicie X i ma link do diagnozy — X pokaże jej kartę. Kolejne wklej jako odpowiedzi.</p>
      <div className="sc-xshare__actions">
        <a className="sc-xshare__link is-primary" href={xIntentUrl(posts[0])} target="_blank" rel="noopener noreferrer">Opublikuj 1/{posts.length} na X</a>
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

/** „Udostępnij na X” — dla czytelników i dla zespołu (ten sam przycisk w kolejce). */
export function ShareSpinOnX({ id, spin }: { id: number; spin?: SpinDetailData }) {
  const [open, setOpen] = useState(false);
  const query = useQuery({ queryKey: ["clinic-spin", String(id)], queryFn: () => getSpin(id), enabled: open && !spin });
  const data = spin ?? query.data;
  return <>
    <Button variant="quiet" size="sm" onClick={() => setOpen(true)}>Udostępnij na X</Button>
    <Dialog open={open} onClose={() => setOpen(false)} title="Diagnoza jako wątek na X">
      {data ? <ThreadPosts spin={data} /> : <p>Ładowanie diagnozy…</p>}
    </Dialog>
  </>;
}
