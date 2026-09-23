import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/** Wyjaśnienia, „dlaczego to tu jest”. */
export function InfoIcon({ size = 24, className, title }: IconProps) {
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
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5.5" />
      <line x1="12" y1="7.6" x2="12" y2="7.61" />
    </svg>
  );
}
