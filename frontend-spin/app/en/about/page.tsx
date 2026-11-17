import { AboutDocument } from "../../../lib/documents/AboutDocument";
import { englishMetadata } from "../../../lib/documents/metadata";

export const metadata = englishMetadata("About", "The spin.clinic project, its operator, funding, independence and contact details. We show how messages are constructed.", "/o-nas", "/en/about");

export default function AboutPage() {
  return <AboutDocument lang="en" />;
}
