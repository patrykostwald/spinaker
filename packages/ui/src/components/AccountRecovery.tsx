"use client";
import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { apiWrite, ApiValidationError } from "../lib/api";
import { useAccount, type Account } from "../lib/account";
import { Button } from "../kit/Button";
import { AccountDialog } from "./AccountDialog";

export function AccountRecovery({ mode }: { mode: "verify" | "password" }) {
  const params = useSearchParams();
  const account = useAccount();
  const cache = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [notice, setNotice] = useState("");
  const [done, setDone] = useState(false);
  const [login, setLogin] = useState(false);
  const [profileFields, setProfileFields] = useState<Record<string, string>>({});
  const profileFormRef = useRef<HTMLFormElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const googleError = params.get("google_error") === "1";
  const token = params.get("token");
  const uid = params.get("uid");
  const validLink = !!token && (mode === "verify" || !!uid);
  const needsProfile = mode === "verify" && !token && account.data?.authenticated && !account.data.user?.accepted_terms_version;
  function profileField(name: string) { return { "aria-invalid": !!profileFields[name], "aria-describedby": profileFields[name] ? `profile-${name}-error` : undefined }; }
  function profileError(name: string) { return profileFields[name] && <span id={`profile-${name}-error`} role="alert" className="sc-account-form__error">{profileFields[name]}</span>; }
  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (pending) return;
    const form = new FormData(event.currentTarget); setPending(true); setError(""); setProfileFields({});
    try {
      const result = await apiWrite<Account>("/api/account/me/", { email: form.get("email"), password: form.get("password"), accepted_terms: form.get("accepted_terms") === "on", accepted_privacy: form.get("accepted_privacy") === "on" }, "PATCH");
      cache.setQueryData<Account>(["account"], previous => ({ ...previous, ...result, google_enabled: result.google_enabled ?? previous?.google_enabled }));
      await cache.invalidateQueries({ queryKey: ["account"] });
      setNotice("Dane zapisane. Sprawdź pocztę i potwierdź e-mail linkiem z wiadomości.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się zapisać. Spróbuj ponownie.");
      setProfileFields(reason instanceof ApiValidationError ? reason.fields : {});
      requestAnimationFrame(() => profileFormRef.current?.querySelector<HTMLInputElement>('[aria-invalid="true"]')?.focus());
    } finally { setPending(false); }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (pending) return;
    const form = new FormData(event.currentTarget);
    setPending(true); setError(""); setPasswordError(""); setNotice("");
    try {
      await apiWrite(mode === "verify" ? "/api/account/verify-email/" : "/api/account/password-reset/confirm/", mode === "verify" ? { token } : { uid, token, password: form.get("password") });
      await cache.invalidateQueries({ queryKey: ["account"] });
      setDone(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się zapisać. Spróbuj ponownie.");
      if (reason instanceof ApiValidationError && reason.fields.password) { setPasswordError(reason.fields.password); requestAnimationFrame(() => passwordRef.current?.focus()); }
    } finally { setPending(false); }
  }
  async function resend() {
    setPending(true); setError("");
    try { await apiWrite("/api/account/verify-email/resend/", {}); setNotice("Jeśli adres wymaga potwierdzenia, wyślemy nowy link. Sprawdź też spam."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Spróbuj ponownie za chwilę."); }
    finally { setPending(false); }
  }
  return <main className="sc-account-recovery"><h1 className="sc-t-title-m">{googleError ? "Logowanie Google" : mode === "verify" ? "Potwierdź e-mail" : "Ustaw nowe hasło"}</h1>
    {done ? <div className="sc-account-form"><p role="status">{mode === "verify" ? "E-mail potwierdzony. Możesz publikować tropy i opinie." : "Hasło zmienione. Zaloguj się nowym hasłem."}</p>{mode === "verify" && account.data?.authenticated ? <Button href="/konto" variant="primary" size="md">Przejdź do konta</Button> : <Button type="button" variant="primary" size="md" onClick={() => setLogin(true)}>Zaloguj się</Button>}</div> : <div className="sc-account-form">
      {googleError ? <p role="alert">Nie udało się zalogować przez Google. Spróbuj ponownie lub użyj e-maila i hasła. Przy pierwszym logowaniu zaakceptuj zasady i politykę prywatności.</p> : needsProfile ? <form ref={profileFormRef} onSubmit={saveProfile} className="sc-account-form" aria-busy={pending}>
        <p>Uzupełnij konto, aby publikować tropy i opinie. Nadal możesz czytać i zapisywać prywatnie.</p>
        <label>E-mail<input required type="email" name="email" autoComplete="email" maxLength={254} defaultValue={account.data?.user?.email || ""} {...profileField("email")} />{profileError("email")}</label>
        <label>Aktualne hasło<input required type="password" name="password" autoComplete="current-password" maxLength={256} {...profileField("password")} />{profileError("password")}</label>
        <label className="sc-account-form__consent"><input required type="checkbox" name="accepted_terms" {...profileField("accepted_terms")} /><span>Akceptuję <Link href="/zasady-korzystania" target="_blank" rel="noopener noreferrer">Zasady korzystania (nowa karta)</Link>.</span>{profileError("accepted_terms")}</label>
        <label className="sc-account-form__consent"><input required type="checkbox" name="accepted_privacy" {...profileField("accepted_privacy")} /><span>Akceptuję <Link href="/polityka-prywatnosci" target="_blank" rel="noopener noreferrer">Politykę prywatności (nowa karta)</Link>.</span>{profileError("accepted_privacy")}</label>
        <Button type="submit" variant="primary" size="md" fullWidth loading={pending}>Zapisz i wyślij link</Button>
      </form> : validLink ? <form onSubmit={submit} className="sc-account-form" aria-busy={pending}>
        <p className="sc-text-2">{mode === "verify" ? "Potwierdź, że ten adres należy do Ciebie. Link jest ważny przez 48 godzin." : "Wybierz hasło, którego nie używasz w innych serwisach. Link jest ważny przez godzinę."}</p>
        {mode === "password" && <label>Nowe hasło<input ref={passwordRef} name="password" required type="password" autoComplete="new-password" minLength={8} maxLength={256} aria-invalid={!!passwordError} aria-describedby={passwordError ? "new-password-error" : "new-password-help"} /><span id="new-password-help" className="sc-t-caption sc-text-2">Minimum 8 znaków. Unikaj popularnych haseł.</span>{passwordError && <span id="new-password-error" role="alert" className="sc-account-form__error">{passwordError}</span>}</label>}
        <Button type="submit" variant="primary" size="md" fullWidth loading={pending}>{mode === "verify" ? "Potwierdź e-mail" : "Zapisz nowe hasło"}</Button>
      </form> : mode === "verify" && account.data?.authenticated ? <p>{account.data.user?.email_verified ? "Twój e-mail jest już potwierdzony." : "Sprawdź pocztę i potwierdź e-mail. Możesz też poprosić o nowy link."}</p> : <p role="alert">W tym linku brakuje danych. Otwórz cały link z wiadomości lub poproś o nowy.</p>}
      {error && !passwordError && <p role="alert" className="sc-account-form__error">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!needsProfile && (mode === "verify" && account.data?.authenticated ? account.data.user?.email_verified ? <Button href="/konto" variant="quiet" size="md">Wróć do konta</Button> : <Button type="button" variant="quiet" size="md" disabled={pending} onClick={resend}>Wyślij nowy link</Button> : <Button type="button" variant="quiet" size="md" disabled={pending} onClick={() => setLogin(true)}>{mode === "password" ? "Poproś o nowy link w „Nie pamiętam hasła”" : "Zaloguj się, aby wysłać nowy link"}</Button>)}
    </div>}
    <AccountDialog open={login} onClose={() => setLogin(false)} />
  </main>;
}
