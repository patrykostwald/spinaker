import { CouncilDocument } from "../../lib/documents/CouncilDocument";

export const metadata = {
  title: "Konsylium AI — spin.clinic",
  description: "Jak kilka modeli AI różnych firm wspólnie stawia diagnozę: droga wpisu, role, skład, łączenie głosów, narzędzia i zasady.",
  alternates: { canonical: "/konsylium", languages: { pl: "/konsylium", en: "/en/council" } },
};

export default function CouncilPage() {
  return <CouncilDocument />;
}
