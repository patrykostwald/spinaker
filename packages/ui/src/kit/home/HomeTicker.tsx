"use client";

/**
 * Rząd czterech najnowszych materiałów (`mini`) nad heroem — wzór: pasek „ostatnie wyniki”
 * w referencji. Karty wchodzą kaskadą (`stagger` z tokenów ruchu). Na tablecie 2×2.
 */

import { motion } from "framer-motion";
import { NewsCard } from "../NewsCard";
import { useMotionTokens } from "../motion/useMotionTokens";
import type { Article } from "../../types";
import { EmptySlot } from "./Strip";

export function HomeTicker({ articles }: { articles: Article[] }) {
  const m = useMotionTokens();
  const slots = Array.from({ length: 4 }, (_, i) => articles[i] ?? null);
  return (
    <section className="sc-home-ticker" aria-label="Najnowsze materiały">
      {slots.map((article, index) => (
        <motion.div
          key={article?.id ?? `empty-${index}`}
          className="sc-home-ticker__cell"
          initial={{ opacity: 0, y: m.rise }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "0px 0px -8% 0px" }}
          transition={m.t("ui", { delay: index * m.stagger })}
        >
          {article ? <NewsCard article={article} size="mini" headingLevel={3} /> : <EmptySlot index={index + 1} label="Najnowszy materiał" />}
        </motion.div>
      ))}
    </section>
  );
}
