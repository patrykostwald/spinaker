import type { Metadata } from 'next';
import { InterviewVoting } from '@spin-clinic/ui';

export const metadata: Metadata = {
  title: 'Głosowanie na wywiad dnia - Klinika spinu',
  description: 'Wybierz wywiad dnia. Kandydaci, jawne liczby głosów i propozycje czytelników.',
};

export default function InterviewVotingRoute() {
  return <InterviewVoting />;
}
