/**
 * Wspólny kontrakt ikon (docs/UI_KIT_PLAN.md → «Каталог иконок»).
 * Siatka 24×24, currentColor, bez wypełnień. Grubość kreski zależy od rozmiaru:
 * 16px → 1.25px, 20/24px → 1.5px (mniejsze ikony NIE skalują grubości proporcjonalnie).
 */

export type IconSize = 16 | 20 | 24;

export interface IconProps {
  /** Rozmiar w px: 16 / 20 / 24. Domyślnie 24. */
  size?: IconSize;
  className?: string;
  /**
   * Gdy podane — ikona staje się widoczna dla technologii asystujących
   * (dostaje <title> i role="img") i przestaje być aria-hidden.
   * Domyślnie ikony są dekoracyjne (aria-hidden), bo prawie zawsze towarzyszy im tekst.
   */
  title?: string;
}

export function iconStroke(size: IconSize): number {
  return size === 16 ? 1.25 : 1.5;
}

export function iconA11yProps(title?: string): { "aria-hidden"?: true; role?: "img" } {
  return title ? { role: "img" } : { "aria-hidden": true };
}
