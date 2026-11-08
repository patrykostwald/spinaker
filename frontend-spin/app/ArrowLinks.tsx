"use client";

import { useEffect } from "react";

/** Jeden styl odnośników „… →” w całym serwisie (właściciel 5.10, audyt Projektanta): każdy taki odnośnik dostaje klasę sc-ind-link.
 *  Widoki v3 (.sc-v3) mają własny, ten sam styl odnośnika (.sc-v3-lnk) i główny przycisk z gradientem - nie dostają klasy. */
export function ArrowLinks() {
  useEffect(() => {
    const tag = () => document.querySelectorAll<HTMLAnchorElement>("main a").forEach(a => {
      if (!a.classList.contains("sc-ind-link") && a.textContent?.trim().endsWith("→") && !a.closest("nav, .sc-trop-overlay__bar, .sc-overview, .sc-v3")) a.classList.add("sc-ind-link");
    });
    tag();
    const observer = new MutationObserver(tag);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);
  return null;
}
