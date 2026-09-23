"use client";

/**
 * Button — jedyny komponent przycisku w bibliotece (docs/UI_KIT_PLAN.md → «Компоненты», «Каталог кнопок»).
 * Warianty, rozmiary i kształty różnicują propsy, nie osobne implementacje.
 */

import Link from "next/link";
import { AnimatePresence, motion, type Transition } from "framer-motion";
import {
  forwardRef,
  type AriaAttributes,
  type CSSProperties,
  type DOMAttributes,
  type MouseEvent,
  type ReactNode,
  type Ref,
} from "react";
import { useMotionTokens } from "./motion/useMotionTokens";

// TODO(R1): zamienić na kit/icons po scaleniu — na razie tymczasowy inline SVG własny dla R2.
function SpinnerGlyph({ reduced }: { reduced: boolean }) {
  if (reduced) {
    return (
      <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="3" fill="currentColor" />
      </svg>
    );
  }
  return (
    <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="sc-btn__spinner-svg">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeDasharray="40 16" />
    </svg>
  );
}

export type ButtonVariant = "primary" | "secondary" | "quiet" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";
export type ButtonShape = "rounded" | "pill" | "icon";

const ICON_PX: Record<ButtonSize, number> = { sm: 16, md: 18, lg: 20 };

type ButtonOwnProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  pressed?: boolean;
  loading?: boolean;
  iconStart?: ReactNode;
  iconEnd?: ReactNode;
  href?: string;
  fullWidth?: boolean;
  onClick?: (event: MouseEvent<HTMLButtonElement | HTMLAnchorElement>) => void;
};

/**
 * Klucze zdarzeń, którymi framer-motion nadaje własny (gestowy) typ sygnatury —
 * kolidują z natywnymi typami DOM przy spreadowaniu na motion.button/motion(Link).
 */
type MotionConflictingKeys =
  | "onDrag"
  | "onDragStart"
  | "onDragEnd"
  | "onAnimationStart"
  | "onAnimationEnd"
  | "onAnimationIteration"
  | "onTransitionEnd";

/**
 * Baza atrybutów natywnych oparta o wspólny `HTMLElement`, nie `HTMLButtonElement`:
 * inaczej każdy handler zdarzenia (onFocus, onKeyDown, …) trzeba by osobno godzić
 * z typami motion(Link) przy renderze jako <a>. Element-specific atrybuty pomijamy
 * świadomie (formAction, popoverTarget itd. nie są tu potrzebne).
 */
type NativeProps = Omit<DOMAttributes<HTMLElement>, "children" | MotionConflictingKeys> &
  AriaAttributes & {
    id?: string;
    tabIndex?: number;
    title?: string;
    name?: string;
    form?: string;
    value?: string | number;
    disabled?: boolean;
    className?: string;
    style?: CSSProperties;
    /** np. data-lit="true" — witryna wymusza stan naświetlenia bez realnego hover. */
    [dataAttr: `data-${string}`]: string | boolean | undefined;
  };

type ButtonTextProps = ButtonOwnProps &
  NativeProps & {
    shape?: "rounded" | "pill";
    children: ReactNode;
    type?: "button" | "submit" | "reset";
  };

type ButtonIconOnlyProps = ButtonOwnProps &
  NativeProps & {
    shape: "icon";
    children?: never;
    "aria-label": string;
    type?: "button" | "submit" | "reset";
  };

/** Ikonowy przycisk musi mieć aria-label — wymuszone przeciążeniem typu, nie propem w runtime. */
export type ButtonProps = ButtonTextProps | ButtonIconOnlyProps;

const MotionButton = motion.button;
const MotionLink = motion(Link);

export const Button = forwardRef<HTMLButtonElement | HTMLAnchorElement, ButtonProps>(function Button(props, ref) {
  const {
    variant = "secondary",
    size = "md",
    shape = "rounded",
    pressed,
    loading = false,
    iconStart,
    iconEnd,
    href,
    fullWidth,
    disabled,
    className,
    children,
    type,
    style,
    ...rest
  } = props;

  const m = useMotionTokens();
  const isIconOnly = shape === "icon";
  const iconPx = ICON_PX[size];
  const isDisabled = Boolean(disabled) || loading;

  const hoverTransition: Transition = m.t("ui");
  const tapTransition: Transition = m.t("press");

  const classes = [
    "sc-btn",
    "sc-hoverable",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const spinner = (
    <AnimatePresence>
      {loading && (
        <motion.span
          key="spinner"
          className="sc-btn__spinner"
          style={{ width: iconPx, height: iconPx }}
          initial={{ opacity: 0, scale: m.scale(0.8) }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: m.scale(0.8) }}
          transition={m.t("fade")}
        >
          <SpinnerGlyph reduced={m.reduced} />
        </motion.span>
      )}
    </AnimatePresence>
  );

  const content = isIconOnly ? (
    <>
      <span className="sc-btn__icon" style={{ width: iconPx, height: iconPx }} aria-hidden="true">
        {iconStart ?? iconEnd}
      </span>
      {spinner}
    </>
  ) : (
    <>
      {iconStart && (
        <span className="sc-btn__icon" style={{ width: iconPx, height: iconPx }} aria-hidden="true">
          {iconStart}
        </span>
      )}
      <span className="sc-btn__label">{children}</span>
      {iconEnd && (
        <span className="sc-btn__icon" style={{ width: iconPx, height: iconPx }} aria-hidden="true">
          {iconEnd}
        </span>
      )}
      {spinner}
    </>
  );

  const sharedProps = {
    className: classes,
    style,
    "data-variant": variant,
    "data-size": size,
    "data-shape": shape,
    "data-full-width": fullWidth ? "true" : undefined,
    "aria-pressed": pressed,
    "aria-busy": loading || undefined,
    whileHover: isDisabled ? undefined : { y: m.reduced ? 0 : -1, transition: hoverTransition },
    whileTap: isDisabled ? undefined : { scale: m.scale(0.97), transition: tapTransition },
    ...rest,
  } as const;

  if (href) {
    return (
      <MotionLink
        ref={ref as Ref<HTMLAnchorElement>}
        href={href}
        aria-disabled={isDisabled || undefined}
        onClick={isDisabled ? (event: MouseEvent) => event.preventDefault() : rest.onClick}
        {...sharedProps}
      >
        {content}
      </MotionLink>
    );
  }

  return (
    <MotionButton
      ref={ref as Ref<HTMLButtonElement>}
      type={type ?? "button"}
      disabled={isDisabled}
      {...sharedProps}
    >
      {content}
    </MotionButton>
  );
});
