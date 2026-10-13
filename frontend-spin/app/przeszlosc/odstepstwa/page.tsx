import { OdstepstwaPage } from './OdstepstwaPage';

export const metadata = {
  title: 'Odstępstwa od klubu - przeszłość.today',
  description: 'Kto w Sejmie głosuje inaczej niż większość własnego klubu. Te same progi dla każdego klubu; odstępstwo nie jest zarzutem.',
  robots: { index: false, follow: false },
};

export default function OdstepstwaRoute() {
  return <OdstepstwaPage />;
}
