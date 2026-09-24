import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/**
 * Uchwyt przeciągania polosy (dwie kolumny × trzy rzędy kropek).
 * Kropki są krótkimi odcinkami z okrągłym zakończeniem — system nie używa wypełnień.
 * Widoczność przy najechaniu na polosę zarządza kontener polosy (R4); tu tylko kształt.
 */
export function GripIcon({ size = 24, className, title }: IconProps) {
  const w = iconStroke(size);
  const cols = [9, 15];
  const rows = [7, 12, 17];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={w}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={["sc-icon", "sc-icon--grip", className].filter(Boolean).join(" ")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      {cols.flatMap((x) => rows.map((y) => <line key={`${x}-${y}`} x1={x} y1={y} x2={x} y2={y + 0.01} />))}
    </svg>
  );
}
