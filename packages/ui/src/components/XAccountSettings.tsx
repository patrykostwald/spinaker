"use client";
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { apiFetch, apiWrite } from '../lib/api';
import { useAccount } from '../lib/account';

export function XAccountSettings() {
  const account = useAccount(), cache = useQueryClient();
  const connection = useQuery({ queryKey: ['x-connection', account.data?.user?.id], enabled: !!account.data?.authenticated,
    queryFn: () => apiFetch<{ connected: boolean; username: string; use_x_name: boolean; oauth_enabled: boolean; connect_url: string | null }>('/api/account/x-connection/') });
  const [pending, setPending] = useState(false), [error, setError] = useState('');
  async function change(method: string, body = {}) {
    setPending(true); setError('');
    try { await apiWrite('/api/account/x-connection/', body, method); await Promise.all([cache.invalidateQueries({ queryKey: ['x-connection'] }), cache.invalidateQueries({ queryKey: ['account'] }), cache.invalidateQueries({ queryKey: ['community-threads'] }), cache.invalidateQueries({ queryKey: ['thread-comments'] })]); }
    catch (e) { setError(e instanceof Error ? e.message : 'Nie udało się zapisać.'); } finally { setPending(false); }
  }
  if (!connection.data?.connected && !connection.data?.oauth_enabled) return null;
  return <section><h3>Konto X</h3>{connection.data.connected ? <>
    <p><a href={`https://x.com/${connection.data.username}`} target="_blank" rel="noopener noreferrer">@{connection.data.username} 𝕏</a></p>
    <label>Wyświetlany nick<select disabled={pending} value={connection.data.use_x_name ? 'x' : 'local'} onChange={e => change('PATCH', { use_x_name: e.target.value === 'x' })}><option value="local">{account.data?.user?.username}</option><option value="x">@{connection.data.username}</option></select></label>
    <button type="button" disabled={pending} onClick={() => change('DELETE')}>Rozłącz konto X</button>
  </> : <a href={connection.data.connect_url!}>Połącz konto X</a>}{error && <p role="alert">{error}</p>}</section>;
}
