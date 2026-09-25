"use client";

/**
 * Pasek tematów nad rzędem „Top 10” (wzór: rząd kategorii w referencji). Te same tematy, które stary
 * `TopTenRedakcji` pokazywał jako pigułki; aktywny temat filtruje rząd „Top 10”.
 * Wskaźnik przejeżdża wspólnym `layoutId` (MorphIndicator), jak w NavMenu.
 * Jeden wiersz: [`start` — np. selektor źródeł] [tematy, wyśrodkowane] [`end` — np. pole hasła];
 * boczne sloty mają równe kolumny `1fr`, więc nie przesuwają tematów ze środka.
 */

import { motion } from "framer-motion";
import type { ReactNode } from "react";
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

export function HomeCategoryBar({
  value,
  onChange,
  start,
  end,
}: {
  value: string | null;
  onChange: (topic: string | null) => void;
  start?: ReactNode;
  end?: ReactNode;
}) {
  const m = useMotionTokens();
  const items = [{ label: "Wszystko", value: null as string | null }, ...HOME_TOPICS];
  return (
    <div className="sc-home-catrow">
    {start ? <div className="sc-home-catrow__start">{start}</div> : null}
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
    {end ? <div className="sc-home-catrow__end">{end}</div> : null}
    </div>
  );
}
