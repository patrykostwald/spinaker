"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Segmented } from "../kit/Segmented";
import { apiFetch, apiWrite } from "../lib/api";
import { useAccount } from "../lib/account";

type StoredTheme = "dark" | "light" | "pastel";
type ThemeMode = "dark" | "light" | "auto";
type ProfileSettings = { username: string; public_activity: boolean; theme_preference: StoredTheme };

function systemTheme(): "dark" | "light" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolvedTheme(mode: ThemeMode): "dark" | "light" {
  return mode === "auto" ? systemTheme() : mode;
}

function applyTheme(mode: ThemeMode) {
  const root = document.documentElement;
  const theme = resolvedTheme(mode);
  root.classList.add("sc-theme-transition");
  root.dataset.themePreference = mode;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  window.setTimeout(() => root.classList.remove("sc-theme-transition"), 300);
}

export function ThemeSwitcher() {
  const account = useAccount();
  const ownerId = account.data?.user?.id;
  const cache = useQueryClient();
  const [mode, setMode] = useState<ThemeMode>("dark");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const profile = useQuery({
    queryKey: ["account-profile", ownerId],
    queryFn: () => apiFetch<ProfileSettings>("/api/account/profile/"),
    enabled: Boolean(ownerId),
  });

  useEffect(() => {
    const stored = window.localStorage.getItem("spin-theme");
    const next: ThemeMode = stored === "auto" ? "auto" : stored === "light" || stored === "pastel" ? "light" : "dark";
    if (stored === "pastel") window.localStorage.setItem("spin-theme", "light");
    setMode(next);
    applyTheme(next);
  }, []);

  useEffect(() => {
    if (!profile.data) return;
    const next: ThemeMode = profile.data.theme_preference === "pastel" ? "light" : profile.data.theme_preference;
    window.localStorage.setItem("spin-theme", next);
    setMode(next);
    applyTheme(next);
  }, [profile.data]);

  useEffect(() => {
    if (mode !== "auto") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const refresh = () => applyTheme("auto");
    media.addEventListener("change", refresh);
    return () => media.removeEventListener("change", refresh);
  }, [mode]);

  async function choose(next: string) {
    const nextMode = next as ThemeMode;
    const previous = mode;
    window.localStorage.setItem("spin-theme", nextMode);
    setMode(nextMode);
    applyTheme(nextMode);
    setError("");
    if (!ownerId) return;
    setSaving(true);
    try {
      const updated = await apiWrite<ProfileSettings>("/api/account/profile/", { theme_preference: resolvedTheme(nextMode) }, "PATCH");
      cache.setQueryData(["account-profile", ownerId], updated);
    } catch {
      window.localStorage.setItem("spin-theme", previous);
      setMode(previous);
      applyTheme(previous);
      setError("Nie udało się zapisać motywu.");
    } finally {
      setSaving(false);
    }
  }

  return <div className="sc-theme-switcher">
    <Segmented name="theme" label="Motyw" value={mode} onChange={choose} disabled={saving} options={[{ value: "dark", label: "Ciemny" }, { value: "light", label: "Jasny" }, { value: "auto", label: "Automatyczny" }]} />
    {error ? <p className="sc-t-caption sc-text-2" role="alert">{error}</p> : null}
  </div>;
}
