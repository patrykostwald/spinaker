"use client";

/**
 * Dane strony głównej (etap 2, krok 1). Te same wywołania API co w starym `PortalHome`
 * (`getPortalConfig`, `getNewsFeed`, `/api/portal/topic-of-day/`, `getThreads`), plus jedna rzecz,
 * której stara strona nie miała: **tryb demonstracyjny** — gdy backend jest nieosiągalny
 * (fetch rzuca TypeError, nie ApiError) i nie jesteśmy w produkcji, w miejsce danych wchodzą
 * fikstury z witryny (fikcyjne, `przyklad.invalid`, ujemne id, „DEMO” na obrazkach), a strona
 * pokazuje baner „Dane demonstracyjne”. Dzięki temu układ da się oglądać i poprawiać bez Django
 * (docs/UI_KIT_PLAN.md → «Живая работа»). W produkcji zachowanie jest identyczne ze starym.
 */

import { useQuery, useInfiniteQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { ApiError, apiFetch, getThreads } from "../../lib/api";
import { getNewsFeed, getPortalConfig, type NewsFeed, type PortalConfig } from "../../lib/portal";
import type { ThreadDetail } from "../../types";
import { FIXTURE_SOURCES, FIXTURE_STRIPS, makeArticles } from "../showcase/fixtures";

// ---------------------------------------------------------------------------
// Tryb demonstracyjny
// ---------------------------------------------------------------------------

const DEMO_ALLOWED = process.env.NODE_ENV !== "production";

let demoActive = false;
const demoListeners = new Set<() => void>();

function setDemo(active: boolean) {
  if (demoActive === active) return;
  demoActive = active;
  demoListeners.forEach((listener) => listener());
}

/** `true`, gdy choć jedno zapytanie spadło na fikstury — strona pokazuje baner. */
export function useDemoMode(): boolean {
  return useSyncExternalStore(
    (listener) => {
      demoListeners.add(listener);
      return () => demoListeners.delete(listener);
    },
    () => demoActive,
    () => false,
  );
}

function isNetworkFailure(error: unknown): boolean {
  // Brak połączenia (fetch rzuca TypeError) albo 5xx z proxy Next (`/api/*` → backend, którego nie ma).
  // Odpowiedzi 4xx to prawdziwe odpowiedzi backendu — ich NIE maskujemy fiksturami.
  if (error instanceof TypeError) return true;
  return error instanceof ApiError && error.status >= 500;
}

async function withDemo<T>(request: () => Promise<T>, demo: () => T): Promise<T> {
  try {
    return await request();
  } catch (error) {
    if (DEMO_ALLOWED && isNetworkFailure(error)) {
      setDemo(true);
      return demo();
    }
    throw error;
  }
}

function hashParams(input: string): number {
  let hash = 7;
  for (let i = 0; i < input.length; i += 1) hash = (hash * 31 + input.charCodeAt(i)) % 100_003;
  return hash;
}

export const DEMO_CATEGORIES = [
  { value: "article", label: "Artykuł" },
  { value: "interview", label: "Wywiad" },
  { value: "report", label: "Reportaż" },
  { value: "document", label: "Dokument urzędowy" },
  { value: "voting", label: "Głosowanie Sejmu" },
  { value: "factcheck", label: "Fact-check" },
  { value: "video", label: "Film" },
];

function demoConfig(): PortalConfig {
  return {
    categories: DEMO_CATEGORIES,
    sources: FIXTURE_SOURCES,
    top_sources: FIXTURE_SOURCES,
    editorial: { government: null, opposition: null },
    x_editorial: { configured: false, status: "disabled" },
  };
}

function demoFeed(key: string, pageSize: number, page: number): NewsFeed {
  const seed = hashParams(key) + page * 97;
  const results = makeArticles(pageSize, seed).map((article, index) => ({
    ...article,
    id: -(200_000 + seed * 50 + index),
    category: DEMO_CATEGORIES[(seed + index) % DEMO_CATEGORIES.length].value,
  }));
  return {
    results,
    total: pageSize * 4,
    next_page: page < 4 ? page + 1 : null,
    checked_at: new Date().toISOString(),
    latest_published_at: results[0]?.published_date ?? null,
    mode: "latest",
    selection_note: "Dane demonstracyjne",
    top_sources: FIXTURE_SOURCES,
  };
}

// ---------------------------------------------------------------------------
// Hooki
// ---------------------------------------------------------------------------

export function useHomeConfig() {
  return useQuery({
    queryKey: ["home-portal-config"],
    queryFn: () => withDemo(getPortalConfig, demoConfig),
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });
}

export type FeedParams = Parameters<typeof getNewsFeed>[0];

export function useHomeFeed(key: string, params: FeedParams, options?: { enabled?: boolean; refetchInterval?: number }) {
  return useQuery({
    queryKey: ["home-feed", key, JSON.stringify(params)],
    queryFn: async () => {
      const feed = await withDemo(
        () => getNewsFeed(params),
        () => demoFeed(`${key}:${JSON.stringify(params)}`, params?.pageSize ?? 20, params?.page ?? 1),
      );
      return feed;
    },
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval,
    refetchIntervalInBackground: false,
  });
}

export function useHomeInfiniteFeed(key: string, params: Omit<NonNullable<FeedParams>, "page">, options?: { enabled?: boolean }) {
  return useInfiniteQuery({
    enabled: options?.enabled ?? true,
    queryKey: ["home-feed-infinite", key, JSON.stringify(params)],
    initialPageParam: 1,
    queryFn: async ({ pageParam }) => {
      const feed = await withDemo(
        () => getNewsFeed({ ...params, page: pageParam }),
        () => demoFeed(`${key}:${JSON.stringify(params)}`, params.pageSize ?? 30, pageParam),
      );
      return feed;
    },
    getNextPageParam: (last) => last.next_page ?? undefined,
  });
}

export type DailyTopic = {
  query: string | null;
  label: string | null;
  mode: "automatic" | "unavailable";
  source_count: number;
  article_count: number;
};

export function useTopicOfDay() {
  return useQuery({
    queryKey: ["home-topic-of-day"],
    queryFn: () =>
      withDemo(
        () => apiFetch<DailyTopic>("/api/portal/topic-of-day/"),
        (): DailyTopic => ({ query: "temat demonstracyjny", label: "Temat demonstracyjny", mode: "automatic", source_count: 4, article_count: 12 }),
      ),
    refetchInterval: 600_000,
    refetchIntervalInBackground: false,
    staleTime: 600_000,
  });
}

function demoThread(): ThreadDetail {
  const articles = FIXTURE_STRIPS[2].articles;
  return {
    id: -9100,
    title: "Nitka demonstracyjna — układ dwóch kolumn i jednego rzędu",
    slug: "nitka-demonstracyjna",
    thread_type: "context",
    is_featured: true,
    updated_at: articles[0]?.published_date ?? new Date().toISOString(),
    published: true,
    item_count: articles.length,
    description: "Fikcyjna nitka z fikstur witryny — tylko do pracy nad układem.",
    image_url: articles[0]?.image_url ?? "",
    views_count: 0,
    created_at: articles[0]?.published_date ?? new Date().toISOString(),
    author_name: "Autor przykładowy",
    author_role: "editor",
    editorial_slot: "",
    items: articles.map((article, index) => ({
      id: -(9200 + index),
      position: index + 1,
      editorial_note: index === 0 ? "Komentarz do materiału otwierającego (przykład)." : "",
      author_name: "Autor przykładowy",
      author_role: "editor",
      article,
    })),
  };
}

/** Nitka Dr. Spina: pierwsza OPUBLIKOWANA wyróżniona nitka; brak → sekcja pokazuje układ-zapowiedź. */
export function useDrSpinThread() {
  return useQuery({
    queryKey: ["home-dr-spin"],
    queryFn: () =>
      withDemo(
        async () => (await getThreads(true)).results.find((thread) => thread.published) ?? null,
        (): ThreadDetail | null => demoThread(),
      ),
    staleTime: 300_000,
  });
}
