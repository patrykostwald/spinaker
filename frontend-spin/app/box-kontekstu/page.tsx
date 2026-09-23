import type { Metadata } from 'next';
import Link from 'next/link';
import { BoxKontekstu } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Box kontekstu (demo) — spin.clinic',
  description: 'Demonstracja widoku: box źródłowy, oś czasu powiązanych materiałów i własna nitka kontekstowa. Dane przykładowe.',
  robots: { index: false, follow: false },
};

export default function BoxKontekstuPage() {
  return (
    <div className="mvp-ctx-page">
      <Link href="/" className="mvp-ctx-back">← Strona główna</Link>
      <BoxKontekstu />
    </div>
  );
}
