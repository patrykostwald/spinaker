"use client";
import { useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { apiWrite } from '../lib/api';
import { useAccount, type Account } from '../lib/account';
import { Dialog } from './Dialog';

export function AccountDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const cache = useQueryClient();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true); setError('');
    try {
      const result = await apiWrite<Account>(`/api/account/${mode}/`, {
        username: form.get('username'), password: form.get('password'),
        ...(mode === 'register' ? { email: form.get('email') || '' } : {}),
      });
      cache.setQueryData(['account'], result);
      await cache.invalidateQueries({ queryKey: ['me'] });
      onClose();
    } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się zalogować.'); }
    finally { setPending(false); }
  }
  return <Dialog open={open} onClose={onClose} title={mode === 'login' ? 'Zaloguj się' : 'Załóż konto'}>
    <form onSubmit={submit} className="account-form space-y-5 p-6">
      <p className="text-sm text-slate-400">Zapisuj własne tematy i komentuj materiały. Tworzenie nitek przez użytkowników udostępnimy w kolejnym etapie.</p>
      <label className="block text-sm">Nazwa użytkownika<input required name="username" autoComplete="username" minLength={mode === 'register' ? 3 : undefined} maxLength={mode === 'register' ? 30 : 150} pattern={mode === 'register' ? '[A-Za-z0-9_]{3,30}' : undefined} className="mt-2 w-full rounded border bg-transparent p-3" />{mode === 'register' && <span className="mt-1 block text-xs text-slate-500">3–30 znaków: litery bez polskich znaków, cyfry lub podkreślenie.</span>}</label>
      {mode === 'register' && <label className="block text-sm">E-mail <span className="text-slate-500">(opcjonalnie)</span><input name="email" type="email" autoComplete="email" className="mt-2 w-full rounded border bg-transparent p-3" /></label>}
      <label className="block text-sm">Hasło<input required name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'register' ? 8 : undefined} className="mt-2 w-full rounded border bg-transparent p-3" /></label>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <button disabled={pending} className="w-full rounded bg-primary px-4 py-3 text-sm font-medium text-white disabled:opacity-50">{pending ? 'Chwila…' : mode === 'login' ? 'Zaloguj się' : 'Utwórz konto'}</button>
      <button type="button" disabled={pending} onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }} className="w-full text-sm text-primary">{mode === 'login' ? 'Nie masz konta? Zarejestruj się' : 'Masz już konto? Zaloguj się'}</button>
    </form>
  </Dialog>;
}

export function AccountControl() {
  const account = useAccount();
  const cache = useQueryClient();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function logout() {
    setPending(true); setError('');
    try {
      await apiWrite('/api/account/logout/', {});
      cache.removeQueries({ queryKey: ['account-topics'] });
      cache.removeQueries({ queryKey: ['topic-feed'] });
      await Promise.all([cache.invalidateQueries({ queryKey: ['account'] }), cache.invalidateQueries({ queryKey: ['me'] })]);
    } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się wylogować.'); }
    finally { setPending(false); }
  }
  return <div className="account-control">
    {account.data?.authenticated ? <><Link href="/profile" className="account-name" title="Twój profil">{account.data.user?.username}</Link>{account.data.user?.can_edit_threads && <Link href="/editor" className="editor-entry">{account.data.user?.is_staff ? 'Redakcja' : 'Warsztat'}</Link>}<button disabled={pending} onClick={logout} className="quiet-button">Wyloguj</button></> : <button onClick={() => setOpen(true)} className="quiet-button" disabled={account.isPending}>Zaloguj się</button>}
    {error && <span role="alert" className="text-xs text-red-700">{error}</span>}
    <AccountDialog open={open} onClose={() => setOpen(false)} />
  </div>;
}
