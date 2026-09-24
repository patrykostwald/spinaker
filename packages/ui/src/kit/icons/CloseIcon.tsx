import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/** Krzyżyk. Klasa `sc-icon--close` w kit.css obraca go o 90° przy najechaniu (poza przyciskiem). */
export function CloseIcon({ size = 24, className, title }: IconProps) {
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
      className={["sc-icon", "sc-icon--close", className].filter(Boolean).join(" ")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M6 6 18 18M18 6 6 18" />
    </svg>
  );
}
