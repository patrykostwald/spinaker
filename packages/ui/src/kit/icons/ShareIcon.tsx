import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/** Publikacja w X. Unosi się o 1px przy najechaniu. */
export function ShareIcon({ size = 24, className, title }: IconProps) {
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
      className={["sc-icon", "sc-icon--share", className].filter(Boolean).join(" ")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M12 15V4M8 8l4-4 4 4" />
      <path d="M5 13v6a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-6" />
    </svg>
  );
}
