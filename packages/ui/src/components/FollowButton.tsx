"use client";
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '../kit';
import { apiWrite } from '../lib/api';
import { useAccount } from '../lib/account';
import { useFeature } from '../lib/features';
import { isUnavailable } from '../lib/personal';
import { accountMessage, useFollows, type FollowKind } from '../lib/accountPhase2';
import { AccountDialog } from './AccountDialog';

export function FollowButton(props: { kind: FollowKind; targetId: number; label: string; compactLabel?: boolean }) {
  const ACCOUNTS_ENABLED = useFeature('ACCOUNTS_ENABLED');
  const THREADS_ENABLED = useFeature('THREADS_ENABLED');
  return ACCOUNTS_ENABLED && (props.kind !== 'thread' || THREADS_ENABLED) ? <FollowControl {...props} /> : null;
}
function FollowControl({ kind, targetId, label, compactLabel }: { kind: FollowKind; targetId: number; label: string; compactLabel?: boolean }) {
  const account = useAccount(); const follows = useFollows(); const cache = useQueryClient();
  const [open, setOpen] = useState(false); const [pending, setPending] = useState(false); const [message, setMessage] = useState('');
  const match = follows.data?.find(row => row.kind === kind && row.target_id === targetId);
  async function toggle() {
    if (pending) return;
    if (!account.data?.authenticated) { setOpen(true); return; }
    setPending(true); setMessage('');
    try {
      if (match) await apiWrite(`/api/account/follows/${match.id}/`, {}, 'DELETE');
      else await apiWrite('/api/account/follows/', { kind, target_id: targetId });
      await cache.invalidateQueries({ queryKey: ['account-follows'] });
      setMessage(match ? 'Usunięto z obserwowanych.' : 'Dodano do obserwowanych.');
    } catch (error) { setMessage(accountMessage(error)); }
    finally { setPending(false); }
  }
  if (kind === 'user' && account.data?.user?.id === targetId) return null;
  if (isUnavailable(follows.error)) return <span className="sc-f2-muted">Obserwowanie będzie dostępne wkrótce.</span>;
  return <span className="sc-f2-follow">
    <Button type="button" variant="quiet" aria-pressed={Boolean(match)} aria-label={`${compactLabel ? (match ? 'Usuń z obserwowanych nitek' : 'Zapisz w obserwowanych nitkach') : match ? 'Przestań obserwować' : 'Obserwuj'}: ${label}`} title={compactLabel ? 'Zapisz w obserwowanych nitkach' : undefined} loading={pending}
      disabled={account.isFetching || Boolean(account.data?.authenticated && !follows.isSuccess)} onClick={toggle}>{compactLabel ? (match ? 'Zapisano' : 'Zapisz') : kind === 'thread' ? (match ? 'Obserwujesz nitkę ✓' : 'Obserwuj nitkę') : kind === 'user' ? (match ? 'Obserwujesz autora ✓' : 'Obserwuj autora') : (match ? 'Obserwujesz ✓' : 'Obserwuj')}</Button>
    {follows.isError && <Button variant="quiet" onClick={() => follows.refetch()}>Ponów</Button>}
    {message && <span role="status">{message}</span>}
    <AccountDialog open={open} onClose={() => setOpen(false)} />
  </span>;
}
