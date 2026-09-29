import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { cache } from 'react';
import { MessageDetail, formatDatePl, type MessageDay } from '@spin-clinic/ui';

const API = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const loadMessage = cache(async (day: string): Promise<MessageDay> => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) notFound();
  const response = await fetch(`${API}/api/clinic/messages/${encodeURIComponent(day)}/`, { cache: 'no-store' });
  if (response.status === 404) notFound();
  if (!response.ok) throw new Error('Unable to load daily messages');
  return response.json();
});

export async function generateMetadata({ params }: { params: { day: string } }): Promise<Metadata> {
  const data = await loadMessage(params.day);
  const title = `Przekazy dnia: ${formatDatePl(data.day)} — Klinika spinu`;
  const description = 'Przekaz rządzących i opozycji: syntezy, zakres analizowanego materiału i wpisy źródłowe.';
  return { title, description, alternates: { canonical: `/klinika/przekazy/${data.day}` },
    openGraph: { title, description, type: 'article', siteName: 'spin.clinic' } };
}

export default async function MessageRoute({ params }: { params: { day: string } }) {
  return <MessageDetail data={await loadMessage(params.day)} />;
}
