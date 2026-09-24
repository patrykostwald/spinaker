"use client";

/**
 * Pasek tematów pod szapką (wzór: rząd kategorii w referencji). Te same tematy, które stary
 * `TopTenRedakcji` pokazywał jako pigułki; aktywny temat filtruje mozaikę „Wszystkie źródła”.
 * Wskaźnik przejeżdża wspólnym `layoutId` (MorphIndicator), jak w NavMenu.
 */

import { motion } from "framer-motion";
import { MorphIndicator } from "../motion/MorphIndicator";
import { useMotionTokens } from "../motion/useMotionTokens";

export const HOME_TOPICS: { label: string; value: string }[] = [
  { label: "Polityka", value: "polityka" },
  { label: "Polska", value: "polska" },
  { label: "Świat", value: "swiat" },
  { label: "Gospodarka", value: "biznes" },
  { label: "Społeczeństwo", value: "spoleczenstwo" },
  { label: "Zdrowie", value: "zdrowie" },
  { label: "Technologie", value: "technologie" },
  { label: "Prawo", value: "prawo" },
];

export function HomeCategoryBar({ value, onChange }: { value: string | null; onChange: (topic: string | null) => void }) {
  const m = useMotionTokens();
  const items = [{ label: "Wszystko", value: null as string | null }, ...HOME_TOPICS];
  return (
    <nav className="sc-nav-categories sc-home-catbar" aria-label="Tematy">
      <ul className="sc-nav-categories__list" role="list">
        {items.map((item) => (
          <li key={item.value ?? "all"} className="sc-nav-categories__item">
            <motion.button
              type="button"
              className="sc-nav-categories__link sc-hoverable sc-home-catbar__btn"
              aria-pressed={value === item.value}
              onClick={() => onChange(item.value)}
              whileTap={{ scale: m.scale(0.97), transition: m.t("press") }}
            >
              {item.label}
              <MorphIndicator id="sc-home-catbar" active={value === item.value} />
            </motion.button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
