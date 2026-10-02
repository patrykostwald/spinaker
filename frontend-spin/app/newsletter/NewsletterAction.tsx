'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { apiWrite } from '@spin-clinic/ui';

type Result = { kind: 'idle' | 'working' | 'ok' | 'error'; text?: string; token?: string };

/** Potwierdzenie zapisu (od razu po wejściu z linku) albo wypisanie (dopiero po kliknięciu - skanery poczty otwierają linki). */
export function NewsletterAction({ mode }: { mode: 'confirm' | 'unsubscribe' }) {
  const token = useSearchParams().get('t') ?? '';
  const [result, setResult] = useState<Result>({ kind: 'idle' });

  async function run() {
    setResult({ kind: 'working' });
    try {
      const data = await apiWrite<{ unsubscribe_token?: string }>(`/api/newsletter/${mode === 'confirm' ? 'confirm' : 'unsubscribe'}/`, { token });
      setResult({ kind: 'ok', token: data.unsubscribe_token });
    } catch (error) {
      setResult({ kind: 'error', text: error instanceof Error ? error.message : 'Coś poszło nie tak.' });
    }
  }

  useEffect(() => {
    if (mode === 'confirm' && token) void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, token]);

  if (!token) return <p>Brak kodu w linku. Otwórz link z maila jeszcze raz albo <Link href="/newsletter">zapisz się ponownie</Link>.</p>;
  if (result.kind === 'error') return <p role="alert">{result.text} <Link href="/newsletter">Zapisz się ponownie</Link></p>;
  if (mode === 'confirm') {
    if (result.kind !== 'ok') return <p role="status">Potwierdzamy zapis…</p>;
    return <p role="status">✓ Gotowe - jesteś na liście. Napiszemy, gdy wystartujemy. Rozmyślisz się? <Link href={`/newsletter/wypisz?t=${encodeURIComponent(result.token ?? token)}`}>Wypisz się</Link>.</p>;
  }
  if (result.kind === 'ok') return <p role="status">✓ Wypisaliśmy ten adres. Nie wyślemy już żadnej wiadomości.</p>;
  return <p><button type="button" className="sc-onas-mail" onClick={() => void run()} disabled={result.kind === 'working'}>{result.kind === 'working' ? 'Wypisuję…' : 'Wypisz mnie z newslettera'}</button></p>;
}
