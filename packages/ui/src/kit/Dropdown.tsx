"use client";

/**
 * Dropdown — jedna implementacja zamiast trzech (docs/UI_KIT_PLAN.md → «Компоненты», «Дропдаун»).
 * Tryby: menu (akcje) · single (wybór jednej wartości) · multi (wybór wielu, panel nie zamyka się na wyborze).
 * Wyzwalacz to własny Button; panel rośnie z punktu wyzwalacza i odwraca się w górę przy dolnej krawędzi ekranu.
 */

import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  type Ref,
} from "react";
import { Button, type ButtonVariant } from "./Button";
import { useMotionTokens } from "./motion/useMotionTokens";
import { useDismissable } from "./useDismissable";
// R7: BottomSheet zamiast zaślepki popovera dla presentation="sheet" / "auto" ≤ 480px.
import { BottomSheet } from "./mobile/BottomSheet";
import { BREAKPOINTS } from "./tokens";

// TODO(R1): zamienić na kit/icons po scaleniu — na razie tymczasowy inline SVG własny dla R2.
function ChevronDownIcon() {
  return (
    <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// TODO(R1): zamienić na kit/icons po scaleniu — na razie tymczasowy inline SVG własny dla R2.
function CheckIcon() {
  return (
    <svg width="100%" height="100%" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M5 12.5l4.5 4.5L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export type DropdownMode = "menu" | "single" | "multi";
export type DropdownItem = { value: string; label: string; description?: string; disabled?: boolean };
export type DropdownPresentation = "popover" | "sheet" | "auto";
export type DropdownAlign = "start" | "end";

export type DropdownProps = {
  label: string;
  ariaLabel?: string;
  mode: DropdownMode;
  items: DropdownItem[];
  value?: string | string[];
  onSelect?: (item: DropdownItem) => void;
  onChange?: (value: string | string[]) => void;
  align?: DropdownAlign;
  width?: number | "trigger";
  triggerVariant?: ButtonVariant;
  footer?: ReactNode;
  /**
   * 'popover' — panel rosnący z wyzwalacza. 'sheet' — zawsze BottomSheet (kit/mobile).
   * 'auto' — BottomSheet poniżej BREAKPOINTS.phone (481px), inaczej popover. (R7)
   */
  presentation?: DropdownPresentation;
  /** Wygodne dla wystawek/dema — panel startuje otwarty, bez zmiany kontraktu innych propsów. */
  defaultOpen?: boolean;
};

const TYPEAHEAD_MS = 250;
const CASCADE_STEP = 0.02;
const CASCADE_CAP = 8;

export function Dropdown({
  label,
  ariaLabel,
  mode,
  items,
  value,
  onSelect,
  onChange,
  align = "start",
  width,
  triggerVariant = "secondary",
  footer,
  presentation = "popover",
  defaultOpen = false,
}: DropdownProps) {
  const m = useMotionTokens();
  const instanceId = useId();
  const panelId = `sc-dropdown-panel-${instanceId}`;
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(defaultOpen);
  const [placement, setPlacement] = useState<"bottom" | "top">("bottom");
  const [triggerWidth, setTriggerWidth] = useState<number>();

  // R7: presentation="auto" przełącza się na dolny arkusz poniżej progu telefonu (BREAKPOINTS.phone).
  const [isPhoneViewport, setIsPhoneViewport] = useState(false);
  useEffect(() => {
    if (presentation !== "auto") return;
    const mql = window.matchMedia(`(max-width: ${BREAKPOINTS.phone}px)`);
    const update = () => setIsPhoneViewport(mql.matches);
    update();
    mql.addEventListener("change", update);
    return () => mql.removeEventListener("change", update);
  }, [presentation]);
  const useSheet = presentation === "sheet" || (presentation === "auto" && isPhoneViewport);

  const enabledIndexes = useMemo(
    () => items.map((item, index) => (item.disabled ? -1 : index)).filter((index) => index >= 0),
    [items],
  );
  const [activeIndex, setActiveIndex] = useState(enabledIndexes[0] ?? 0);
  const typeahead = useRef({ buffer: "", timer: undefined as ReturnType<typeof setTimeout> | undefined });

  function close() {
    setOpen(false);
  }

  const panelRef = useDismissable<HTMLDivElement>({
    open,
    onClose: close,
    triggerRef: triggerRef as React.RefObject<HTMLElement>,
  });

  function openMenu() {
    const trigger = triggerRef.current;
    if (trigger) {
      const rect = trigger.getBoundingClientRect();
      const lowerThird = (window.innerHeight * 2) / 3;
      setPlacement(rect.top > lowerThird ? "top" : "bottom");
      setTriggerWidth(rect.width);
    }
    const selectedValues = Array.isArray(value) ? value : value ? [value] : [];
    const selectedIndex = items.findIndex((item) => !item.disabled && selectedValues.includes(item.value));
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : enabledIndexes[0] ?? 0);
    setOpen(true);
  }

  function toggle() {
    if (open) close();
    else openMenu();
  }

  function isChecked(item: DropdownItem): boolean {
    if (mode === "single") return value === item.value;
    if (mode === "multi") return Array.isArray(value) && value.includes(item.value);
    return false;
  }

  function activate(item: DropdownItem, index: number) {
    if (item.disabled) return;
    setActiveIndex(index);
    if (mode === "menu") {
      onSelect?.(item);
      close();
      triggerRef.current?.focus();
    } else if (mode === "single") {
      onChange?.(item.value);
      close();
      triggerRef.current?.focus();
    } else {
      const current = Array.isArray(value) ? value : [];
      const next = current.includes(item.value)
        ? current.filter((entry) => entry !== item.value)
        : [...current, item.value];
      onChange?.(next);
      // multi nie zamyka panelu — wybór można poprawiać dalej.
    }
  }

  function moveActive(delta: number) {
    if (enabledIndexes.length === 0) return;
    const pos = enabledIndexes.indexOf(activeIndex);
    const nextPos = ((pos < 0 ? 0 : pos) + delta + enabledIndexes.length) % enabledIndexes.length;
    setActiveIndex(enabledIndexes[nextPos]);
  }

  function onListKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        moveActive(1);
        return;
      case "ArrowUp":
        event.preventDefault();
        moveActive(-1);
        return;
      case "Home":
        event.preventDefault();
        if (enabledIndexes.length) setActiveIndex(enabledIndexes[0]);
        return;
      case "End":
        event.preventDefault();
        if (enabledIndexes.length) setActiveIndex(enabledIndexes[enabledIndexes.length - 1]);
        return;
      case "Enter":
      case " ": {
        event.preventDefault();
        const item = items[activeIndex];
        if (item) activate(item, activeIndex);
        return;
      }
      default: {
        if (event.key.length !== 1 || !/\S/.test(event.key)) return;
        const buf = typeahead.current;
        clearTimeout(buf.timer);
        buf.buffer += event.key.toLowerCase();
        const match = items.findIndex((item) => !item.disabled && item.label.toLowerCase().startsWith(buf.buffer));
        if (match >= 0) setActiveIndex(match);
        buf.timer = setTimeout(() => {
          buf.buffer = "";
        }, TYPEAHEAD_MS);
      }
    }
  }

  // Fokus podąża za aktywnym elementem (roving tabindex) — tylko podczas otwarcia panelu.
  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => {
      listRef.current?.querySelector<HTMLElement>('[data-active="true"]')?.focus();
    });
    return () => cancelAnimationFrame(id);
  }, [open, activeIndex]);

  useEffect(() => {
    return () => clearTimeout(typeahead.current.timer);
  }, []);

  const resolvedWidth = typeof width === "number" ? width : width === "trigger" ? triggerWidth : undefined;
  const originX = align === "end" ? "100%" : "0%";
  const originY = placement === "top" ? "100%" : "0%";
  const yFrom = m.reduced ? 0 : placement === "top" ? 4 : -4;
  const scaleFrom = m.reduced ? 1 : 0.96;

  // R7: lista pozycji wydzielona, żeby popover i BottomSheet renderowały DOKŁADNIE tę samą
  // klawiaturę/role/kaskadę — różni się tylko opakowanie (panel na transform-origin vs arkusz).
  function renderItemsList() {
    return (
      <LayoutGroup id={instanceId}>
        <div ref={listRef} className="sc-dropdown__list" role="presentation" onKeyDown={onListKeyDown}>
          {items.map((item, index) => {
            const checked = isChecked(item);
            const isActive = index === activeIndex;
            const role = mode === "single" ? "menuitemradio" : mode === "multi" ? "menuitemcheckbox" : "menuitem";
            return (
              <motion.div
                key={item.value}
                role={role}
                aria-checked={mode === "menu" ? undefined : checked}
                aria-disabled={item.disabled || undefined}
                data-active={isActive || undefined}
                tabIndex={isActive ? 0 : -1}
                className={"sc-dropdown__item" + (isActive && mode !== "menu" ? " sc-dropdown__item--active" : "")}
                onClick={() => activate(item, index)}
                onPointerEnter={() => !item.disabled && setActiveIndex(index)}
                initial={{ opacity: 0, y: m.rise }}
                animate={{ opacity: 1, y: 0 }}
                transition={m.t("ui", { delay: Math.min(index, CASCADE_CAP - 1) * CASCADE_STEP })}
              >
                {isActive && mode === "menu" && (
                  <motion.span
                    layoutId={`sc-dropdown-highlight-${instanceId}`}
                    className="sc-dropdown__highlight"
                    transition={m.t("move")}
                  />
                )}
                <span className="sc-dropdown__item-text">
                  <span className="sc-t-body-s">{item.label}</span>
                  {item.description && (
                    <span className="sc-dropdown__item-desc sc-t-caption sc-text-3">{item.description}</span>
                  )}
                </span>
                {mode === "single" && checked && (
                  <motion.span
                    layoutId={`sc-dropdown-check-${instanceId}`}
                    className="sc-dropdown__check"
                    transition={m.t("move")}
                  >
                    <CheckIcon />
                  </motion.span>
                )}
                {mode === "multi" && (
                  <motion.span
                    className="sc-dropdown__check"
                    initial={false}
                    animate={{ scale: checked ? 1 : 0.6, opacity: checked ? 1 : 0 }}
                    transition={m.t("expand")}
                  >
                    <CheckIcon />
                  </motion.span>
                )}
              </motion.div>
            );
          })}
        </div>
      </LayoutGroup>
    );
  }

  return (
    <div className="sc-dropdown">
      <Button
        ref={triggerRef as Ref<HTMLButtonElement>}
        variant={triggerVariant}
        size="md"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={ariaLabel}
        onClick={toggle}
        iconEnd={
          <motion.span
            className="sc-dropdown__chevron"
            animate={{ rotate: open ? 180 : 0 }}
            transition={m.t("ui")}
          >
            <ChevronDownIcon />
          </motion.span>
        }
      >
        {label}
      </Button>

      {/* R7: presentation="sheet" (lub "auto" ≤ BREAKPOINTS.phone) — pozycje w BottomSheet zamiast
          popovera. Ta sama klawiatura (onListKeyDown), te same role — patrz renderItemsList() wyżej. */}
      {useSheet ? (
        <BottomSheet open={open} onClose={close} title={ariaLabel ?? label} id={panelId}>
          {renderItemsList()}
          {footer && <div className="sc-dropdown__footer">{footer}</div>}
        </BottomSheet>
      ) : (
        <AnimatePresence>
          {open && (
            <motion.div
              ref={panelRef}
              id={panelId}
              role="menu"
              aria-label={ariaLabel ?? label}
              className="sc-dropdown__panel sc-chrome"
              data-align={align}
              data-placement={placement}
              style={{
                transformOrigin: `${originX} ${originY}`,
                width: resolvedWidth,
                ...(align === "end" ? { right: 0 } : { left: 0 }),
                ...(placement === "top" ? { bottom: "calc(100% + 8px)" } : { top: "calc(100% + 8px)" }),
              }}
              initial={{ opacity: 0, scale: scaleFrom, y: yFrom }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: scaleFrom, y: yFrom }}
              transition={open ? m.t("ui") : m.t("collapse")}
            >
              {renderItemsList()}
              {footer && <div className="sc-dropdown__footer">{footer}</div>}
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}
