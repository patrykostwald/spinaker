import { CouncilDocument } from "../../../lib/documents/CouncilDocument";
import { englishMetadata } from "../../../lib/documents/metadata";

export const metadata = englishMetadata("AI Council (Konsylium)", "How AI models from different companies produce a joint diagnosis: the process, roles, membership, votes, tools and principles.", "/konsylium", "/en/council");

export default function CouncilPage() {
  return <CouncilDocument lang="en" />;
}
