"use client";
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '../kit';
import { apiWrite } from '../lib/api';
import { useAccount } from '../lib/account';
import { ACCOUNTS_ENABLED, THREADS_ENABLED } from '../lib/features';
import { isUnavailable } from '../lib/personal';
import { accountMessage, useFollows, type FollowKind } from '../lib/accountPhase2';
import { AccountDialog } from './AccountDialog';

export function FollowButton(props: { kind: FollowKind; targetId: number; label: string }) {
  return ACCOUNTS_ENABLED && (props.kind !== 'thread' || THREADS_ENABLED) ? <FollowControl {...props} /> : null;
}
function FollowControl({ kind, targetId, label }: { kind: FollowKind; targetId: number; label: string }) {
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
    <Button type="button" variant="quiet" aria-pressed={Boolean(match)} aria-label={`${match ? 'Przestań obserwować' : 'Obserwuj'}: ${label}`} loading={pending}
      disabled={account.isFetching || Boolean(account.data?.authenticated && !follows.isSuccess)} onClick={toggle}>{match ? 'Obserwujesz' : kind === 'thread' ? 'Obserwuj nitkę' : kind === 'user' ? 'Obserwuj autora' : 'Obserwuj'}</Button>
    {follows.isError && <Button variant="quiet" onClick={() => follows.refetch()}>Ponów</Button>}
    {message && <span role="status">{message}</span>}
    <AccountDialog open={open} onClose={() => setOpen(false)} />
  </span>;
}
