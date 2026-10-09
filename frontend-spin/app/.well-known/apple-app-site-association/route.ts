export const dynamic = 'force-dynamic';
export function GET() {
  const team = process.env.APPLE_TEAM_ID;
  const bundle = process.env.APPLE_BUNDLE_ID;
  if (!team || !bundle) return new Response(null, { status: 404 });
  return Response.json({ applinks: { apps: [], details: [{
    appID: `${team}.${bundle}`, paths: process.env.NEXT_PUBLIC_THREADS_ENABLED === 'true' ? ['/klinika', '/klinika/*', '/thread/*', '/spinki', '/spinki/*'] : ['/klinika', '/klinika/*', '/thread/*'],
  }] } });
}
