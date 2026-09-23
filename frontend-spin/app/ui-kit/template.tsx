"use client";

/**
 * template.tsx — TYLKO segment /ui-kit (docs/UI_KIT_PLAN.md → «Переходы между
 * страницами»). W odróżnieniu od layout.tsx przemontowuje się przy KAŻDEJ nawigacji
 * wewnątrz segmentu, co daje animację wejścia bez hacków z „zamrożonym routerem”
 * (App Router nie potrafi animować wyjścia trasy — patrz plan, ta sama sekcja).
 *
 * NIE kopiować do app/template.tsx: to ożywiłoby wejście na WSZYSTKICH żywych stronach
 * już dziś, a to zmiana odłożona do etapu 2 (kryterium przyjęcia etapu 1 — „żywe strony
 * wyglądają dokładnie jak wcześniej”). Na etapie 2 plik po prostu przenosi się do korzenia.
 */

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { useMotionTokens } from "@spin-clinic/ui/kit";

export default function UiKitTemplate({ children }: { children: ReactNode }) {
  const m = useMotionTokens();
  return (
    <motion.div
      initial={{ opacity: 0, y: m.rise }}
      animate={{ opacity: 1, y: 0 }}
      transition={m.t("fade")}
    >
      {children}
    </motion.div>
  );
}
