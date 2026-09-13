"use client";
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { ThreadListItem } from '../types';
import { useAccount } from '../lib/account';
import { apiFetch, apiWrite } from '../lib/api';
import { AccountDialog } from './AccountDialog';

export function ThreadFavoriteButton({ thread }: { thread: Pick<ThreadListItem, 'id' | 'published' | 'title'> }) {
  const account = useAccount();
  const ownerId = account.data?.user?.id;
  const cache = useQueryClient();
  const key = ['thread-favorite', ownerId, thread.id];
  const favorite = useQuery({ queryKey: key, queryFn: () => apiFetch<{ results: { id: number }[] }>(`/api/account/favorites/?thread_id=${thread.id}`), enabled: Boolean(ownerId && thread.published), staleTime: 30_000 });
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const saved = Boolean(favorite.data?.results.length);
  async function toggle() {
    if (!ownerId) { setOpen(true); return; }
    setPending(true); setError('');
    try {
      await apiWrite(saved ? `/api/account/favorites/${thread.id}/` : '/api/account/favorites/', saved ? {} : { thread_id: thread.id }, saved ? 'DELETE' : 'POST');
      await Promise.all([cache.invalidateQueries({ queryKey: key }), cache.invalidateQueries({ queryKey: ['account-favorites', ownerId] })]);
    } catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się zmienić ulubionych.'); }
    finally { setPending(false); }
  }
  if (!thread.published) return null;
  return <div className="favorite-control"><button type="button" className="quiet-button favorite-button" aria-pressed={saved} aria-label={`${saved ? 'Usuń z ulubionych' : 'Dodaj do ulubionych'}: ${thread.title}`} disabled={pending || Boolean(ownerId && favorite.isPending)} onClick={toggle}><span aria-hidden="true">{saved ? '♥' : '♡'}</span> {saved ? 'Zapisana' : 'Zapisz'}</button>{favorite.isError && <button className="text-xs text-primary" onClick={() => favorite.refetch()}>Odśwież ulubione</button>}{error && <span role="alert" className="text-xs text-red-700">{error}</span>}<AccountDialog open={open} onClose={() => setOpen(false)} /></div>;
}
