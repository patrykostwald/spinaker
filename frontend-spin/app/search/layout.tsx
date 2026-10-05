import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'Szukaj - spin.clinic', description: 'Wyszukiwarka diagnoz, spinek i materiałów w spin.clinic.' };

export default function Layout({ children }: { children: React.ReactNode }) { return children; }
