import { PublicAccountProfile } from '@spin-clinic/ui';
export default function PublicProfilePage({ params }: { params: { username: string } }) { return <PublicAccountProfile username={params.username} />; }
