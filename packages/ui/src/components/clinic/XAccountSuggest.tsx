"use client";

import { useId, useState, type FormEvent } from "react";
import { Button } from "../../kit";
import { suggestXAccount } from "../../lib/clinic";

/** „Zasugeruj konto X”: czytelnik wkleja link do profilu, zespół weryfikuje go oficjalnym dowodem. */
export function XAccountSuggest({ figureId, name }: { figureId: number; name: string }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true); setError("");
    try {
      const result = await suggestXAccount(figureId, url.trim());
      setMessage(result.status === "received"
        ? `Dziękujemy. Sprawdzimy, czy @${result.handle} to oficjalne konto, zanim zaczniemy je czytać.`
        : `Ktoś już zgłosił @${result.handle} — czeka na weryfikację.`);
      setOpen(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się wysłać sugestii.");
    } finally { setPending(false); }
  }

  if (message) return <span className="sc-x-suggest__done" role="status">{message}</span>;
  if (!open) return <Button size="sm" variant="quiet" onClick={() => setOpen(true)}>Zasugeruj konto X<span className="sr-only"> dla: {name}</span></Button>;
  return (
    <form className="sc-x-suggest" onSubmit={submit}>
      <label htmlFor={id}>Link do profilu X osoby: {name}</label>
      <div className="sc-x-suggest__row">
        <input id={id} type="url" required inputMode="url" placeholder="https://x.com/nazwa_konta" value={url} maxLength={300}
               onChange={event => setUrl(event.target.value)} />
        <Button type="submit" size="sm" variant="primary" loading={pending} disabled={pending || !url.trim()}>Wyślij</Button>
        <Button type="button" size="sm" variant="quiet" onClick={() => setOpen(false)}>Anuluj</Button>
      </div>
      {error && <p role="alert" className="sc-x-suggest__error">{error}</p>}
    </form>
  );
}
