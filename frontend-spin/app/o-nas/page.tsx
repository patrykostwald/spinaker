import { AboutDocument } from "../../lib/documents/AboutDocument";

export const metadata = {
  title: "O nas - spin.clinic",
  description: "Projekt spin.clinic, operator, finansowanie, niezależność i kontakt. Pokazujemy, jak zbudowany jest przekaz.",
  alternates: { canonical: "/o-nas", languages: { pl: "/o-nas", en: "/en/about" } },
};

export default function AboutPage() {
  return <AboutDocument />;
}
