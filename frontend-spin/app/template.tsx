"use client";

import { motion } from "framer-motion";
import { useEffect, type ReactNode } from "react";
import { useMotionTokens } from "@spin-clinic/ui/kit";

export default function RouteTemplate({ children }: { children: ReactNode }) {
  const m = useMotionTokens();
  useEffect(() => {
    // The database restores its position after loading the saved result pages.
    if (window.location.pathname === "/klinika/diagnozy") return;
    // Trwałe linki przekazów wskazują konkretną stronę dnia.
    if (window.location.hash) {
      document.getElementById(window.location.hash.slice(1))?.scrollIntoView();
      return;
    }
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, []);
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
