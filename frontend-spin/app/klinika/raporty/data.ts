import { notFound } from 'next/navigation';
import { cache } from 'react';
import type { ReportResponse } from '@spin-clinic/ui';

const API = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export const loadReport = cache(async (week?: string): Promise<ReportResponse> => {
  if (week !== undefined && !/^\d{4}-\d{2}-\d{2}$/.test(week)) notFound();
  const response = await fetch(`${API}/api/clinic/report/${week ? `${encodeURIComponent(week)}/` : ''}`, { cache: 'no-store' });
  if (response.status === 404) notFound();
  if (!response.ok) throw new Error('Unable to load report');
  return response.json();
});
