import type { Metadata } from 'next';
import { MojaNitkaEditor } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Nowa prywatna nitka — spin.clinic',
  robots: { index: false, follow: false },
};

export default function NewPersonalThreadPage() {
  return <MojaNitkaEditor />;
}
