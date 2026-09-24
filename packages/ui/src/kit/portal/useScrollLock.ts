"use client";

import { useLayoutEffect } from "react";

/**
 * Блокировка скролла страницы на время оверлея — с компенсацией полосы прокрутки.
 *
 * `useLayoutEffect`, а не `useEffect`: применяем ДО первого закрашенного кадра с оверлеем.
 * Иначе между измерением прямоугольников карточек (для морфинга портала) и первым кадром
 * страница станет уже на ширину полосы прокрутки, и все измеренные прямоугольники сдвинутся —
 * морфинг поедет по горизонтали (docs/UI_KIT_PLAN.md → «Сплошная система движения» → «Портал»).
 *
 * На время блокировки гасим `scroll-behavior: smooth` — он выставлен глобально в
 * frontend-spin/app/globals.css:11 и иначе конфликтует с любой программной прокруткой,
 * которую оверлей делает при открытии/наведении на связанный материал.
 *
 * Внутренний скроллер САМОГО оверлея должен нести `overscroll-behavior: contain` —
 * это забота вызывающего компонента (MaterialSurface, R5): без неё прокрутка содержимого
 * оверлея до упора "протекает" на затемнённую страницу позади него.
 */
export function useScrollLock(active: boolean): void {
  useLayoutEffect(() => {
    if (!active) return;
    const root = document.documentElement;
    const scrollbarGutter = window.innerWidth - root.clientWidth;
    const previous = {
      overflow: root.style.overflow,
      paddingRight: root.style.paddingRight,
      scrollBehavior: root.style.scrollBehavior,
    };
    const existingPadding = parseFloat(getComputedStyle(root).paddingRight || "0") || 0;

    root.style.overflow = "hidden";
    if (scrollbarGutter > 0) {
      root.style.paddingRight = `${existingPadding + scrollbarGutter}px`;
    }
    root.style.scrollBehavior = "auto";

    return () => {
      root.style.overflow = previous.overflow;
      root.style.paddingRight = previous.paddingRight;
      root.style.scrollBehavior = previous.scrollBehavior;
    };
  }, [active]);
}
