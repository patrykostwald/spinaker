import { NextResponse } from 'next/server';

// Cel i zebrana kwota z .env.production (SUPPORT_MONTHLY_GOAL_PLN, SUPPORT_MONTHLY_RAISED_PLN) - czytane przy
// każdym zapytaniu, więc zmiana kwoty nie wymaga przebudowy. Pasek wsparcia nad stopką pobiera to raz na wizytę.
export const dynamic = 'force-dynamic';

// Stan zbiórki zapisany w kodzie - działa po samym wdrożeniu; zmienne z .env.production mają pierwszeństwo, gdy są ustawione.
// 30.09.2026: 40 zł (10 + 30) z 1500 zł miesięcznie.
const GOAL_PLN = 1500;
const RAISED_PLN = 40;

export function GET() {
  const goal = Number(process.env.SUPPORT_MONTHLY_GOAL_PLN || GOAL_PLN);
  // Wyższa z dwóch kwot: stary wpis „0” w .env.production nie może przykryć wpłat zapisanych w kodzie.
  const raised = Math.max(0, RAISED_PLN, Number(process.env.SUPPORT_MONTHLY_RAISED_PLN) || 0);
  return NextResponse.json({ goal: Number.isFinite(goal) ? goal : 0, raised: Number.isFinite(raised) ? raised : 0 },
    { headers: { 'Cache-Control': 'public, max-age=300' } });
}
