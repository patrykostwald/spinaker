import type { Metadata } from 'next';
import Link from 'next/link';
import { PowiekszonyBoxDemo } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Powiększony box materiału (demo) — spin.clinic',
  description: 'Demonstracja powiększonego boxa: relacje i chronologia materiałów oraz wariant profilu polityka. Dane fikcyjne.',
  robots: { index: false, follow: false },
};

export default function BoxMaterialuPage() {
  return (
    <div className="mvp-ctx-page">
      <h1 className="sr-only">Powiększony box materiału — demo z danymi fikcyjnymi</h1>
      <Link href="/" className="mvp-ctx-back">← Strona główna</Link>
      <PowiekszonyBoxDemo />
    </div>
  );
}
