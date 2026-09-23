import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/** Usuwanie w redakcji. Wieczko (`.sc-icon__lid`) unosi się o 1px przy najechaniu. */
export function TrashIcon({ size = 24, className, title }: IconProps) {
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
      className={["sc-icon", "sc-icon--trash", className].filter(Boolean).join(" ")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M5.5 7.5h13" className="sc-icon__lid" />
      <path d="M9.5 7.5V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2.5" className="sc-icon__lid" />
      <path d="M7 7.5 7.7 19a1 1 0 0 0 1 1h6.6a1 1 0 0 0 1-1l.7-11.5" />
      <path d="M10.3 11v6M13.7 11v6" />
    </svg>
  );
}
