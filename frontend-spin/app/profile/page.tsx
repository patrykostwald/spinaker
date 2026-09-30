import { redirect } from 'next/navigation';
export default function ProfilePage() {
  // Konta czytelników wracają w fazie II (NEXT_PUBLIC_ACCOUNTS_ENABLED=true).
  if (process.env.NEXT_PUBLIC_ACCOUNTS_ENABLED !== 'true') redirect('/');
  redirect('/konto');
}
