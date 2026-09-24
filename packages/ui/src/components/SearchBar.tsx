"use client";
import { useEffect, useState, useId } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '../kit/Button';
import { SearchField } from '../kit/SearchField';
export function SearchBar({ initialQuery = '', navigateOnSubmit = true }: { initialQuery?: string; navigateOnSubmit?: boolean }) {
  const [value, setValue] = useState(initialQuery);
  const id = useId();
  const router = useRouter();
  useEffect(() => setValue(initialQuery), [initialQuery]);
  return <form className="sc-search-form" onSubmit={event => {
    event.preventDefault();
    if (value.trim() && navigateOnSubmit) router.push(`/search?q=${encodeURIComponent(value.trim())}`);
  }}>
    <SearchField id={id} label="Szukaj tematu, nazwiska lub wklej URL" value={value} onChange={setValue}
      placeholder="Wpisz temat, nazwisko lub wklej URL…" maxLength={1024} />
    <Button variant="primary" size="lg" type="submit">Szukaj</Button>
  </form>;
}
