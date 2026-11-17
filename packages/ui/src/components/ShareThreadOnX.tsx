"use client";

import { useState } from "react";
import { Button } from "../kit";
import { buildStoryThread, type StoryThread } from "../lib/xStory";
import { xIntentUrl } from "../lib/xThread";
import { Dialog } from "./Dialog";

/**
 * Cała nitka jako wątek na X: 1/N - tytuł, opis i link do nitki; dalej po jednym wpisie na box
 * z linkiem do oryginału (X pokaże kartę ze zdjęciem strony źródła). Kolejne wpisy wkleja się jako odpowiedzi.
 */
export function ShareThreadOnX({ thread }: { thread: StoryThread }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<number | null>(null);
  const posts = open ? buildStoryThread(thread) : [];
  async function copy(text: string, index: number) {
    try { await navigator.clipboard.writeText(text); setCopied(index); } catch { setCopied(null); }
  }
  return <>
    <Button variant="quiet" size="sm" onClick={() => setOpen(true)}>Udostępnij spinkę na X</Button>
    <Dialog open={open} onClose={() => setOpen(false)} title="Spinka jako wątek na X">
      <div className="sc-xshare">
        <p className="sc-xshare__hint">
          Wątek z {posts.length} wpisów. Pierwszy to tytuł i opis z linkiem do nitki; każdy kolejny to jeden box z linkiem do oryginału -
          X pokaże przy nim kartę ze zdjęciem. Opublikuj pierwszy, a kolejne wklej jako odpowiedzi.
        </p>
        <div className="sc-xshare__actions">
          {posts[0] && <a className="sc-xshare__link is-primary" href={xIntentUrl(posts[0])} target="_blank" rel="noopener noreferrer">Opublikuj 1/{posts.length} na X</a>}
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
    </Dialog>
  </>;
}
