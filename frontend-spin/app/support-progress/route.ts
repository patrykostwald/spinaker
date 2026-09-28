import { NextResponse } from 'next/server';

// Cel i zebrana kwota z .env.production (SUPPORT_MONTHLY_GOAL_PLN, SUPPORT_MONTHLY_RAISED_PLN) — czytane przy
// każdym zapytaniu, więc zmiana kwoty nie wymaga przebudowy. Pasek wsparcia nad stopką pobiera to raz na wizytę.
export const dynamic = 'force-dynamic';

export function GET() {
  const goal = Number(process.env.SUPPORT_MONTHLY_GOAL_PLN || 0);
  const raised = Math.max(0, Number(process.env.SUPPORT_MONTHLY_RAISED_PLN || 0));
  return NextResponse.json({ goal: Number.isFinite(goal) ? goal : 0, raised: Number.isFinite(raised) ? raised : 0 },
    { headers: { 'Cache-Control': 'public, max-age=300' } });
}
