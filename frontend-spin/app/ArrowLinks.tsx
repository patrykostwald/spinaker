"use client";

import { useEffect } from "react";

/** Jeden styl odnośników „… →” w całym serwisie (właściciel 5.10, audyt Projektanta): każdy taki odnośnik dostaje klasę sc-ind-link. */
export function ArrowLinks() {
  useEffect(() => {
    const tag = () => document.querySelectorAll<HTMLAnchorElement>("main a").forEach(a => {
      if (!a.classList.contains("sc-ind-link") && a.textContent?.trim().endsWith("→") && !a.closest("nav, .sc-trop-overlay__bar, .sc-overview")) a.classList.add("sc-ind-link");
    });
    tag();
    const observer = new MutationObserver(tag);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);
  return null;
}
