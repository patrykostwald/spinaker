import { StanDanych } from './StanDanych';

export const metadata = {
  title: 'Stan danych - przeszłość.today',
  description: 'Każde źródło przeszłość.today: czy zbieramy, ile rekordów, kiedy ostatnio pobrane i jakie są znane braki. Pokrycie KRS osób i podmiotów.',
};

export default function StanDanychRoute() {
  return <StanDanych />;
}
