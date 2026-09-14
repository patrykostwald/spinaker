"use client";
import Link from 'next/link';
import { SearchBar } from './SearchBar';
import { AccountControl } from './AccountDialog';
import { ThemeSwitcher } from './ThemeSwitcher';
import type { SiteConfig } from '../types';
export function SiteHeader({ site }: { site: SiteConfig; showSearch?: boolean }) {
  return <header className="site-header border-b"><div className="mx-auto grid max-w-7xl items-center gap-3 px-4 py-3 md:grid-cols-[auto_minmax(0,1fr)_auto]">
    <Link href="/" className="site-wordmark text-xl font-bold tracking-tight"><span>{site.name}</span></Link>
    <div className="w-full md:mx-auto md:max-w-xl"><SearchBar /></div>
    <div className="header-account"><Link href="/jak-dzialamy" className="header-motto whitespace-nowrap text-center">CONTEXT BEFORE CONTENT</Link><div className="header-account-actions"><ThemeSwitcher /><AccountControl /></div></div>
  </div></header>;
}
