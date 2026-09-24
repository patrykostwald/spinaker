"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ThreadListItem } from "../types";
import { useAccount } from "../lib/account";
import { apiFetch, apiWrite } from "../lib/api";
import { AccountDialog } from "./AccountDialog";
import { Button } from "../kit/Button";
import { HeartIcon } from "../kit/icons/HeartIcon";

export function ThreadFavoriteButton({ thread }: { thread: Pick<ThreadListItem, "id" | "published" | "title"> }) {
  const account = useAccount(); const ownerId = account.data?.user?.id; const cache = useQueryClient();
  const key = ["thread-favorite", ownerId, thread.id];
  const favorite = useQuery({ queryKey: key, queryFn: () => apiFetch<{ results: { id: number }[] }>(`/api/account/favorites/?thread_id=${thread.id}`), enabled: Boolean(ownerId && thread.published), staleTime: 30_000 });
  const [open, setOpen] = useState(false); const [pending, setPending] = useState(false); const [error, setError] = useState("");
  const saved = Boolean(favorite.data?.results.length);
  async function toggle() { if (!ownerId) { setOpen(true); return; } setPending(true); setError(""); try { await apiWrite(saved ? `/api/account/favorites/${thread.id}/` : "/api/account/favorites/", saved ? {} : { thread_id: thread.id }, saved ? "DELETE" : "POST"); await Promise.all([cache.invalidateQueries({ queryKey: key }), cache.invalidateQueries({ queryKey: ["account-favorites", ownerId] })]); } catch (reason) { setError(reason instanceof Error ? reason.message : "Nie udało się zmienić ulubionych."); } finally { setPending(false); } }
  if (!thread.published) return null;
  return <div className="sc-thread-favorite"><Button type="button" variant="secondary" size="md" pressed={saved} loading={pending || Boolean(ownerId && favorite.isPending)} aria-label={`${saved ? "Usuń z ulubionych" : "Dodaj do ulubionych"}: ${thread.title}`} onClick={toggle} iconStart={<HeartIcon filled={saved} />}>{saved ? "Zapisana" : "Zapisz"}</Button>{favorite.isError ? <Button type="button" variant="quiet" size="sm" onClick={() => favorite.refetch()}>Odśwież ulubione</Button> : null}{error ? <span role="alert" className="sc-t-caption">{error}</span> : null}<AccountDialog open={open} onClose={() => setOpen(false)} /></div>;
}
