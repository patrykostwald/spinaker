import type { Metadata } from 'next';
import { isThreadsEnabled } from '../../lib/threadsRouting';

export const metadata: Metadata = { title: 'Szukaj - spin.clinic', description: isThreadsEnabled() ? 'Wyszukiwarka diagnoz, spinek i materiałów w spin.clinic.' : 'Wyszukiwarka diagnoz i materiałów w spin.clinic.' };

export default function Layout({ children }: { children: React.ReactNode }) { return children; }
