import { MethodologyDocument } from "../../../lib/documents/MethodologyDocument";
import { englishMetadata } from "../../../lib/documents/metadata";

export const metadata = englishMetadata("Methodology", "How we select posts, combine AI assessments and calculate Clinic data. Scope, limitations and error reporting.", "/metodologia", "/en/methodology");

export default function MethodologyPage() {
  return <MethodologyDocument lang="en" />;
}
