import type { IconProps } from "./types";
import { iconStroke, iconA11yProps } from "./types";

/**
 * Ładowanie. Jedyna zapętlona animacja w systemie: obrót 1s przez CSS (`.sc-icon--spinner`
 * w kit.css), nie przez framer-motion — nie ma sensu płacić za JS-owy re-render co klatkę
 * dla nieskończonej pętli. Globalny kill-switch `prefers-reduced-motion` w kit.css ustawia
 * wszystkim elementom `.sc-root` animation-iteration-count:1 i animation-duration:1ms, więc
 * przy zredukowanym ruchu obrót zatrzymuje się natychmiast — zostaje statyczny łuk (kropka).
 * Struktura znaczników jest zawsze taka sama (bez rozgałęzień na `reduced` — patrz zasada 6).
 */
export function SpinnerIcon({ size = 24, className, title }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={iconStroke(size)}
      strokeLinecap="round"
      className={["sc-icon", "sc-icon--spinner", className].filter(Boolean).join(" ")}
      {...iconA11yProps(title)}
    >
      {title ? <title>{title}</title> : null}
      <circle cx="12" cy="12" r="9" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" />
    </svg>
  );
}
