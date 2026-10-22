"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { apiWrite, ApiError } from "../lib/api";
import { nb, type PositionPairData } from "../lib/positionPairs";
import "./position-pair.css";

/**
 * „Zgłoś błąd lub sprostowanie” przy parze „Wcześniej i teraz”. Używa procedury z kontraktu (API-v3.md, sekcja 5):
 * POST /api/stanowiska/<id>/zgloszenie/ {reason >= 20 znaków, contact, is_subject}. Po zgłoszeniu para wraca do decyzji
 * człowieka i znika z API do czasu decyzji - formularz mówi o tym wprost. Natywne <dialog>: fokus, Esc, tło.
 */
export function PositionPairReport({ pair, className = "sc-pp__rep" }: { pair: Pick<PositionPairData, "id" | "topic" | "report_url">; className?: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [contact, setContact] = useState("");
  const [subject, setSubject] = useState(false);
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [error, setError] = useState("");
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
    if (reason.trim().length < 20) { setError("Opisz sprawę w co najmniej 20 znakach."); setState("error"); return; }
    setState("sending"); setError("");
    try {
      await apiWrite(pair.report_url, { reason: reason.trim(), contact: contact.trim(), is_subject: subject });
      setState("sent"); setReason(""); setContact("");
    } catch (failure) {
      const status = failure instanceof ApiError ? failure.status : 0;
      setError(status === 429 ? "Z tego adresu wysłano już za dużo zgłoszeń. Spróbuj za godzinę."
        : status === 404 ? "Ta para nie jest już publiczna. Odśwież stronę."
        : "Nie udało się wysłać. Spróbuj za chwilę.");
      setState("error");
    }
  }

  return <>
    <button type="button" className={className} aria-haspopup="dialog" onClick={() => { setState("idle"); setError(""); setOpen(true); }}>Zgłoś błąd lub sprostowanie</button>
    {open && <dialog ref={dialog} className="sc-pp-rep" aria-labelledby={`${uid}-h`} onClose={() => setOpen(false)}
      onClick={event => { if (event.target === event.currentTarget) close(); }}>
      <h2 id={`${uid}-h`} className="sc-pp-rep__h">Zgłoś błąd lub sprostowanie</h2>
      <p className="sc-pp-rep__rec">{nb(`Zestawienie „Wcześniej i teraz”: ${pair.topic}`)}</p>
      {state === "sent" ? <div className="sc-pp-rep__form" style={{ display: "grid", gap: 16 }}>
        <p className="sc-pp-rep__rec" role="status">{nb("Dziękujemy. Zgłoszenie trafiło do zespołu. To zestawienie wróciło do ponownej oceny przez człowieka i do czasu decyzji nie jest widoczne.")}</p>
        <div className="sc-pp-rep__act"><button type="button" className="sc-pp-rep__ok" onClick={close}>Zamknij</button></div>
      </div> : <form onSubmit={send}>
        <label>{nb("Co jest nieprawdziwe, ucięte albo wymaga kontekstu? Podaj źródło, jeśli je masz.")}
          <textarea required minLength={20} maxLength={1000} rows={4} value={reason} onChange={event => setReason(event.target.value)} aria-describedby={`${uid}-n`} />
        </label>
        <label>{nb("E-mail, jeśli chcesz odpowiedź (nieobowiązkowo)")}
          <input type="email" maxLength={200} value={contact} onChange={event => setContact(event.target.value)} autoComplete="email" />
        </label>
        <label className="sc-pp-rep__chk"><input type="checkbox" checked={subject} onChange={event => setSubject(event.target.checked)} />
          <span>{nb("Zgłaszam jako osoba, której dotyczą te wypowiedzi")}</span></label>
        <p id={`${uid}-n`} className="sc-pp-rep__note">{nb("Co najmniej 20 znaków. Po zgłoszeniu zestawienie wraca do decyzji człowieka i do czasu decyzji nie jest widoczne.")}</p>
        {state === "error" && error && <p role="alert" className="sc-pp-rep__err">{error}</p>}
        <div className="sc-pp-rep__act">
          <button type="submit" className="sc-pp-rep__ok" disabled={state === "sending"}>{state === "sending" ? "Wysyłam" : "Wyślij"}</button>
          <button type="button" className="sc-pp-rep__no" onClick={close}>Anuluj</button>
        </div>
      </form>}
    </dialog>}
  </>;
}
