"use client";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import { useAccount } from '../lib/account';

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

  return <span className="share-x-button">
    <button type="button" className="quiet-button" onClick={() => setOpen(value => !value)}>{label}</button>
    {open && <span className="share-x-editor">
      <label>Twój komentarz <textarea value={draft} maxLength={240} onChange={event => setDraft(event.target.value)} /></label>
      <small>Link do materiału lub nitki zostanie dodany przez X. Publikację zatwierdzasz tam samodzielnie.</small>
      <button type="button" className="quiet-button" onClick={share}>Otwórz X ↗</button>
    </span>}
  </span>;
}
