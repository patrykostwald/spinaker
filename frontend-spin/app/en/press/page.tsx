import { PressDocument } from "../../../lib/documents/PressDocument";
import { englishMetadata } from "../../../lib/documents/metadata";

export const metadata = englishMetadata("For the press", "Weekly reports and data for newsrooms and institutions, analysis scope and guidance on citing AI diagnoses.", "/dla-redakcji", "/en/press");

export default function PressPage() {
  return <PressDocument lang="en" />;
}
