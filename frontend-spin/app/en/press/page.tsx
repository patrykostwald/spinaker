import { PressDocument } from "../../../lib/documents/PressDocument";
import { englishMetadata } from "../../../lib/documents/metadata";

export const metadata = englishMetadata("For the press", "How to cite AI diagnoses, link to sources and methodology, and join the authorised context thread pilot.", "/dla-redakcji", "/en/press");

export default function PressPage() {
  return <PressDocument lang="en" />;
}
