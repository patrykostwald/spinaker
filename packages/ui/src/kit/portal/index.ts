/**
 * Wewnętrzny barrel katalogu `portal/` (R5) — używany przez sekcję witryny i (docelowo)
 * przez integratora przy dopisywaniu eksportów do `kit/index.ts` (patrz raport R5).
 */
export {
  PortalProvider,
  usePortal,
  usePortalApi,
  usePortalState,
  usePortalEngine,
  type PortalApi,
  type PortalStateValue,
  type PortalEngineValue,
  type PortalHistoryMode,
  type FlightOrigin,
  type PortalExit,
} from "./PortalProvider";
export { PortalLayer, type PortalLayerProps } from "./PortalLayer";
export { useHistoryPortal, type UseHistoryPortalOptions, type HistoryPortal } from "./useHistoryPortal";
export { useHoverExpand } from "./useHoverExpand";
export { useScrollLock } from "./useScrollLock";
export { useModalA11y, type ModalA11y } from "./useModalA11y";
export { useDragDismiss, type DragDismiss, type DragDismissOptions } from "./useDragDismiss";
