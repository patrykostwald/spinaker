import type { Metadata } from 'next';
import { SpinDetail } from '@spin-clinic/ui';

export const metadata: Metadata = { title: 'Diagnoza spinu — spin.clinic' };

export default function SpinRoute({ params }: { params: { id: string } }) {
  return <SpinDetail id={params.id} />;
}
