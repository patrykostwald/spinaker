"use client";
import { useId, useState, type FormEvent } from "react";
import Link from "next/link";
import { Button } from "../kit/Button";
import { apiWrite } from "../lib/api";
import { Dialog } from "./Dialog";

export type CorrectionKind = "diagnosis" | "interview" | "figure" | "message";
type CorrectionType = "correction" | "error" | "objection";

const TYPE_LABELS: Record<CorrectionType, string> = {
  correction: "Sprostowanie / odpowiedź", error: "Zgłoszenie błędu", objection: "Sprzeciw wobec danych o osobie",
};
const MIN = 20;
const MAX = 2000;

/**
 * „Sprostowanie / odpowiedź” i „Zgłoś błąd”: formularz zapisuje zgłoszenie do przeglądu przez zespół
 * (POST /api/corrections/). Nic nie jest publikowane ani wysyłane automatycznie.
 */
export function CorrectionForm({ kind, targetId, type, label, className }: {
  kind: CorrectionKind; targetId: number; type: CorrectionType; label: string; className?: string;
}) {
  const uid = useId();
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<CorrectionType>(type);
  const [relation, setRelation] = useState<"subject" | "other">(type === "correction" ? "subject" : "other");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [trap, setTrap] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [reference, setReference] = useState("");
  const types: CorrectionType[] = kind === "figure" ? ["error", "correction", "objection"] : ["correction", "error"];
  const valid = message.trim().length >= MIN && message.length <= MAX && /\S+@\S+\.\S+/.test(email);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || pending) return;
    setPending(true); setError("");
    try {
      const result = await apiWrite<{ status: string; reference?: string }>("/api/corrections/", {
        target_kind: kind, target_id: targetId, request_type: chosen, relation, name: name.trim(), email: email.trim(),
        message: message.trim(), website: trap,
      });
      setReference(result.reference ?? "przyjęte");
      setMessage("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się wysłać zgłoszenia.");
    } finally { setPending(false); }
  }

  return <>
    <Button type="button" variant="secondary" size="md" className={className} aria-haspopup="dialog" onClick={() => { setOpen(true); setReference(""); setChosen(type); }}>{label}</Button>
    <Dialog open={open} onClose={() => setOpen(false)} title={label}>
      {reference ? <div className="sc-correction" role="status">
        <p><strong>Dziękujemy. Zgłoszenie {reference} trafiło do redakcji.</strong></p>
        <p>Nic nie zostało jeszcze opublikowane ani zmienione: zespół sprawdzi sprawę i odpowie na podany adres.</p>
        <Button type="button" variant="primary" size="md" onClick={() => setOpen(false)}>Zamknij</Button>
      </div> : <form className="sc-correction" onSubmit={submit} noValidate>
        <p className="sc-correction__lead">Autor wypowiedzi lub osoba, której dotyczy analiza, może przesłać odpowiedź. Zgłoszenie trafia do zespołu do sprawdzenia: <strong>nic nie jest publikowane ani wysyłane automatycznie</strong>. Potwierdzimy odbiór zgłoszenia.</p>
        <label htmlFor={`${uid}-type`}>Rodzaj zgłoszenia
          <select id={`${uid}-type`} value={chosen} onChange={event => setChosen(event.target.value as CorrectionType)}>
            {types.map(item => <option key={item} value={item}>{TYPE_LABELS[item]}</option>)}
          </select>
        </label>
        <fieldset className="sc-correction__relation"><legend>Kim jesteś?</legend>
          <label><input type="radio" name={`${uid}-rel`} checked={relation === "subject"} onChange={() => setRelation("subject")} /> Autor wypowiedzi lub osoba, której dotyczy</label>
          <label><input type="radio" name={`${uid}-rel`} checked={relation === "other"} onChange={() => setRelation("other")} /> Inna osoba</label>
        </fieldset>
        <label htmlFor={`${uid}-name`}>Imię i nazwisko (opcjonalnie)
          <input id={`${uid}-name`} value={name} maxLength={120} autoComplete="name" onChange={event => setName(event.target.value)} />
        </label>
        <label htmlFor={`${uid}-email`}>Adres e-mail do odpowiedzi
          <input id={`${uid}-email`} type="email" required value={email} maxLength={254} autoComplete="email" onChange={event => setEmail(event.target.value)} />
        </label>
        <label htmlFor={`${uid}-msg`}>Treść ({MIN}–{MAX} znaków)
          <textarea id={`${uid}-msg`} required rows={6} value={message} maxLength={MAX} onChange={event => setMessage(event.target.value)} aria-describedby={`${uid}-count`} />
        </label>
        <p id={`${uid}-count`} className="sc-t-caption sc-text-2">{message.trim().length}/{MAX}{message.trim().length < MIN ? ` · jeszcze minimum ${MIN - message.trim().length}` : ""}</p>
        <div className="sc-correction__trap" aria-hidden="true"><label>Nie wypełniaj tego pola<input tabIndex={-1} autoComplete="off" value={trap} onChange={event => setTrap(event.target.value)} /></label></div>
        <p className="sc-t-caption sc-text-2">Adres e-mail służy wyłącznie do odpowiedzi w tej sprawie (<Link href="/polityka-prywatnosci#osoby">Prywatność</Link>). Zgłoszenie przechowujemy do 3 lat.</p>
        {error ? <p role="alert" className="sc-correction__error">{error}</p> : null}
        <div className="sc-correction__actions">
          <Button type="submit" variant="primary" size="md" loading={pending} disabled={!valid || pending}>Wyślij do redakcji</Button>
          <Button type="button" variant="quiet" size="md" onClick={() => setOpen(false)}>Anuluj</Button>
        </div>
      </form>}
    </Dialog>
  </>;
}
