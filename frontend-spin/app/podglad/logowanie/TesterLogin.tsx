'use client';

import { useState, type FormEvent } from 'react';
import { apiWrite } from '@spin-clinic/ui';

export function TesterLogin() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = new FormData(event.currentTarget);
    setPending(true); setError('');
    try {
      const result = await apiWrite<{ next?: string }>('/api/preview/login/', { username: form.get('username'), password: form.get('password') });
      window.location.assign(result?.next || '/podglad');
    } catch (reason) {
      setError(reason instanceof Error && reason.message ? reason.message : 'Nie udało się zalogować. Spróbuj ponownie.');
      setPending(false);
    }
  }
  return <form className="sc-account-form sc-tester-login" onSubmit={submit} aria-busy={pending}>
    <label>Login<input name="username" required autoComplete="username" autoCapitalize="none" spellCheck={false} maxLength={150} /></label>
    <label>Hasło<input name="password" type="password" required autoComplete="current-password" maxLength={256} /></label>
    {error && <p role="alert" className="sc-account-form__error">{error}</p>}
    <button type="submit" className="sc-preview-exit" disabled={pending}>{pending ? 'Logowanie…' : 'Zaloguj się'}</button>
  </form>;
}
