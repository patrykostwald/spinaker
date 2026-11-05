"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "../kit/Button";
import { buildCitation } from "../lib/cite";
import { Dialog } from "./Dialog";

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    try { return document.execCommand("copy"); } finally { area.remove(); }
  }
}

/**
 * Jeden wzorzec udostępniania w całym serwisie: „Cytuj” (zapis z permalinkiem, datą publikacji i datą dostępu)
 * oraz „Udostępnij” (okno: kopiuj link, udostępnianie systemowe, publikacja na X; `extra` — np. wątek na X diagnozy).
 */
export function CiteShare({ title, path, author, publishedAt, updatedAt, kind, shareText, extra, className }: {
  title: string; path: string; author?: string; publishedAt?: string | null; updatedAt?: string | null; kind?: string; shareText?: string;
  extra?: ReactNode; className?: string;
}) {
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [native, setNative] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => { setNative(typeof navigator.share === "function"); return () => clearTimeout(timer.current); }, []);
  const say = (message: string) => {
    setStatus(message);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setStatus(""), 4000);
  };
  const permalink = () => new URL(path, window.location.origin).toString();
  const intent = () => `https://x.com/intent/tweet?${new URLSearchParams({ text: shareText ?? title, url: permalink() })}`;
  return <div className={["sc-cite-share", className].filter(Boolean).join(" ")}>
    <Button type="button" variant="secondary" size="md" onClick={async () => {
      const ok = await copyText(buildCitation({ author, title, publishedAt, updatedAt, kind, url: permalink() }));
      say(ok ? "Skopiowano cytat do schowka." : "Nie udało się skopiować cytatu.");
    }}>Cytuj</Button>
    <Button type="button" variant="secondary" size="md" aria-haspopup="dialog" onClick={() => setOpen(true)}>Udostępnij</Button>
    <span className="sc-cite-share__status sc-t-caption sc-text-2" role="status" aria-live="polite">{open ? "" : status}</span>
    <Dialog open={open} onClose={() => setOpen(false)} title="Udostępnij">
      <div className="sc-cite-share__dialog">
        <p className="sc-cite-share__title">{title}</p>
        <input className="sc-cite-share__link" readOnly aria-label="Adres do udostępnienia" value={open ? permalink() : ""} onFocus={event => event.currentTarget.select()} />
        <div className="sc-cite-share__actions">
          <Button type="button" variant="primary" size="md" onClick={async () => say(await copyText(permalink()) ? "Skopiowano link do schowka." : "Nie udało się skopiować linku.")}>Kopiuj link</Button>
          {native ? <Button type="button" variant="secondary" size="md" onClick={async () => {
            try { await navigator.share({ title, text: shareText ?? title, url: permalink() }); setOpen(false); } catch { /* anulowano */ }
          }}>Udostępnij w aplikacji</Button> : null}
          {extra ? null : <a className="sc-xshare__link" href={open ? intent() : undefined} target="_blank" rel="noopener noreferrer">Opublikuj na X</a>}
        </div>
        <p className="sc-t-caption sc-text-2" role="status" aria-live="polite">{open ? status : ""}</p>
        {extra}
      </div>
    </Dialog>
  </div>;
}
