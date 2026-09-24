/**
 * Физика жестов (Apple, «Designing Fluid Interfaces»).
 * Чистые функции без React — используются в перетаскивании, нижних листах, закрытии портала.
 */

/**
 * Проекция инерции: куда долетит объект, отпущенный со скоростью `initialVelocity` (px/s).
 * Именно экспоненциальная форма, а не v²/2a из учебника — вторая ощущается иначе.
 * decelerationRate 0.998 — как у прокрутки; 0.99 — резче, лучше для листов и оверлеев.
 */
export function project(initialVelocity: number, decelerationRate = 0.998): number {
  return ((initialVelocity / 1000) * decelerationRate) / (1 - decelerationRate);
}

/** Резиновая граница: чем дальше за край, тем слабее объект следует за пальцем. */
export function rubberband(overshoot: number, dimension: number, constant = 0.55): number {
  return (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot));
}

export const clamp = (value: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, value));

/** Точка примагничивания, ближайшая к тому, куда ДВИЖЕТСЯ жест, а не к тому, где он остановился. */
export function projectedTarget(current: number, velocity: number, snaps: readonly number[]): number {
  const endpoint = current + project(velocity, 0.99);
  return snaps.reduce(
    (best, snap) => (Math.abs(snap - endpoint) < Math.abs(best - endpoint) ? snap : best),
    snaps[0],
  );
}

/** Порог, выше которого решение «закрыть или вернуть» принимает знак скорости, а не позиция. */
export const VELOCITY_COMMIT = 120;
/** Доля высоты поверхности, после которой медленное отпускание считается закрытием. */
export const DISTANCE_COMMIT = 0.22;

/**
 * Решение по отпусканию: `true` — закрыть, `false` — вернуть.
 * Скорость главнее позиции; позиция — только запасной критерий при почти нулевой скорости.
 */
export function shouldDismiss(offset: number, velocity: number, dimension: number): boolean {
  if (Math.abs(velocity) > VELOCITY_COMMIT) return velocity > 0;
  return offset + project(velocity, 0.99) > dimension * DISTANCE_COMMIT;
}
