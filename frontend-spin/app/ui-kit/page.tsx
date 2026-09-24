import type { Metadata } from "next";
import { UiKitShowcase } from "@spin-clinic/ui/kit";

export const metadata: Metadata = {
  title: "Biblioteka UI (demo) — spin.clinic",
  description: "Demonstracja komponentów interfejsu. Wszystkie dane są fikcyjne.",
  robots: { index: false, follow: false },
};

export default function UiKitPage() {
  return <UiKitShowcase />;
}
