import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/** Otwarcie filtrów. Licznik aktywnych filtrów obok ikony animuje konsument (MorphValue). */
export function FilterIcon({ size = 24, className, title }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={iconStroke(size)}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M4 5h16l-6.2 7.4V19l-3.6 1.8v-8.4z" />
    </svg>
  );
}
