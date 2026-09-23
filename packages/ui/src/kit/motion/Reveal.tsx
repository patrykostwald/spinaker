"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";
import { useMotionTokens } from "./useMotionTokens";

export type RevealProps = {
  when: boolean;
  children: ReactNode;
  /** Задержка появления, секунды (каскады блоков внутри развёрнутой карточки/оверлея). */
  delay?: number;
  as?: "div" | "span" | "li";
  className?: string;
};

/**
 * Появление и исчезновение любого узла: fade + `rise` (смещение по Y, 0 при уменьшенном
 * движении). Вход — `ui`, выход — `collapse` (без задержки: асимметрия намеренная,
 * раскрытие требует намерения, сворачивание — нет).
 */
export function Reveal({ when, children, delay = 0, as: Tag = "div", className }: RevealProps) {
  const m = useMotionTokens();
  const MotionTag = motion[Tag];
  return (
    <AnimatePresence initial={true}>
      {when && (
        <MotionTag
          className={className}
          initial={{ opacity: 0, y: m.rise }}
          animate={{ opacity: 1, y: 0, transition: m.t("ui", { delay }) }}
          exit={{ opacity: 0, y: 0, transition: m.t("collapse") }}
        >
          {children}
        </MotionTag>
      )}
    </AnimatePresence>
  );
}

export type RevealHeightProps = {
  when: boolean;
  children: ReactNode;
  /** Задержка появления содержимого относительно старта разворачивания высоты. */
  contentDelay?: number;
  className?: string;
};

/**
 * Морфинг высоты для раскрытия/сворачивания (аккордеон, фильтры `<details>`, ошибка формы).
 * Единственное разрешённое исключение из правила «только transform/opacity» — и то на
 * ОБЁРТКЕ: `height` анимируется на внешнем `motion.div` с `overflow: hidden`, а содержимое
 * внутри анимирует только `opacity` (кросс-фейд). Раскрытие — `expand` (здесь живёт bounce
 * владельца), сворачивание — `collapse`, без отскока, содержимое гаснет первым.
 */
export function RevealHeight({ when, children, contentDelay = 0.06, className }: RevealHeightProps) {
  const m = useMotionTokens();
  return (
    <AnimatePresence initial={true}>
      {when && (
        <motion.div
          className={className}
          style={{ overflow: "hidden" }}
          initial={{ height: 0 }}
          animate={{ height: "auto", transition: m.t("expand") }}
          exit={{ height: 0, transition: m.t("collapse") }}
        >
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: m.t("fade", { delay: contentDelay }) }}
            exit={{ opacity: 0, transition: m.t("collapse", { delay: 0 }) }}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
