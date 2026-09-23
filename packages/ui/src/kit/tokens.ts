/**
 * Значения дизайн-системы, нужные в JS (docs/UI_KIT_PLAN.md).
 * Источник истины для цвета и отступов — kit.css; здесь только то, что
 * читает код: радиусы для инлайновых стилей морфинга и параметры карточек.
 */

export const CARD_SIZES = ["mini", "compact", "medium", "large"] as const;
export type CardSize = (typeof CARD_SIZES)[number];

/** Радиусы, px. Морфинг задаёт радиус инлайново, поэтому значения нужны в JS. */
export const RADIUS = { xs: 6, sm: 10, md: 14, lg: 18, xl: 22, "2xl": 28, pill: 999 } as const;

/** Внешний радиус, внутренний отступ и подъём при наведении — по размеру карточки. */
export const CARD_SPEC: Record<CardSize, { radius: number; padding: number; lift: number; previewScale: number }> = {
  mini: { radius: RADIUS.lg, padding: 10, lift: 2, previewScale: 1.1 },
  compact: { radius: RADIUS.lg, padding: 12, lift: 2, previewScale: 1.1 },
  medium: { radius: RADIUS.xl, padding: 14, lift: 3, previewScale: 1.12 },
  large: { radius: RADIUS["2xl"], padding: 18, lift: 4, previewScale: 1.14 },
};

/** Подсветка при наведении (ступень A). */
export const HOVER_SCALE = 1.03;
/** Задержка намерения перед предпросмотром (ступень B), мс. */
export const PREVIEW_DELAY_MS = 400;
/** Долгое нажатие на тач-устройстве для захвата перетаскивания, мс. */
export const LONG_PRESS_MS = 250;

/** Точки перелома. */
export const BREAKPOINTS = { phone: 480, tablet: 900 } as const;

/** Имена токенов цвета — для витрины и проверок. */
export const COLOR_TOKENS = [
  "bg", "surface", "surface-2", "surface-3", "chrome", "line", "line-strong", "line-hover", "hairline",
  "text", "text-2", "text-3", "accent", "accent-hover", "accent-press", "accent-soft", "on-accent", "focus",
  "live", "positive", "warning", "negative", "glow", "glow-strong",
] as const;

export const SPACING_TOKENS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] as const;
export const RADIUS_TOKENS = ["xs", "sm", "md", "lg", "xl", "2xl"] as const;
export const TYPE_TOKENS = ["display", "title-l", "title-m", "title-s", "title-xs", "body", "body-s", "meta", "caption"] as const;
