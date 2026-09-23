/**
 * @spin-clinic/ui/kit — точка входа библиотеки нового визуального языка.
 * Экспорты только явные, без `export *` из компонентов: конфликт имён должен ронять сборку,
 * а не молча теряться в рантайме. Владелец файла — R0 (интегратор).
 */

// Контракты (волна 0)
export { springs, responsive, type SpringName } from "./motion/springs";
export { project, rubberband, clamp, projectedTarget, shouldDismiss, VELOCITY_COMMIT, DISTANCE_COMMIT } from "./motion/physics";
export { useMotionTokens, ForcedReducedMotionContext, type MotionTokens } from "./motion/useMotionTokens";
export { MotionRoot } from "./motion/MotionRoot";
export * from "./tokens";

// Витрина
export { UiKitShowcase } from "./showcase/UiKitShowcase";
export {
  makeArticle,
  makeArticles,
  demoImage,
  FIXTURE_ARTICLES,
  FIXTURE_SOURCES,
  FIXTURE_STATES,
  FIXTURE_STRIPS,
  POLISH_SPECIMEN,
  POLISH_LONG_WORDS,
} from "./showcase/fixtures";

// Волна 1 — R1 иконки и контролы, R2 кнопки и дропдаун, R3 карточка, R4 примитивы движения
// Волна 2 — R5 портал, R6 навигация и футер, R7 мобильный слой
// (экспорты дописывает интегратор при мерже каждого пакета)
