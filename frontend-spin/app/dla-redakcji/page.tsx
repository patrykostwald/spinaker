import { PressDocument } from "../../lib/documents/PressDocument";

export const metadata = {
  title: "Dla redakcji - spin.clinic",
  description: "Raporty tygodniowe i dane dla redakcji oraz instytucji. Bezpłatna próbka, zakres analiz i zasady cytowania diagnoz AI.",
  alternates: { canonical: "/dla-redakcji", languages: { pl: "/dla-redakcji", en: "/en/press" } },
};

export default function PressPage() {
  return <PressDocument />;
}
