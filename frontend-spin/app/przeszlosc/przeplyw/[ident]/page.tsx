import { notFound } from 'next/navigation';
import { FlowTree } from '../../FlowTree';

export const metadata = {
  title: 'Drzewo przepływu - przeszłość.today',
  description: 'Powiązania i przepływy wokół osoby publicznej albo podmiotu, z datami i źródłami.',
  robots: { index: false, follow: false },
};
export default function FlowRoute({ params }: { params: { ident: string } }) {
  let ident: string;
  try { ident = decodeURIComponent(params.ident); } catch { notFound(); }
  if (!/^(osoba:[a-zA-Z0-9-]{1,140}|spolka:\d{1,14})$/.test(ident)) notFound();
  return <FlowTree ident={ident} />;
}
