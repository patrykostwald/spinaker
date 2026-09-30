export const dynamic = 'force-dynamic';
export function GET() {
  const fingerprint = process.env.ANDROID_SHA256_FINGERPRINT;
  const packageName = process.env.ANDROID_PACKAGE_NAME;
  if (!fingerprint || !packageName) return new Response(null, { status: 404 });
  return Response.json([{
    relation: ['delegate_permission/common.handle_all_urls'],
    target: { namespace: 'android_app', package_name: packageName, sha256_cert_fingerprints: [fingerprint] },
  }]);
}
