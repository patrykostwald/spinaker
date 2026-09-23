"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiWrite } from "../lib/api";
import { useAccount } from "../lib/account";

export type ThemePreference = "dark" | "light" | "pastel";
type ProfileSettings = { username: string; public_activity: boolean; theme_preference: ThemePreference };

const themes: Array<{ value: ThemePreference; label: string }> = [
  { value: "dark", label: "Ciemny" },
  { value: "light", label: "Jasny" },
  { value: "pastel", label: "Pastelowy" },
];

function resolveTheme(preference: ThemePreference) {
  return preference;
}

function applyTheme(preference: ThemePreference) {
  const root = document.documentElement;
  root.dataset.themePreference = preference;
  root.dataset.theme = resolveTheme(preference);
  root.style.colorScheme = root.dataset.theme === "dark" ? "dark" : "light";
}

export function ThemeSwitcher() {
  const account = useAccount();
  const ownerId = account.data?.user?.id;
  const cache = useQueryClient();
  const [preference, setPreference] = useState<ThemePreference>("dark");
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const container = useRef<HTMLDivElement>(null);
  const profile = useQuery({
    queryKey: ["account-profile", ownerId],
    queryFn: () => apiFetch<ProfileSettings>("/api/account/profile/"),
    enabled: Boolean(ownerId),
  });

  useEffect(() => {
    const stored = window.localStorage.getItem("spin-theme");
    const initial = themes.some(theme => theme.value === stored) ? stored as ThemePreference : "dark";
    setPreference(initial);
    applyTheme(initial);

  }, []);

  useEffect(() => {
    if (!profile.data) return;
    const next = themes.some(theme => theme.value === profile.data.theme_preference) ? profile.data.theme_preference : "dark";
    window.localStorage.setItem("spin-theme", next);
    setPreference(next);
    applyTheme(next);
  }, [profile.data]);

  useEffect(() => {
    function close(event: PointerEvent) {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", escape);
    };
  }, []);

  async function choose(next: ThemePreference) {
    const previous = preference;
    window.localStorage.setItem("spin-theme", next);
    setPreference(next);
    applyTheme(next);
    setOpen(false);
    setError("");
    if (!ownerId) return;
    setSaving(true);
    try {
      const updated = await apiWrite<ProfileSettings>(
        "/api/account/profile/",
        { theme_preference: next },
        "PATCH",
      );
      cache.setQueryData(["account-profile", ownerId], updated);
    } catch {
      window.localStorage.setItem("spin-theme", previous);
      setPreference(previous);
      applyTheme(previous);
      setError("Nie udało się zapisać motywu.");
    } finally {
      setSaving(false);
    }
  }

  return <div className="theme-switcher" ref={container}>
    <button
      type="button"
      className="theme-trigger"
      aria-label={`Motyw: ${themes.find(theme => theme.value === preference)?.label ?? "Ciemny"}`}
      aria-expanded={open}
      aria-haspopup="menu"
      disabled={saving}
      onClick={() => setOpen(value => !value)}
    >
      <span className="theme-bar theme-bar-one" />
      <span className="theme-bar theme-bar-two" />
      <span className="theme-bar theme-bar-three" />
    </button>
    {open && <div className="theme-menu" role="menu" aria-label="Wybierz motyw">
      {themes.map(theme => <button
        type="button"
        role="menuitemradio"
        aria-checked={preference === theme.value}
        className="theme-option"
        key={theme.value}
        disabled={saving}
        onClick={() => void choose(theme.value)}
      >
        <span>{theme.label}</span><span aria-hidden="true">{preference === theme.value ? "●" : ""}</span>
      </button>)}
    </div>}
    {error && <span className="theme-error" role="alert">{error}</span>}
  </div>;
}
