import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './api';
import { ACCOUNTS_ENABLED } from './features';

type AccountDetails = { email?: string; email_verified?: boolean; accepted_terms_version?: string };
export type Account = AccountDetails & { authenticated: boolean; google_enabled?: boolean; user: (AccountDetails & { id: number; username: string; is_staff: boolean; is_journalist?: boolean; can_edit_threads?: boolean }) | null; csrfToken: string };
export const TERMS_VERSION = '2026-09-30';
export const accountEmail = (account?: Account) => account?.user?.email ?? account?.email ?? '';
export const emailVerified = (account?: Account) => (account?.user?.email_verified ?? account?.email_verified) === true;
export type SavedTopic = { id: number; label: string; query: string; categories: string[]; topics?: string[]; source_ids: number[]; position: number };
export function useAccount() {
  return useQuery({ queryKey: ['account'], queryFn: () => apiFetch<Account>('/api/account/me/'), enabled: ACCOUNTS_ENABLED, staleTime: 30_000, retry: false });
}
