"use client";
import Link from 'next/link';
import { SearchBar } from './SearchBar';
import { AccountControl } from './AccountDialog';
import type { SiteConfig } from '../types';
export function SiteHeader({ site }: { site: SiteConfig; showSearch?: boolean }) {
  return <header className="site-header border-b"><div className="mx-auto grid max-w-7xl items-center gap-3 px-4 py-3 md:grid-cols-[auto_minmax(0,1fr)_auto]">
    <Link href="/" className="site-wordmark text-xl font-bold tracking-tight text-primary"><svg className="brand-axis" width="33" height="20" viewBox="0 0 33 20" aria-hidden="true"><path d="M1 10H24" fill="none" stroke="currentColor" strokeWidth="1.7" /><circle cx="26" cy="10" r="4.5" fill="currentColor" /></svg><span>{site.name}</span><span className="brand-beta text-xs font-medium text-slate-400">BETA</span></Link>
    <div className="w-full md:mx-auto md:max-w-xl"><SearchBar /></div>
    <div className="header-account"><Link href="/jak-dzialamy" className="header-motto whitespace-nowrap text-center">CONTEXT BEFORE CONTENT</Link><AccountControl /></div>
  </div></header>;
}
