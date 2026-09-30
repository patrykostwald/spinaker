/** Przełączniki funkcji. Nitki czytelników czekają na fazę II — włącza je NEXT_PUBLIC_THREADS_ENABLED=true. */
export const THREADS_ENABLED = process.env.NEXT_PUBLIC_THREADS_ENABLED === "true";
/** Konta czytelników (logowanie, reakcje, komentarze, ulubione) — wyłączone na start; włącza NEXT_PUBLIC_ACCOUNTS_ENABLED=true. */
export const ACCOUNTS_ENABLED = process.env.NEXT_PUBLIC_ACCOUNTS_ENABLED === "true";
export const PUSH_ENABLED = process.env.NEXT_PUBLIC_PUSH_ENABLED === "true";
/** Aplikacja (instalacja z przeglądarki, service worker, push) — ukryta publicznie do decyzji właściciela; włącza NEXT_PUBLIC_APP_ENABLED=true. */
export const APP_ENABLED = process.env.NEXT_PUBLIC_APP_ENABLED === "true";
