import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/** Materiał wideo. Skaluje się do 1.1 przy najechaniu na kartę (klasa sc-icon--play). */
export function PlayIcon({ size = 24, className, title }: IconProps) {
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
      className={["sc-icon", "sc-icon--play", className].filter(Boolean).join(" ")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M8 5.5v13l11-6.5z" />
    </svg>
  );
}
