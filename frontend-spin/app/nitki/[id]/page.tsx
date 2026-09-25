import type { Metadata } from 'next';
import { CommunityThreadPage } from '@spin-clinic/ui';

export const metadata: Metadata = { title: 'Nitka czytelnika — spin.clinic' };

export default function CommunityThreadRoute({ params }: { params: { id: string } }) {
  return <CommunityThreadPage id={params.id} />;
}
