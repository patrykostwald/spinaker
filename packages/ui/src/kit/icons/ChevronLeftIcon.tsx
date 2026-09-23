import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/** Strzałka przewijania lент w lewo. Przesuwa się o 2px w kierunku wskazywanym przy najechaniu. */
export function ChevronLeftIcon({ size = 24, className, title }: IconProps) {
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
      className={["sc-icon", "sc-icon--chevron-left", className].filter(Boolean).join(" ")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M14.5 6 8.5 12l6 6" />
    </svg>
  );
}
