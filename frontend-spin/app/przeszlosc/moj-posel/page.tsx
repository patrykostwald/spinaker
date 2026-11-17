import { MojPoselPage } from './MojPoselPage';

export const metadata = {
  title: 'Mój poseł - przeszłość.today',
  description: 'Wybierz okręg wyborczy i zobacz posłów z tego okręgu: klub, profil z głosowaniami, wypowiedziami i odstępstwami od klubu.',
  robots: { index: false, follow: false },
};

export default function MojPoselRoute() {
  return <MojPoselPage />;
}
