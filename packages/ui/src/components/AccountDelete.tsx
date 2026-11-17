"use client";
import { useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiWrite, ApiValidationError } from "../lib/api";
import { useAccount } from "../lib/account";
import { useFeature } from "../lib/features";
import { Button } from "../kit/Button";
import { AccountDialog } from "./AccountDialog";
import { Loading } from "../kit/Loading";

export function AccountDelete() {
  const account = useAccount(), threadsEnabled = useFeature("THREADS_ENABLED");
  const cache = useQueryClient();
  const formRef = useRef<HTMLFormElement>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [login, setLogin] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (pending) return;
    const form = new FormData(event.currentTarget); setPending(true); setError(""); setFields({});
    try {
      await apiWrite("/api/account/delete/", { password: form.get("password"), confirm: form.get("confirm") });
      cache.clear(); window.location.assign("/");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się usunąć konta. Spróbuj ponownie.");
      setFields(reason instanceof ApiValidationError ? reason.fields : {});
      requestAnimationFrame(() => formRef.current?.querySelector<HTMLInputElement>('[aria-invalid="true"]')?.focus());
    } finally { setPending(false); }
  }
  return <main className="sc-account-recovery"><h1 className="sc-t-title-m">Usuń konto</h1>{account.isPending ? <p role="status"><Loading label="Wczytywanie" /></p> : !account.data?.authenticated ? <Button type="button" variant="primary" size="md" onClick={() => setLogin(true)}>Zaloguj się</Button> : <form ref={formRef} onSubmit={submit} className="sc-account-form" aria-busy={pending}>
    <p>Usuniemy Twoje dane osobowe oraz konto. {threadsEnabled ? "Twoje publiczne i prywatne spinki, opinie, ulubione i obserwowani również znikną." : "Twoje komentarze, opinie, ulubione i obserwowani również znikną."} Tego nie można cofnąć.</p>
    <Button href="/api/account/export/" variant="secondary" size="md">Pobierz kopię danych (JSON)</Button>
    <label>Hasło<input name="password" required type="password" autoComplete="current-password" maxLength={256} aria-invalid={!!fields.password} aria-describedby={fields.password ? "delete-password-error" : "delete-password-help"} /><span id="delete-password-help" className="sc-t-caption sc-text-2">Konto z Google bez hasła? Ustaw hasło przez „Nie pamiętam hasła” w oknie logowania.</span>{fields.password && <span id="delete-password-error" role="alert" className="sc-account-form__error">{fields.password}</span>}</label>
    <Button type="button" variant="quiet" size="md" disabled={pending} onClick={() => setLogin(true)}>Ustaw lub przypomnij hasło</Button>
    <label>Aby potwierdzić, wpisz USUŃ<input name="confirm" required pattern="USUŃ" autoComplete="off" spellCheck={false} aria-invalid={!!fields.confirm} aria-describedby={fields.confirm ? "delete-confirm-error" : undefined} />{fields.confirm && <span id="delete-confirm-error" role="alert" className="sc-account-form__error">{fields.confirm}</span>}</label>
    {error && <p role="alert" className="sc-account-form__error">{fields.password || fields.confirm ? "Sprawdź zaznaczone pola." : error}</p>}
    <Button type="submit" variant="danger" size="md" loading={pending}>{threadsEnabled ? "Usuń konto i moje spinki" : "Usuń konto i moje dane"}</Button><Button href="/konto" variant="quiet" size="md">Wróć do konta</Button>
  </form>}<AccountDialog open={login} onClose={() => setLogin(false)} /></main>;
}
