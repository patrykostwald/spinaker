"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { apiWrite, ApiError } from "../lib/api";
import { nb, replyBody, replyError, replyStatusMessage, type PositionPairData } from "../lib/positionPairs";
import "./position-pair.css";

/**
 * „Odpowiedz na zestawienie” (decyzja właściciela 13.10, API-v3 sekcja 0): POST /api/stanowiska/<id>/odpowiedz/
 * {text 10-600, token?}. Pole „Kod z wiadomości” = jednorazowy kod z e-maila po potwierdzeniu adresu (ważny 14 dni),
 * nie token z linku. 202 = przyjęta do sprawdzenia; 403 = nadawca niezweryfikowany; 404 = ten sam komunikat
 * co dla nieistniejącego zestawienia (para niepubliczna nie jest ujawniana). Natywne <dialog>.
 */
export function PositionPairReply({ pair, className = "sc-pp__rep" }: { pair: Pick<PositionPairData, "id" | "topic">; className?: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [code, setCode] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [message, setMessage] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const uid = useId();

  useEffect(() => {
    const el = dialog.current;
    if (!open || !el || el.open) return;
    if (typeof el.showModal === "function") el.showModal(); else el.setAttribute("open", "");
  }, [open]);
  const close = () => { const el = dialog.current; if (el?.open && typeof el.close === "function") el.close(); setOpen(false); };

  async function send(event: FormEvent) {
    event.preventDefault();
    const err = replyError(text, code);
    if (err) { setMessage(err); setState("error"); return; }
    setState("sending"); setMessage("");
    try {
      await apiWrite(`/api/stanowiska/${pair.id}/odpowiedz/`, replyBody(text, code));
      setState("sent"); setMessage(replyStatusMessage(202)); setText(""); setCode("");
    } catch (failure) {
      setMessage(replyStatusMessage(failure instanceof ApiError ? failure.status : 0)); setState("error");
    }
  }

  return <>
    <button type="button" className={className} aria-haspopup="dialog" onClick={() => { setState("idle"); setMessage(""); setOpen(true); }}>Odpowiedz jako osoba z zestawienia</button>
    {open && <dialog ref={dialog} className="sc-pp-rep" aria-labelledby={`${uid}-h`} onClose={() => setOpen(false)}
      onClick={event => { if (event.target === event.currentTarget) close(); }}>
      <h2 id={`${uid}-h`} className="sc-pp-rep__h">Odpowiedź osoby</h2>
      <p className="sc-pp-rep__rec">{nb(`Zestawienie „Wcześniej i teraz”: ${pair.topic}`)}</p>
      {state === "sent" ? <div className="sc-pp-rep__form" style={{ display: "grid", gap: 16 }}>
        <p className="sc-pp-rep__rec" role="status">{nb(message)}</p>
        <div className="sc-pp-rep__act"><button type="button" className="sc-pp-rep__ok" onClick={close}>Zamknij</button></div>
      </div> : <form onSubmit={send}>
        <label>{nb("Twoja odpowiedź (10-600 znaków). Pokażemy ją pod zestawieniem z datą, bez zmian w treści.")}
          <textarea required minLength={10} maxLength={600} rows={5} value={text} onChange={event => setText(event.target.value)} aria-describedby={`${uid}-n`} />
        </label>
        <label>Kod z wiadomości
          <input inputMode="text" autoComplete="one-time-code" maxLength={64} value={code} onChange={event => setCode(event.target.value)} />
        </label>
        <p id={`${uid}-n`} className="sc-pp-rep__note">{nb("Kod dostajesz e-mailem po potwierdzeniu adresu; jest jednorazowy i ważny 14 dni.")}</p>
        {state === "error" && message && <p role="alert" className="sc-pp-rep__err">{nb(message)}</p>}
        <div className="sc-pp-rep__act">
          <button type="submit" className="sc-pp-rep__ok" disabled={state === "sending"}>{state === "sending" ? "Wysyłam" : "Wyślij"}</button>
          <button type="button" className="sc-pp-rep__no" onClick={close}>Anuluj</button>
        </div>
      </form>}
    </dialog>}
  </>;
}
