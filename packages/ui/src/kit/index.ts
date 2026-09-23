/**
 * @spin-clinic/ui/kit — точка входа библиотеки нового визуального языка.
 * Экспорты только явные, без `export *` из компонентов: конфликт имён должен ронять сборку,
 * а не молча теряться в рантайме. Владелец файла — R0 (интегратор).
 */

// Контракты (волна 0)
export { springs, responsive, type SpringName } from "./motion/springs";
export { project, rubberband, clamp, projectedTarget, shouldDismiss, VELOCITY_COMMIT, DISTANCE_COMMIT } from "./motion/physics";
export { useMotionTokens, ForcedReducedMotionContext, type MotionTokens } from "./motion/useMotionTokens";
export { MotionRoot } from "./motion/MotionRoot";
export * from "./tokens";

// Витрина
export { UiKitShowcase } from "./showcase/UiKitShowcase";
export {
  makeArticle,
  makeArticles,
  demoImage,
  FIXTURE_ARTICLES,
  FIXTURE_SOURCES,
  FIXTURE_STATES,
  FIXTURE_STRIPS,
  POLISH_SPECIMEN,
  POLISH_LONG_WORDS,
} from "./showcase/fixtures";

// Волна 1 — R1 иконки и контролы
export {
  type IconProps, type IconSize,
  SearchIcon, CloseIcon,
  ChevronDownIcon, type ChevronDownIconProps,
  ChevronLeftIcon, ChevronRightIcon, ArrowUpRightIcon,
  CheckIcon, type CheckIconProps,
  MinusIcon, type MinusIconProps,
  HeartIcon, type HeartIconProps,
  ShareIcon, GripIcon, FilterIcon, CalendarIcon, ClockIcon, GlobeIcon, PlayIcon, DocumentIcon,
  PlusIcon, type PlusIconProps,
  MenuClose, type MenuCloseProps,
  ThemeIcon, type ThemeIconProps,
  SpinnerIcon, AlertIcon, InfoIcon, TrashIcon, EditIcon,
  EyeIcon, type EyeIconProps,
} from "./icons";
export { Checkbox, type CheckboxProps } from "./Checkbox";
export { Radio, type RadioProps, RadioGroup, type RadioOption, type RadioGroupProps } from "./Radio";
export { Switch, type SwitchProps } from "./Switch";
export { Segmented, type SegmentedOption, type SegmentedProps } from "./Segmented";
export { SearchField, type SearchFieldProps } from "./SearchField";

// Волна 1 — R2 кнопки и дропдаун
export { Button, type ButtonProps, type ButtonVariant, type ButtonSize, type ButtonShape } from "./Button";
export { useDismissable, type UseDismissableOptions } from "./useDismissable";
export {
  Dropdown,
  type DropdownProps, type DropdownItem, type DropdownMode, type DropdownPresentation, type DropdownAlign,
} from "./Dropdown";

// Волна 1 — R3 карточка
export { NewsCard, type NewsCardProps, type NewsCardSize } from "./NewsCard";

// Волна 1 — R4 примитивы движения и жесты
export { Morph, type MorphProps } from "./motion/Morph";
export { MorphList, type MorphListProps } from "./motion/MorphList";
export { MorphIndicator, type MorphIndicatorProps } from "./motion/MorphIndicator";
export { Reveal, type RevealProps, RevealHeight, type RevealHeightProps } from "./motion/Reveal";
export { MorphValue, type MorphValueProps } from "./motion/MorphValue";
export { SkeletonMorph, type SkeletonMorphProps } from "./motion/SkeletonMorph";
export { ReorderableStrips, type ReorderableStrip, type ReorderableStripsProps } from "./ReorderableStrips";
export { useScrollLock } from "./portal/useScrollLock";
export { useModalA11y, type ModalA11y } from "./portal/useModalA11y";
export { useDragDismiss, type DragDismiss, type DragDismissOptions } from "./portal/useDragDismiss";

// Волна 2 — R5 портал, R6 навигация и футер, R7 мобильный слой (дописываются при мерже)
