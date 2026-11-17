"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "../../kit";
import { getSpin, type SpinDetailData } from "../../lib/clinic";
import { buildXThread, xIntentUrl } from "../../lib/xThread";
import { Dialog } from "../Dialog";
import { Loading } from "../../kit/Loading";

function ThreadPosts({ spin }: { spin: SpinDetailData }) {
  const posts = buildXThread(spin);
  const card = `/api/clinic/spins/${spin.id}/card.png`;
  const [copied, setCopied] = useState<string | null>(null);
  async function copy(text: string, key: string) {
    try { await navigator.clipboard.writeText(text); setCopied(key); } catch { setCopied(null); }
  }
  async function copyImage() {
    try {
      const blob = await (await fetch(card)).blob();
      await navigator.clipboard.write([new ClipboardItem({ [blob.type || "image/png"]: blob })]);
      setCopied("image");
    } catch { setCopied("image-failed"); }
  }
  return (
    <div className="sc-xshare">
      {/* Grafika z wynikami jest głównym elementem udostępnienia (właściciel 2.10.2026: ludzie są wzrokowcami). */}
      <figure className="sc-xshare__card">
        {/* eslint-disable-next-line @next/next/no-img-element -- karta generowana przez API */}
        <img src={card} alt={`Karta diagnozy: ${spin.headline}`} width={1600} height={900} />
      </figure>
      <div className="sc-xshare__actions">
        <a className="sc-xshare__link is-primary" href={xIntentUrl(posts[0])} target="_blank" rel="noopener noreferrer">{posts.length === 1 ? "Opublikuj na X" : `Opublikuj 1/${posts.length} na X`}</a>
        <a className="sc-xshare__link" href={card} download={`spin-clinic-diagnoza-${spin.id}.png`}>Pobierz grafikę</a>
        <button type="button" className="sc-xshare__link" onClick={copyImage}>{copied === "image" ? "Grafika skopiowana" : copied === "image-failed" ? "Użyj „Pobierz grafikę”" : "Kopiuj grafikę"}</button>
        <a className="sc-xshare__link" href={xIntentUrl(posts[0], spin.post.id)} target="_blank" rel="noopener noreferrer">Odpowiedz pod wpisem @{spin.author.handle}</a>
      </div>
      <p className="sc-xshare__hint">Link w poście pokaże tę kartę na X. Możesz też dołączyć ją jako zdjęcie: pobierz albo skopiuj grafikę i wklej do posta.</p>
      <ol className="sc-xshare__posts">
        {posts.map((post, index) => (
          <li key={index}>
            <p>{post}</p>
            <button type="button" onClick={() => copy(post, `post-${index}`)}>{copied === `post-${index}` ? "Skopiowano" : "Kopiuj tekst"}</button>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function ShareXCardContent({ interview = false }: { interview?: boolean }) {
  return <><svg className="sc-share-cta__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path fill="currentColor" d="M18.9 2H22l-6.8 7.8L23.2 22h-6.3L12 14.6 5.5 22H2.3l7.9-9L.8 2h6.5l4.5 6.8L18.9 2Zm-1.1 18h1.7L6.4 3.9H4.6L17.8 20Z" /></svg><span><strong>Udostępnij na X</strong><span>{interview ? "Pokaż, jak zbudowana jest ta rozmowa - z analizą wywiadu" : "Pokaż, jak zbudowany jest ten przekaz - z kartą diagnozy"}</span></span></>;
}

/** „Udostępnij na X” - dla czytelników i dla zespołu (ten sam przycisk w kolejce). */
export function ShareSpinOnX({ id, spin }: { id: number; spin?: SpinDetailData }) {
  const [open, setOpen] = useState(false);
  // Osobny klucz: odświeżenie przy otwarciu nie może przełączyć strony diagnozy (ten sam klucz) w „Wczytujemy…”,
  // bo strona odmontowuje wtedy przycisk razem ze stanem okna i okno nigdy się nie otwiera.
  const query = useQuery({ queryKey: ["clinic-spin-share", String(id)], queryFn: () => getSpin(id), enabled: open, staleTime: 0 });
  const data = query.data;
  return <>
    <button type="button" className="sc-share-cta" aria-haspopup="dialog" onClick={() => setOpen(true)}><ShareXCardContent /></button>
    <Dialog open={open} onClose={() => setOpen(false)} title="Udostępnij diagnozę na X">
      {query.isFetching ? <p>Sprawdzanie dostępności diagnozy…</p> : query.isError ? <p>Diagnoza jest niedostępna. Nie można przygotować publikacji.</p>
        : data?.status === "withdrawn" ? <p>Diagnoza została wycofana. Nie można jej udostępnić.</p>
        : data ? <ThreadPosts spin={data} /> : <p><Loading label="Ładowanie diagnozy" /></p>}
    </Dialog>
  </>;
}
