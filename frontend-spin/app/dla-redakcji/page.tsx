import { PressDocument } from "../../lib/documents/PressDocument";

export const metadata = {
  title: "Dla redakcji - spin.clinic",
  description: "Jak cytować diagnozy AI, odsyłać do źródeł i metodologii oraz dołączyć do pilotażu autoryzowanych nitek.",
  alternates: { canonical: "/dla-redakcji", languages: { pl: "/dla-redakcji", en: "/en/press" } },
};

export default function PressPage() {
  return <PressDocument />;
}
