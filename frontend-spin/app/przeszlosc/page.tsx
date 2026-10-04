import { TopicTree } from './TopicTree';

export const metadata = { title: 'przeszłość.today - kto, co i kiedy w jednym temacie', robots: { index: false, follow: false } };

export default function PrzeszloscPage() {
  return <TopicTree />;
}
