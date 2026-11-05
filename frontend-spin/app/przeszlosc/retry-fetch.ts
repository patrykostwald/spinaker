/**
 * Ponawianie odczytu danych przeszłość.today (runda person 1, 5.11.2026).
 *
 * Przy limicie zapytań (HTTP 429) albo chwilowym błędzie serwera (502, 503, 504) strony pokazywały od razu
 * „Nie udało się pobrać ...”, choć ponowienie po kilku sekundach zwykle się udaje. Zamiast przepisywać kilkadziesiąt
 * osobnych wywołań fetch, ten moduł owija window.fetch i dotyczy WYŁĄCZNIE odczytów (GET) pod /api/przeszlosc/.
 * Zapisy (POST) nigdy nie są ponawiane. Przerwanie przez AbortController jest respektowane. Czekanie bierze nagłówek
 * Retry-After; jeśli serwer każe czekać dłużej niż MAX_WAIT_MS, nie ponawiamy (i tak by się nie udało w rozsądnym czasie).
 */
export const RETRY_STATUSES = [429, 502, 503, 504];
export const MAX_RETRIES = 2;
export const MAX_WAIT_MS = 8000;
export const BASE_WAIT_MS = 1200;

type Init = { method?: string; signal?: AbortSignal | null } & Record<string, unknown>;
type FetchLike = (input: any, init?: any) => Promise<any>;
type Sleep = (ms: number, signal?: AbortSignal | null) => Promise<void>;

const urlOf = (input: unknown): string => {
  if (typeof input === 'string') return input;
  const o = (input ?? {}) as { href?: string; url?: string };
  return o.href ?? o.url ?? '';
};

const methodOf = (input: unknown, init?: Init): string => {
  const fromInput = typeof input === 'object' && input !== null ? (input as { method?: string }).method : undefined;
  return String(init?.method ?? fromInput ?? 'GET').toUpperCase();
};

/** Tylko odczyty (GET) pod /api/przeszlosc/ - względne albo z pełnym adresem tej samej ścieżki. */
export function isRetryable(input: unknown, init?: Init): boolean {
  if (methodOf(input, init) !== 'GET') return false;
  return urlOf(input).replace(/^https?:\/\/[^/]+/i, '').startsWith('/api/przeszlosc/');
}

/** Ile czekać przed kolejną próbą; null = nie ponawiać (serwer kazał czekać dłużej niż MAX_WAIT_MS). */
export function waitBeforeRetry(response: { headers?: { get?: (name: string) => string | null } }, attempt: number): number | null {
  const seconds = Number(response.headers?.get?.('Retry-After'));
  if (Number.isFinite(seconds) && seconds > 0) return seconds * 1000 > MAX_WAIT_MS ? null : seconds * 1000;
  return Math.min(BASE_WAIT_MS * (attempt + 1), MAX_WAIT_MS);
}

const abortError = () => { const e = new Error('Aborted'); e.name = 'AbortError'; return e; };

const defaultSleep: Sleep = (ms, signal) => new Promise(resolve => {
  const timer = setTimeout(resolve, ms);
  signal?.addEventListener?.('abort', () => { clearTimeout(timer); resolve(); }, { once: true });
});

export async function fetchWithRetry(base: FetchLike, input: unknown, init?: Init, sleep: Sleep = defaultSleep) {
  if (!isRetryable(input, init)) return base(input, init);
  const signal = init?.signal ?? null;
  for (let attempt = 0; ; attempt++) {
    let response: { status: number; headers?: { get?: (name: string) => string | null } };
    try {
      response = await base(input, init);
    } catch (error) {
      if (signal?.aborted || (error as { name?: string })?.name === 'AbortError' || attempt >= MAX_RETRIES) throw error;
      await sleep(BASE_WAIT_MS * (attempt + 1), signal);
      if (signal?.aborted) throw abortError();
      continue;
    }
    if (!RETRY_STATUSES.includes(response.status) || attempt >= MAX_RETRIES) return response;
    const wait = waitBeforeRetry(response, attempt);
    if (wait === null) return response;
    await sleep(wait, signal);
    if (signal?.aborted) throw abortError();
  }
}

type Host = { fetch: FetchLike; __ptRetryFetch?: boolean };

export function installRetryFetch(host: Host) {
  if (host.__ptRetryFetch) return;
  const original = host.fetch.bind(host);
  host.fetch = (input, init) => fetchWithRetry(original, input, init);
  host.__ptRetryFetch = true;
}
