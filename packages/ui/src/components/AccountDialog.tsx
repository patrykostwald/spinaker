"use client";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { apiWrite, ApiValidationError } from "../lib/api";
import { useAccount, type Account } from "../lib/account";
import { useFeature } from "../lib/features";
import { useRouter } from "next/navigation";
import { Dialog } from "./Dialog";
import { Button } from "../kit/Button";

type Mode = "login" | "register" | "reset";
export function AccountDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ACCOUNTS_ENABLED = useFeature('ACCOUNTS_ENABLED');
  const [mode, setMode] = useState<Mode>("login");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [googleConsent, setGoogleConsent] = useState(false);
  const [googleAdult, setGoogleAdult] = useState(false), [googleNewsletter, setGoogleNewsletter] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  const id = useId();
  const cache = useQueryClient();
  const account = useAccount();
  const router = useRouter();
  useEffect(() => { if (open) { setError(""); setFields({}); setNotice(""); setGoogleConsent(false); setGoogleAdult(false); setGoogleNewsletter(false); } }, [open]);
  function changeMode(next: Mode) { setMode(next); setError(""); setFields({}); setNotice(""); setGoogleConsent(false); setGoogleAdult(false); setGoogleNewsletter(false); requestAnimationFrame(() => formRef.current?.querySelector<HTMLInputElement>("input")?.focus()); }
  function field(name: string) { return { "aria-invalid": !!fields[name], "aria-describedby": fields[name] ? `${id}-${name}` : undefined }; }
  function fieldError(name: string) { return fields[name] ? <span id={`${id}-${name}`} className="sc-account-form__error" role="alert">{fields[name]}</span> : null; }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (pending) return;
    const form = new FormData(event.currentTarget); setPending(true); setError(""); setFields({});
    try {
      if (mode === "reset") {
        await apiWrite("/api/account/password-reset/", { email: form.get("email") });
        setNotice("Jeśli ten adres jest przypisany do konta, wyślemy link do zmiany hasła. Sprawdź też spam.");
      } else {
        const result = await apiWrite<Account>(`/api/account/${mode}/`, { username: form.get("username"), password: form.get("password"), ...(mode === "register" ? { email: form.get("email"), accepted_terms: form.get("accepted_terms") === "on", adult: form.get("adult") === "on", newsletter: form.get("newsletter") === "on" } : {}) });
        // Nowa sesja nie dziedziczy prywatnych danych poprzedniego czytelnika (zlecenie 055).
        const googleEnabled = result.google_enabled ?? cache.getQueryData<Account>(["account"])?.google_enabled;
        cache.clear(); cache.setQueryData<Account>(["account"], { ...result, google_enabled: googleEnabled });
        let firstVisit = true;
        try { firstVisit = localStorage.getItem(`sc-onboarding:${result.user?.id}`) !== "done"; } catch {}
        if (mode === "register") setNotice("Sprawdź pocztę, aby potwierdzić e-mail. Jeśli masz już konto, zaloguj się lub ustaw nowe hasło. Link potwierdzający działa przez 48 godzin.");
        else if (!result.user?.email_verified) setNotice("Jesteś zalogowany. Możesz czytać i zapisywać prywatnie. Aby publikować nitki i opinie, potwierdź e-mail.");
        else { onClose(); if (firstVisit) router.push("/konto"); }
      }
    } catch (reason) {
      const errors = reason instanceof ApiValidationError ? reason.fields : {};
      setFields(errors); setError(reason instanceof Error ? reason.message : "Nie udało się połączyć. Spróbuj ponownie.");
      requestAnimationFrame(() => formRef.current?.querySelector<HTMLInputElement>('[aria-invalid="true"]')?.focus());
    } finally { setPending(false); }
  }
  if (!ACCOUNTS_ENABLED) return null;
  return <Dialog open={open} onClose={onClose} title={mode === "login" ? "Zaloguj się" : mode === "register" ? "Załóż konto" : "Zmień hasło"}>
    {notice ? <div className="sc-account-form"><p role="status">{notice}</p>{mode === "login" ? <><Button href="/konto/potwierdz" variant="primary" size="md" fullWidth onClick={onClose}>Potwierdź e-mail</Button><Button type="button" variant="quiet" size="md" fullWidth onClick={onClose}>Na razie korzystam prywatnie</Button></> : <Button type="button" variant="primary" size="md" fullWidth onClick={() => changeMode("login")}>Przejdź do logowania</Button>}</div> : <>
    <form key={mode} ref={formRef} onSubmit={submit} className="sc-account-form" aria-busy={pending}>
      <p className="sc-t-body sc-text-2">{mode === "register" ? "Zapisuj prywatnie. Po potwierdzeniu e-maila publikuj nitki i opinie. Twoja nazwa będzie publiczna; e-mail pozostanie prywatny." : mode === "reset" ? "Podaj e-mail konta. Wyślemy link ważny przez godzinę." : "Wróć do swoich nitek i aktywności."}</p>
      {mode !== "reset" && <label>{mode === "login" ? "Nazwa użytkownika lub e-mail" : "Nazwa użytkownika"}<input required name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} minLength={mode === "register" ? 3 : undefined} maxLength={mode === "register" ? 30 : 254} pattern={mode === "register" ? "[A-Za-z0-9_]{3,30}" : undefined} {...field("username")} />{mode === "register" && <span className="sc-t-caption sc-text-2">3-30 znaków: litery bez polskich znaków, cyfry lub podkreślenie.</span>}{fieldError("username")}</label>}
      {mode !== "login" && <label>E-mail<input required name="email" type="email" maxLength={254} autoComplete="email" {...field("email")} />{fieldError("email")}</label>}
      {mode !== "reset" && <label>Hasło<input required name="password" type="password" maxLength={256} autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 8 : undefined} {...field("password")} />{mode === "register" && <span className="sc-t-caption sc-text-2">Minimum 8 znaków. Unikaj popularnych haseł i samej nazwy konta.</span>}{fieldError("password")}</label>}
      {mode === "register" && <><label className="sc-account-form__consent"><input required name="accepted_terms" type="checkbox" {...field("accepted_terms")} /><span>Akceptuję <Link href="/zasady-korzystania" target="_blank" rel="noopener noreferrer">Zasady korzystania (nowa karta)</Link>.</span>{fieldError("accepted_terms")}</label><label className="sc-account-form__consent"><input required name="adult" type="checkbox" {...field("adult")} /><span>Mam ukończone 18 lat.</span>{fieldError("adult")}</label><label className="sc-account-form__consent"><input name="newsletter" type="checkbox" /><span>Chcę otrzymywać newsletter e-mailem (opcjonalnie).</span></label><p className="sc-account-meta">Dane konta przetwarzamy w celu wykonania umowy. <Link href="/polityka-prywatnosci">Polityka prywatności</Link>.</p></>}
      {error && <p role="alert" className="sc-account-form__error">{Object.keys(fields).some(key => ["username", "email", "password", "accepted_terms", "adult"].includes(key)) ? "Sprawdź zaznaczone pola." : error}</p>}
      <Button type="submit" fullWidth variant="primary" size="md" loading={pending}>{mode === "login" ? "Zaloguj się" : mode === "register" ? "Utwórz konto" : "Wyślij link"}</Button>
      {mode === "login" && <Button type="button" fullWidth variant="quiet" size="md" disabled={pending} onClick={() => changeMode("reset")}>Nie pamiętam hasła</Button>}
      <Button type="button" fullWidth variant="quiet" size="md" disabled={pending} onClick={() => changeMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "Nie masz konta? Zarejestruj się" : "Wróć do logowania"}</Button>
    </form>
    {(account.data?.google_enabled || account.data?.x_enabled) && mode !== "reset" && <div className="sc-account-form sc-account-form__google"><p className="sc-t-caption sc-text-2">Pierwszy raz z Google lub X? Zaakceptuj zasady, aby utworzyć konto.</p><label className="sc-account-form__consent"><input type="checkbox" checked={googleConsent} onChange={event => setGoogleConsent(event.target.checked)} /><span>Akceptuję <Link href="/zasady-korzystania" target="_blank" rel="noopener noreferrer">Zasady korzystania</Link> (nowa karta).</span></label><label className="sc-account-form__consent"><input type="checkbox" checked={googleAdult} onChange={e => setGoogleAdult(e.target.checked)} /><span>Mam ukończone 18 lat.</span></label>{account.data?.google_enabled && <label className="sc-account-form__consent"><input type="checkbox" checked={googleNewsletter} onChange={e => setGoogleNewsletter(e.target.checked)} /><span>Chcę otrzymywać newsletter e-mailem (opcjonalnie, przy Google).</span></label>}
      {account.data?.google_enabled && <Button type="button" fullWidth variant="secondary" size="md" disabled={pending} onClick={() => { window.location.assign(`/api/account/google/start/${googleConsent && googleAdult ? `?accepted_terms=true&adult=true&newsletter=${googleNewsletter}` : ""}`); }}>Kontynuuj z Google</Button>}
      {account.data?.x_enabled && <Button type="button" fullWidth variant="secondary" size="md" disabled={pending} onClick={() => { window.location.assign(`/api/account/x/start/${googleConsent && googleAdult ? "?accepted_terms=true&adult=true" : ""}`); }}>Zaloguj przez X</Button>}</div>}
    </>}
  </Dialog>;
}

