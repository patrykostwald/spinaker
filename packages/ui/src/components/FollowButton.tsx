"use client";
import { useId, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '../kit';
import { apiWrite } from '../lib/api';
import { useAccount } from '../lib/account';
import { useFeature } from '../lib/features';
import { isUnavailable } from '../lib/personal';
import { accountMessage, FOLLOW_MODES, useFollows, type Follow, type FollowKind, type FollowMode } from '../lib/accountPhase2';
import { AccountDialog } from './AccountDialog';

export function FollowButton(props: { kind: FollowKind; targetId: number; label: string; compactLabel?: boolean }) {
  const ACCOUNTS_ENABLED = useFeature('ACCOUNTS_ENABLED');
  const THREADS_ENABLED = useFeature('THREADS_ENABLED');
  return ACCOUNTS_ENABLED && (props.kind !== 'thread' || THREADS_ENABLED) ? <FollowControl {...props} /> : null;
}
function FollowControl({ kind, targetId, label, compactLabel }: { kind: FollowKind; targetId: number; label: string; compactLabel?: boolean }) {
  const account = useAccount(); const follows = useFollows(); const cache = useQueryClient();
  const [open, setOpen] = useState(false); const [pending, setPending] = useState(false); const [message, setMessage] = useState('');
  const [choosing, setChoosing] = useState(false), [mode, setMode] = useState<FollowMode>('diagnoses');
  const modeId = useId();
  const match = follows.data?.find(row => row.kind === kind && row.target_id === targetId);
  async function toggle(confirmMode = false) {
    if (pending) return;
    if (!account.data?.authenticated) { setOpen(true); return; }
    if (!match && kind === 'figure' && !confirmMode) {
      if (!choosing) setMode('diagnoses');
      setChoosing(value => !value); return;
    }
    setPending(true); setMessage('');
    try {
      if (match) await apiWrite(`/api/account/follows/${match.id}/`, {}, 'DELETE');
      else await apiWrite('/api/account/follows/', { kind, target_id: targetId, ...(kind === 'figure' ? { mode } : {}) });
      await cache.invalidateQueries({ queryKey: ['account-follows'] });
      setChoosing(false);
      setMessage(match ? 'Usunięto z obserwowanych.' : 'Dodano do obserwowanych.');
    } catch (error) { setMessage(accountMessage(error)); }
    finally { setPending(false); }
  }
  if (kind === 'user' && account.data?.user?.id === targetId) return null;
  if (isUnavailable(follows.error)) return <span className="sc-f2-muted">Obserwowanie będzie dostępne wkrótce.</span>;
  return <span className="sc-f2-follow">
    <Button type="button" variant="quiet" aria-pressed={Boolean(match)} aria-label={`${compactLabel ? (match ? 'Usuń z obserwowanych nitek' : 'Zapisz w obserwowanych nitkach') : match ? 'Przestań obserwować' : 'Obserwuj'}: ${label}`} title={compactLabel ? 'Zapisz w obserwowanych nitkach' : undefined} loading={pending}
      aria-expanded={kind === 'figure' && !match ? choosing : undefined} aria-controls={choosing ? modeId : undefined}
      disabled={account.isFetching || Boolean(account.data?.authenticated && !follows.isSuccess)} onClick={() => toggle()}>{compactLabel ? (match ? 'Zapisano' : 'Zapisz') : kind === 'thread' ? (match ? 'Obserwujesz nitkę ✓' : 'Obserwuj nitkę') : kind === 'user' ? (match ? 'Obserwujesz autora ✓' : 'Obserwuj autora') : (match ? 'Obserwujesz ✓' : 'Obserwuj')}</Button>
    {choosing && !match && <span id={modeId} className="sc-follow-mode-box" onKeyDown={event => { if (event.key === 'Escape') setChoosing(false); }}>
      <span role="radiogroup" aria-label={`Powiadomienia: ${label}`}>
        {FOLLOW_MODES.map(option => <label key={option.value}><input type="radio" name={modeId} value={option.value} checked={mode === option.value} disabled={pending} onChange={() => setMode(option.value)} />{option.label}</label>)}
      </span>
      <span className="sc-f2-actions"><Button loading={pending} onClick={() => toggle(true)}>Zapisz</Button><Button disabled={pending} variant="quiet" onClick={() => setChoosing(false)}>Anuluj</Button></span>
    </span>}
    {follows.isError && <Button variant="quiet" onClick={() => follows.refetch()}>Ponów</Button>}
    {message && <span role="status">{message}</span>}
    <AccountDialog open={open} onClose={() => setOpen(false)} />
  </span>;
}

export function FollowModeSelect({ follow }: { follow: Follow }) {
  const cache = useQueryClient();
  const [pending, setPending] = useState(false), [message, setMessage] = useState('');
  async function change(mode: FollowMode) {
    setPending(true); setMessage('');
    try {
      await apiWrite(`/api/account/follows/${follow.id}/`, { mode }, 'PATCH');
      await cache.invalidateQueries({ queryKey: ['account-follows'] });
      setMessage('Zapisano tryb.');
    } catch (error) { setMessage(accountMessage(error)); } finally { setPending(false); }
  }
  return <div className="sc-follow-mode-setting"><label>Powiadomienia
    <select aria-label={`Powiadomienia: ${follow.label}`} value={follow.mode ?? 'diagnoses'} disabled={pending} onChange={event => change(event.target.value as FollowMode)}>
      {FOLLOW_MODES.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select></label>{message && <span role="status">{message}</span>}</div>;
}
