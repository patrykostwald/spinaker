"use client";

import { useReducedMotion, type Transition } from "framer-motion";
import { createContext, useContext, useMemo } from "react";
import { springs, type SpringName } from "./springs";

export type MotionTokens = {
  /** Пользователь просил меньше движения (или витрина принудительно включила этот режим). */
  reduced: boolean;
  /** Именованная пружина; при уменьшенном движении — короткое затухание без отскока. */
  t: (name: SpringName, overrides?: Transition) => Transition;
  /** Шаг каскада в секундах. 0 при уменьшенном движении. */
  stagger: number;
  /** Сколько первых элементов получают собственную задержку; остальные — последнюю. */
  staggerCap: number;
  /** Смещение при появлении, px. 0 → чистое затухание. */
  rise: number;
  /** Масштаб наведения/нажатия; 1 при уменьшенном движении. */
  scale: (value: number) => number;
  /** Разрешены ли жесты перетаскивания. */
  gestures: boolean;
  /** Морфинг общей раскладки или кроссфейд. */
  morph: boolean;
};

/**
 * Принудительное значение для витрины: позволяет показать режим уменьшенного движения
 * без смены системных настроек. `null` — уважать настройку пользователя.
 */
export const ForcedReducedMotionContext = createContext<boolean | null>(null);

/**
 * Единственный источник переходов в библиотеке. Компоненты никогда не пишут `transition`
 * литералами и никогда не ветвят РАЗМЕТКУ по `reduced` (гидратация) — только значения.
 */
export function useMotionTokens(): MotionTokens {
  const system = useReducedMotion() ?? false;
  const forced = useContext(ForcedReducedMotionContext);
  const reduced = forced ?? system;
  return useMemo<MotionTokens>(
    () => ({
      reduced,
      t: (name, overrides) =>
        reduced ? { ...springs.reduced, ...overrides, bounce: 0 } : { ...springs[name], ...overrides },
      stagger: reduced ? 0 : 0.035,
      staggerCap: reduced ? 0 : 10,
      rise: reduced ? 0 : 8,
      scale: (value) => (reduced ? 1 : value),
      gestures: !reduced,
      morph: !reduced,
    }),
    [reduced],
  );
}
