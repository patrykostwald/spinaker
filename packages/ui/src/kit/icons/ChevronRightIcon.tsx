import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/** Strzałka przewijania lент w prawo. Przesuwa się o 2px w kierunku wskazywanym przy najechaniu. */
export function ChevronRightIcon({ size = 24, className, title }: IconProps) {
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
      className={["sc-icon", "sc-icon--chevron-right", className].filter(Boolean).join(" ")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M9.5 6 15.5 12l-6 6" />
    </svg>
  );
}
