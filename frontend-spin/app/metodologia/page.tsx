import { MethodologyDocument } from "../../lib/documents/MethodologyDocument";

export const metadata = {
  title: "Metodologia — spin.clinic",
  description: "Jak wybieramy wpisy, łączymy oceny AI i liczymy dane Kliniki. Zakres, ograniczenia i zasady zgłaszania błędów.",
  alternates: { canonical: "/metodologia", languages: { pl: "/metodologia", en: "/en/methodology" } },
};

export default function MethodologyPage() {
  return <MethodologyDocument />;
}
