"use client";
import { useEffect, useState, useId } from 'react';
import { useRouter } from 'next/navigation';
export function SearchBar({ initialQuery = '', navigateOnSubmit = true }: { initialQuery?: string; navigateOnSubmit?: boolean }) {
  const [value, setValue] = useState(initialQuery);
  const id = useId();
  const router = useRouter();
  useEffect(() => setValue(initialQuery), [initialQuery]);
  return <form className="flex w-full gap-2" onSubmit={event => {
    event.preventDefault();
    if (value.trim() && navigateOnSubmit) router.push(`/search?q=${encodeURIComponent(value.trim())}`);
  }}>
    <label className="sr-only" htmlFor={id}>Szukaj tematu, nazwiska lub wklej URL</label>
    <input id={id} type="search" value={value} required maxLength={1024} onChange={e => setValue(e.target.value)}
      placeholder="Wpisz temat, nazwisko lub wklej URL…"
      className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-4 py-3 text-base focus:ring-2 focus:ring-primary" />
    <button className="rounded-lg bg-primary px-5 py-3 font-semibold text-white" type="submit">Szukaj</button>
  </form>;
}