export function AccountControl() {
  const account = useAccount(); const cache = useQueryClient(); const [open, setOpen] = useState(false); const [pending, setPending] = useState(false); const [error, setError] = useState("");
  async function logout() { setPending(true); setError(""); try { await apiWrite("/api/account/logout/", {}); cache.clear(); cache.setQueryData<Account>(["account"], { authenticated: false, user: null, csrfToken: "" }); await cache.invalidateQueries({ queryKey: ["account"] }); } catch (reason) { setError(reason instanceof Error ? reason.message : "Nie udało się wylogować."); } finally { setPending(false); } }
  return <div className="sc-account-control">{account.data?.authenticated ? <><Link href="/konto" className="sc-account-control__name" title="Mój spin.clinic">Mój spin.clinic</Link>{account.data.user?.can_edit_threads ? <Link href="/editor" className="sc-account-control__name">{account.data.user?.is_staff ? "Zespół" : "Warsztat"}</Link> : null}<Button type="button" variant="quiet" size="sm" loading={pending} onClick={logout}>Wyloguj</Button></> : <Button type="button" variant="quiet" size="sm" disabled={account.isPending} onClick={() => setOpen(true)}>Zaloguj się</Button>}{error ? <span role="alert" className="sc-t-caption">{error}</span> : null}<AccountDialog open={open} onClose={() => setOpen(false)} /></div>;
}
