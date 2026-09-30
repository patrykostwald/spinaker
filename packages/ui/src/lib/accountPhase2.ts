import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './api';
import { useAccount } from './account';
import { isUnavailable } from './personal';

export type FollowKind = 'figure' | 'user' | 'thread';
export type Follow = { id: number; kind: FollowKind; target_id: number; label: string; url: string };
export type Notification = { id: number; kind: string; title: string; url: string; created_at: string; read_at: string | null };
export type NotificationSettings = { email_digest: 'off' | 'daily' | 'weekly'; push_spin_of_day: boolean; push_followed: boolean; push_thread_replies: boolean };
export function accountMessage(error: unknown) {
  return isUnavailable(error) ? 'Ta funkcja będzie dostępna wkrótce. Nie zapisano zmian.' : error instanceof Error ? error.message : 'Nie udało się zapisać. Spróbuj ponownie.';
}
export function useFollows() {
  const account = useAccount();
  const ownerId = account.data?.user?.id;
  return useQuery({ queryKey: ['account-follows', ownerId], enabled: Boolean(ownerId), retry: false,
    queryFn: async () => {
      const data = await apiFetch<Follow[] | { results: Follow[] }>('/api/account/follows/');
      return Array.isArray(data) ? data : data.results;
    } });
}
export function useNotifications() {
  const account = useAccount();
  return useQuery({ queryKey: ['account-notifications', account.data?.user?.id], enabled: Boolean(account.data?.user?.id), retry: false,
    refetchInterval: query => isUnavailable(query.state.error) ? false : 60_000, refetchIntervalInBackground: false,
    queryFn: () => apiFetch<{ results: Notification[]; unread: number }>('/api/account/notifications/') });
}
/** API-owned internal links only; never turn a notification into an external redirect. */
export function accountHref(url: string) { return /^\/(?![\/\\])/.test(url) && !/[\\\u0000-\u001f]/.test(url) ? url : '/konto'; }
