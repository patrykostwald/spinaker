import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

export interface ChevronDownIconProps extends IconProps {
  /** Gdy true — obrócony o 180° (panel/select rozwinięty). Obrót idzie przez CSS transition, nie przez framer. */
  open?: boolean;
}

/** Szewron w dół — selecty, <details>, akordeony. Obraca się o 180° przy rozwinięciu. */
export function ChevronDownIcon({ size = 24, className, title, open = false }: ChevronDownIconProps) {
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
      className={["sc-icon", "sc-icon--chevron", className].filter(Boolean).join(" ")}
      style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)" }}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <path d="M6 9.5 12 15.5 18 9.5" />
    </svg>
  );
}
