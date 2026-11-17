import type { Metadata } from 'next';
import { ClinicInterviewArchive } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Archiwum wywiadów - Klinika spinu',
  description: 'Wszystkie wywiady Kliniki spinu: ocena gościa i warsztatu prowadzącego, źródła oraz pełne analizy.',
};

export default function InterviewsRoute() {
  return <ClinicInterviewArchive />;
}
