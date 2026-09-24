"use client";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import { useAccount } from '../lib/account';
import { Button } from '../kit/Button';
import { Dialog } from './Dialog';

type ShareOnXProps = {
  title: string;
  path: string;
  label?: string;
};

export function ShareOnX({ title, path, label = "Udostępnij na X" }: ShareOnXProps) {
  const [draft, setDraft] = useState(title);
  const [open, setOpen] = useState(false);
  const account = useAccount();
  const connection = useQuery({
    queryKey: ['x-connection'],
    queryFn: () => apiFetch<{ connected: boolean }>('/api/account/x-connection/'),
    enabled: Boolean(account.data?.authenticated), retry: false,
  });
  if (!account.data?.authenticated || !connection.data?.connected) return null;
  const share = () => {
    const url = new URL(path, window.location.origin).toString();
    const params = new URLSearchParams({ text: draft.trim() || title, url });
    window.open(
      `https://x.com/intent/tweet?${params.toString()}`,
      "spin-clinic-x-share",
      "popup=yes,width=620,height=640,scrollbars=yes,resizable=yes",
    );
  };

  return <>
    <Button type="button" variant="secondary" size="md" onClick={() => setOpen(true)}>{label}</Button>
    <Dialog open={open} onClose={() => setOpen(false)} title="Udostępnij na X">
      <div className="sc-share-x">
        <label className="sc-share-x__label">Twój komentarz
          <textarea value={draft} maxLength={240} rows={4} onChange={event => setDraft(event.target.value)} />
        </label>
        <p className="sc-t-caption sc-text-2">Link do materiału lub nitki zostanie dodany przez X. Publikację zatwierdzasz tam samodzielnie.</p>
        <Button type="button" variant="primary" size="md" onClick={share}>Otwórz X ↗</Button>
      </div>
    </Dialog>
  </>;
}
