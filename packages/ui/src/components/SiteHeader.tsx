"use client";
import { useState, useId, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAccount } from '../lib/account';
import type { SiteConfig } from '../types';
import { ThemeSwitcher } from './ThemeSwitcher';

function HeaderSearch() {
  const [value, setValue] = useState('');
  const id = useId();
  const router = useRouter();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    router.push(value.trim() ? `/?q=${encodeURIComponent(value.trim())}#baza` : '/#baza');
  }
  return (
    <form className="mvp-header-search" onSubmit={submit} role="search">
      <label className="sr-only" htmlFor={id}>Szukaj w bazie materiałów</label>
      <input id={id} type="search" value={value} onChange={event => setValue(event.target.value)} maxLength={200} placeholder="Szukaj w bazie…" />
      <button type="submit">Szukaj</button>
    </form>
  );
}

export function SiteHeader({ site }: { site: SiteConfig }) {
  const [first, ...rest] = site.name.split('.');
  const second = rest.join('.');
  const account = useAccount();
  return (
    <header className="mvp-site-header">
      <div className="mvp-site-header-inner">
        <Link href="/" className="mvp-wordmark">
          {second ? <>{first}<span className="mvp-wordmark-dot" aria-hidden="true">.</span>{second}</> : site.name}
        </Link>
        <HeaderSearch />
        <div className="mvp-header-actions">
          <Link href="/o-nas" className="mvp-header-link">O NAS</Link>
          {account.data?.authenticated
            ? <Link href="/konto" className="mvp-header-link">MOJE KONTO</Link>
            : <Link href="/konto" className="mvp-header-link">ZALOGUJ</Link>}
          <ThemeSwitcher />
        </div>
      </div>
    </header>
  );
}
