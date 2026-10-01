import { CouncilCharterDocument } from "../../../lib/documents/CouncilCharterDocument";

export const metadata = { title: 'Karta Konsylium AI — spin.clinic', alternates: { canonical: "/konsylium/karta", languages: { pl: "/konsylium/karta", en: "/en/council/charter" } } };

export default function CouncilCharterPage() {
  return <CouncilCharterDocument />;
}
