import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/** Dokument, akt, druk. */
export function DocumentIcon({ size = 24, className, title }: IconProps) {
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
      <path d="M7 3.5h6.5L18 8v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-15.5a1 1 0 0 1 1-1Z" />
      <path d="M13.5 3.5V8H18M9 13h6M9 16.5h6" />
    </svg>
  );
}
