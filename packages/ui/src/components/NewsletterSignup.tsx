"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { apiWrite } from "../lib/api";
import { Button } from "../kit/Button";

/** Ta sama treść zgody co w backendzie (news/newsletter.py, CONSENT_TEXT) — zapisujemy jej wersję przy każdym zapisie. */
export const NEWSLETTER_CONSENT =
  "Zgadzam się na otrzymywanie od spin.clinic (iapply sp. z o.o.) e-maili o starcie serwisu i jego nowościach. Mogę się wypisać w każdej chwili jednym kliknięciem.";

type State = { kind: "idle" | "sending" | "done" | "error"; message?: string };

/**
 * Zapis na powiadomienie o starcie: e-mail + zgoda, potem mail z linkiem potwierdzającym (podwójna zgoda).
 * `source` mówi, skąd przyszedł zapis (home, klinika, o-nas…) — do statystyk w panelu.
 */
export function NewsletterSignup({ source, compact = false }: { source: string; compact?: boolean }) {
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [website, setWebsite] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!consent) {
      setState({ kind: "error", message: "Zaznacz zgodę na otrzymywanie wiadomości." });
      return;
    }
    setState({ kind: "sending" });
    try {
      const result = await apiWrite<{ detail: string }>("/api/newsletter/subscribe/", { email, consent, source, website });
      setState({ kind: "done", message: result.detail });
    } catch (error) {
      setState({ kind: "error", message: error instanceof Error ? error.message : "Nie udało się zapisać. Spróbuj ponownie." });
    }
  }

  return (
    <section className="sc-newsletter" data-compact={compact || undefined} aria-labelledby={`newsletter-${source}`}>
      <div className="sc-newsletter__text">
        <p className="sc-clinic-kicker">Newsletter</p>
        <h2 id={`newsletter-${source}`}>Powiadomimy Cię o starcie pełnej wersji</h2>
        <p>
          spin.clinic działa w wersji beta. Zostaw e-mail — napiszemy, gdy wystartuje pełna wersja, i od czasu do czasu o najważniejszych nowościach.
          Bez spamu; nie sprzedajemy ani nie udostępniamy adresów do cudzego marketingu.
        </p>
      </div>
      {state.kind === "done" ? (
        <p className="sc-newsletter__done" role="status">✓ {state.message}</p>
      ) : (
        <form className="sc-newsletter__form" onSubmit={submit} noValidate>
          <div className="sc-newsletter__row">
            <label className="sc-sr-only" htmlFor={`newsletter-email-${source}`}>Adres e-mail</label>
            <input className="sc-input" id={`newsletter-email-${source}`} type="email" required autoComplete="email" placeholder="twoj@adres.pl"
              value={email} onChange={event => setEmail(event.target.value)} />
            <Button type="submit" variant="primary" loading={state.kind === "sending"}>{state.kind === "sending" ? "Zapisuję…" : "Zapisz mnie"}</Button>
          </div>
          {/* Pole-pułapka: ludzie go nie widzą, boty je wypełniają. */}
          <input className="sc-newsletter__trap" tabIndex={-1} autoComplete="off" aria-hidden="true" name="website"
            value={website} onChange={event => setWebsite(event.target.value)} />
          <label className="sc-newsletter__consent">
            <input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />
            <span>{NEWSLETTER_CONSENT} <Link href="/polityka-prywatnosci">Prywatność</Link></span>
          </label>
          {state.kind === "error" && <p className="sc-newsletter__error" role="alert">{state.message}</p>}
        </form>
      )}
    </section>
  );
}
