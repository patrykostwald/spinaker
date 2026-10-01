import { CouncilCharterDocument } from "../../../../lib/documents/CouncilCharterDocument";
import { englishMetadata } from "../../../../lib/documents/metadata";

export const metadata = englishMetadata("AI Council (Konsylium) Charter", "The working principles of the AI Council (Konsylium), Charter acceptance and how to report errors.", "/konsylium/karta", "/en/council/charter");

export default function CouncilCharterPage() {
  return <CouncilCharterDocument lang="en" />;
}
