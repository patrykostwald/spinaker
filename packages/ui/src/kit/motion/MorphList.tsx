"use client";

import { AnimatePresence, motion } from "framer-motion";
import { LayoutGroup } from "framer-motion";
import type { ReactNode } from "react";
import { useMotionTokens } from "./useMotionTokens";

type ListTag = "div" | "ul" | "ol";
type ItemTag = "div" | "li";

export type MorphListProps<T> = {
  /** Уникальный id `LayoutGroup` — несвязанные списки не должны измеряться вместе (бюджет производительности). */
  id: string;
  items: T[];
  getKey: (item: T) => string | number;
  renderItem: (item: T, index: number) => ReactNode;
  as?: ListTag;
  itemAs?: ItemTag;
  className?: string;
  itemClassName?: string | ((item: T, index: number) => string | undefined);
};

/**
 * Коллекция: добавление, удаление, переупорядочивание, фильтрация — одним примитивом.
 * `AnimatePresence` + `layout="position"` на элементах (дешевле полного `layout`, см.
 * docs/UI_KIT_PLAN.md → «Бюджет производительности»). Уцелевшие элементы едут (`move`),
 * ушедшие гаснут (`collapse`: opacity→0, scale .96), пришедшие проявляются каскадом,
 * ограниченным `staggerCap` позициями. Появление — через `whileInView`
 * (IntersectionObserver внутри framer-motion), никогда не подписка на скролл: и первая
 * отрисовка списка, и более поздние добавления проходят один и тот же путь.
 */
export function MorphList<T>({
  id,
  items,
  getKey,
  renderItem,
  as: Container = "div",
  itemAs: Item = "div",
  className,
  itemClassName,
}: MorphListProps<T>) {
  const m = useMotionTokens();
  const MotionContainer = motion[Container];
  const MotionItem = motion[Item];

  return (
    <LayoutGroup id={id}>
      <MotionContainer className={className}>
        <AnimatePresence initial={true}>
          {items.map((item, index) => {
            const key = getKey(item);
            const delay = Math.min(index, m.staggerCap) * m.stagger;
            const itemClass =
              typeof itemClassName === "function" ? itemClassName(item, index) : itemClassName;
            return (
              <MotionItem
                key={key}
                layout="position"
                className={itemClass}
                initial={{ opacity: 0, y: m.rise }}
                whileInView={{ opacity: 1, y: 0, transition: m.t("ui", { delay }) }}
                viewport={{ once: true, margin: "0px 0px -10% 0px" }}
                exit={{ opacity: 0, scale: m.scale(0.96), transition: m.t("collapse") }}
                transition={{ layout: m.t("move") }}
              >
                {renderItem(item, index)}
              </MotionItem>
            );
          })}
        </AnimatePresence>
      </MotionContainer>
    </LayoutGroup>
  );
}
