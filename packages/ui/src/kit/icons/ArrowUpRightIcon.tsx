import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/** Link do oryginału / wyjście zewnętrzne. Przesuwa się po przekątnej o 2px przy najechaniu. */
export function ArrowUpRightIcon({ size = 24, className, title }: IconProps) {
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
      className={["sc-icon", "sc-icon--arrow", className].filter(Boolean).join(" ")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M7 17 17 7M9 7h8v8" />
    </svg>
  );
}
