import type { Metadata } from 'next';
import Link from 'next/link';
import { DEMO_PUBLIC_FIGURE, PublicFigureProfile } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Profil osoby publicznej (demo) — spin.clinic',
  description: 'Demonstracja układu profilu na fikcyjnych danych.',
  robots: { index: false, follow: false },
};

export default function PublicFigureDemoPage() {
  return (
    <div className="mvp-pf-page">
      <p className="mvp-pf-back"><Link href="/osoby-publiczne">← Osoby publiczne</Link></p>
      <PublicFigureProfile figure={DEMO_PUBLIC_FIGURE} demo />
    </div>
  );
}
