"use client";

/**
 * Baza w trybie „Osoby publiczne” (kategoria w filtrach Bazy): siatka profili z rejestru osób publicznych
 * (`/api/public-figures/?q=`), to samo pole szukania co dla materiałów, doładowanie stron w przewijanym
 * obszarze Bazy. Karta prowadzi do profilu `/osoby-publiczne/<id>` (oś czasu, głosowania, relacje, materiały).
 */

import { useInfiniteQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useMemo, useRef, type RefObject } from "react";
import { apiFetch } from "../../lib/api";
import { ROLE_CATEGORY_LABELS, type PublicFigureSummary } from "../../lib/publicFigures";

type Page = { count: number; page: number; page_size: number; results: PublicFigureSummary[] };
const PAGE_SIZE = 60;

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
}

export function usePeople(query: string, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: ["home-people", query],
    enabled,
    initialPageParam: 1,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ page: String(pageParam), page_size: String(PAGE_SIZE) });
      if (query.trim()) params.set("q", query.trim());
      return apiFetch<Page>(`/api/public-figures/?${params}`);
    },
    getNextPageParam: (last) => (last.page * last.page_size < last.count ? last.page + 1 : undefined),
    staleTime: 60_000,
  });
}

export function HomePeople({ query, scrollRoot }: { query: string; scrollRoot: RefObject<HTMLElement> }) {
  const people = usePeople(query, true);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const rows = useMemo(() => people.data?.pages.flatMap((page) => page.results) ?? [], [people.data]);

  useEffect(() => {
    const target = sentinelRef.current;
    if (!target || !people.hasNextPage || people.isFetchingNextPage) return;
    const observer = new IntersectionObserver(([entry]) => entry.isIntersecting && people.fetchNextPage(), { root: scrollRoot.current, rootMargin: "400px 0px" });
    observer.observe(target);
    return () => observer.disconnect();
  }, [people, people.hasNextPage, people.isFetchingNextPage, scrollRoot]);

  if (people.isPending) return <p role="status" className="sc-t-body-s sc-text-2">Ładuję osoby publiczne…</p>;
  if (people.isError) return <p role="alert" className="sc-t-body-s sc-text-2">Nie udało się pobrać rejestru osób publicznych.</p>;
  if (!rows.length) return <p className="sc-t-body-s sc-text-2">Brak osób publicznych pasujących do hasła.</p>;

  return (
    <>
      <ul className="sc-home-baza__grid sc-home-people" role="list">
        {rows.map((person) => (
          <li key={person.id}>
            <Link href={`/osoby-publiczne/${person.id}`} className="sc-home-person sc-hoverable">
              <span className="sc-home-person__mono" aria-hidden="true">
                {initials(person.name)}
              </span>
              <span className="sc-home-person__body">
                <span className="sc-t-caption sc-text-3 sc-home-person__kind">{ROLE_CATEGORY_LABELS[person.role_category] ?? "Osoba publiczna"}</span>
                <span className="sc-t-title-xs sc-home-person__name">{person.name}</span>
                <span className="sc-t-meta sc-text-2 sc-home-person__role">
                  {person.role_title}
                  {person.organisation ? ` · ${person.organisation}` : ""}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {people.hasNextPage ? (
        <div ref={sentinelRef} className="sc-home-baza__more" role="status">
          {people.isFetchingNextPage ? "Ładuję kolejne osoby…" : "Przewiń siatkę niżej, aby załadować kolejne osoby."}
        </div>
      ) : null}
    </>
  );
}
