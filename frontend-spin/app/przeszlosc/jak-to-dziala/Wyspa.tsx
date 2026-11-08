"use client";
import { useStandalone } from '../ui';

/** Wyspa kliencka strony statycznej: tryb osobnej strony przeszłości (bez menu i pasków spin.clinic), nic poza tym. */
export function Standalone() {
  useStandalone();
  return null;
}
