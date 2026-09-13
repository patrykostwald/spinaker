"use client";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import { formatDatePl } from '../lib/utils';
type Coverage = {notice: string; sources: {id: number; name: string; url: string; records: number; oldest: string | null; newest: string | null; status: string; pending_archive_urls: number}[]};
export function SourceCoverage() {
  const [open, setOpen] = useState(false);
  const result = useQuery({queryKey: ['coverage'], queryFn: () => apiFetch<Coverage>('/api/sources/coverage/'), enabled: open});
  return <details className="rounded-lg border bg-white p-4 text-sm" onToggle={e => setOpen(e.currentTarget.open)}><summary className="cursor-pointer font-medium">Co obejmuje nasza baza? Sprawdź źródła i znane braki</summary>{open && <div className="mt-4 space-y-3">{result.isPending ? <p>Sprawdzam zakres…</p> : result.isError ? <p>Nie udało się odczytać zakresu bazy.</p> : <><p>{result.data.notice}</p><div className="max-h-80 space-y-3 overflow-y-auto">{result.data.sources.map(s => <div key={s.id} className="border-t pt-3"><a href={s.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-primary">{s.name} ↗</a><p>{s.records} materiałów · {s.oldest ? `${formatDatePl(s.oldest)} — ${formatDatePl(s.newest)}` : 'Brak ustalonego zakresu dat'}</p>{s.pending_archive_urls > 0 && <p>{s.pending_archive_urls} odkrytych adresów czeka na odczyt lub ponowną próbę.</p>}{s.status === 'requires_attention' && <p className="text-amber-800">Ostatnie pobieranie wymaga sprawdzenia.</p>}</div>)}</div></>}</div>}</details>;
}
