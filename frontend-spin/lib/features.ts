import 'server-only';
import { cookies } from 'next/headers';

export async function serverPreview() {
  const jar = await cookies();
  return jar.get('sc_preview')?.value === '1';
}
export async function serverFeature(name: 'ACCOUNTS_ENABLED' | 'THREADS_ENABLED') {
  const enabled = name === 'ACCOUNTS_ENABLED'
    ? process.env.NEXT_PUBLIC_ACCOUNTS_ENABLED === 'true'
    : process.env.NEXT_PUBLIC_THREADS_ENABLED === 'true';
  return enabled || await serverPreview();
}
/** Verify access to the landing page against Django's signed cookie. */
export async function verifiedPreview() {
  const jar = await cookies();
  const signature = jar.get('sc_preview_sig')?.value;
  if (jar.get('sc_preview')?.value !== '1' || !signature || !/^[A-Za-z0-9_.:-]+$/.test(signature)) return false;
  try {
    const response = await fetch(`${process.env.API_INTERNAL_URL || 'http://localhost:8000'}/api/preview/status/`, {
      headers: { Cookie: `sc_preview_sig=${signature}` },
      cache: 'no-store',
    });
    return response.ok && (await response.json()).active === true;
  } catch { return false; }
}
