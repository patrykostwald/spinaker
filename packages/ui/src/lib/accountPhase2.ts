import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './api';
import { useAccount } from './account';
import { isUnavailable } from './personal';

export type FollowKind = 'figure' | 'user' | 'thread';
export type FollowMode = 'posts' | 'diagnoses' | 'strong_spin';
export const FOLLOW_MODES: { value: FollowMode; label: string }[] = [{ value: 'posts', label: 'Każdy wpis' }, { value: 'diagnoses', label: 'Diagnozy' }, { value: 'strong_spin', label: 'Tylko silny spin' }];
export type Follow = { id: number; kind: FollowKind; target_id: number; label: string; url: string; mode: FollowMode | null };
export type Notification = { id: number; kind: string; title: string; url: string; created_at: string; read_at: string | null; posts?: { id: number; title: string; url: string; score: number | null }[] };
export type NotificationSettings = { service_enabled: boolean; social_enabled: boolean; email_digest: 'off' | 'daily' | 'weekly'; push_spin_of_day: boolean; push_followed: boolean; push_thread_replies: boolean };
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

/** Only canonical X post links may leave the notification centre. */
export function notificationHref(url: string) {
  return /^https:\/\/x\.com\/[A-Za-z0-9_]{1,15}\/status\/[1-9][0-9]*$/.test(url) ? url : accountHref(url);
}
