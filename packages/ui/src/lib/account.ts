import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './api';

export type Account = { authenticated: boolean; google_enabled?: boolean; user: { id: number; username: string; email?: string; email_verified?: boolean; accepted_terms_version?: string; is_staff: boolean; is_journalist?: boolean; can_edit_threads?: boolean } | null; csrfToken: string };
export type SavedTopic = { id: number; label: string; query: string; categories: string[]; topics?: string[]; source_ids: number[]; position: number };
export function useAccount() {
  return useQuery({ queryKey: ['account'], queryFn: () => apiFetch<Account>('/api/account/me/'), staleTime: 30_000, retry: false });
}
